import os
import time
import cv2
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.base import ContentFile
from django.core.management import call_command
from inventory.models import WallConfig
from .models import AuditSession, AuditItemResult
from vision.engine import engine
import threading
from django.core.mail import EmailMessage
from django.conf import settings

def get_default_wall():
    wall, _ = WallConfig.objects.get_or_create(id=1)
    return wall

def _build_workspace_context(wall, active_audit=None, scan_error=None, feedback=None):
    history_list = list(wall.audits.all()[:30])

    if active_audit is None:
        active_audit = history_list[0] if history_list else None
    return {
        "wall": wall,
        "slots": wall.slots.all(),
        "latest_audit": active_audit,
        "audit_history": history_list,
        "scan_error": scan_error,
        "feedback": feedback,
    }


def dashboard(request):
    wall = get_default_wall()
    context = _build_workspace_context(wall)
    return render(request, "audit/dashboard.html", context)

def _send_missing_tools_email(recipient_email, wall_name, newly_missing_names, image_bytes, session_id):
    """שולח אימייל ברקע רק עבור כלים שנעלמו בסריקה הנוכחית"""
    try:
        tools_str = ", ".join(newly_missing_names)
        subject = f"⚠️ התרעת קיר כלים ({wall_name}): נלקחו כלים - {tools_str}"
        body = (
            f"שלום,\n\n"
            f"זוהתה היעלמות חדשה של כלי עבודה בעמדה '{wall_name}' (סריקה #{session_id}):\n"
            f"כלים שנעלמו כעת:\n"
            + "\n".join([f" - {name}" for name in newly_missing_names])
            + "\n\nמצורפת תמונת הבקרה העדכנית מהמצלמה.\n"
            f"לא יישלחו התרעות נוספות על כלים אלו עד להחזרתם למקום."
        )
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "toolwall@localhost"),
            to=[recipient_email],
        )
        if image_bytes:
            email.attach(f"audit_{session_id}.jpg", image_bytes, "image/jpeg")
        email.send(fail_silently=False)
        print(f"[Email Alert] נשלחה התרעה אל {recipient_email} עבור: {tools_str}")
    except Exception as e:
        print(f"[Email Alert Error] שגיאה בשליחת מייל: {e}")

def run_scan(request):
    wall = get_default_wall()
    slots = list(wall.slots.all())
    scan_error = None

    if request.method == "POST":
        t0 = time.perf_counter()
        try:
            frame = engine.capture_frame(wall)
            dx, dy, displaced = engine.get_drift(frame, wall)
            annotated = frame.copy()
            h_frame, w_frame = frame.shape[:2]

            if wall.anchor_w > 0 and wall.anchor_h > 0:
                ax = max(0, min(w_frame - 1, wall.anchor_x + dx))
                ay = max(0, min(h_frame - 1, wall.anchor_y + dy))
                cv2.rectangle(annotated, (ax, ay), (ax + wall.anchor_w, ay + wall.anchor_h), (255, 180, 0), 2)
                cv2.putText(annotated, "ANCHOR", (ax, max(20, ay - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 180, 0), 2)

            valid_slots = []
            crops = []
            ref_embeddings = []
            coords = []

            for idx, slot in enumerate(slots, start=1):
                x = max(0, min(w_frame - 1, slot.roi_x + dx))
                y = max(0, min(h_frame - 1, slot.roi_y + dy))
                w = min(slot.roi_w, w_frame - x)
                h = min(slot.roi_h, h_frame - y)
                crop = frame[y:y+h, x:x+w]
                if crop.size == 0:
                    continue

                if not slot.reference_embedding and slot.reference_image:
                    ref_bgr = cv2.imread(slot.reference_image.path)
                    if ref_bgr is not None:
                        slot.reference_embedding = engine.compute_single_embedding(ref_bgr)
                        slot.save(update_fields=["reference_embedding"])

                if slot.reference_embedding:
                    valid_slots.append((idx, slot))
                    crops.append(crop)
                    ref_embeddings.append(slot.reference_embedding)
                    coords.append((x, y, w, h))

            scores = engine.batch_compare(crops, ref_embeddings)

            present_count = 0
            missing_count = 0
            item_results = []
            newly_missing_tools = []

            for (idx, slot), score, (x, y, w, h) in zip(valid_slots, scores, coords):
                was_present_before = slot.is_present
                is_present = score >= slot.similarity_threshold
                pct_score = round(score * 100, 1)

                if was_present_before and not is_present:
                    newly_missing_tools.append(slot.name)
                slot.is_present = is_present
                slot.last_score = pct_score
                slot.save(update_fields=["is_present", "last_score"])

                if is_present:
                    present_count += 1
                    color = (40, 200, 40)
                    label = f"#{idx} OK ({pct_score}%)"
                else:
                    missing_count += 1
                    color = (30, 30, 230)
                    label = f"#{idx} MISSING ({pct_score}%)"

                cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 3)
                cv2.putText(annotated, label, (x, max(25, y - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

                item_results.append((slot, is_present, pct_score))

            duration_ms = int((time.perf_counter() - t0) * 1000)
            _, buf = cv2.imencode(".jpg", annotated)

            session = AuditSession.objects.create(
                wall=wall,
                total_tools=len(valid_slots),
                present_tools=present_count,
                missing_tools=missing_count,
                drift_dx=dx,
                drift_dy=dy,
                camera_displaced=displaced,
                duration_ms=duration_ms,
            )
            image_bytes = buf.tobytes()
            session.annotated_image.save(f"audit_{session.id}.jpg", ContentFile(image_bytes), save=True)

            # הדפסת דיבאג ברורה לטרמינל של VS Code
            print(f"[Scan #{session.id}] כלים שנעלמו כעת: {newly_missing_tools} | אימייל מוגדר: '{wall.alert_email}'")

            email_feedback = None
            if newly_missing_tools:
                if wall.alert_email:
                    threading.Thread(
                        target=_send_missing_tools_email,
                        args=(wall.alert_email, wall.name, newly_missing_tools, image_bytes, session.id),
                        daemon=True,
                    ).start()
                    email_feedback = f"📧 נשלחה התרעת מייל אל {wall.alert_email} עבור: {', '.join(newly_missing_tools)}"
                else:
                    email_feedback = "⚠️ זוהה כלי שנעלם כעת, אך לא הוגדרה כתובת מייל במסך ההגדרות!"
            for slot, is_present, pct_score in item_results:
                AuditItemResult.objects.create(
                    session=session,
                    slot=slot,
                    is_present=is_present,
                    score=pct_score,
                )

        except Exception as e:
            scan_error = str(e)

    context = _build_workspace_context(wall, scan_error=scan_error)
    if request.headers.get("HX-Request"):
        return render(request, "audit/partials/workspace.html", context)
    return redirect("dashboard")


def view_audit_session(request, session_id):
    wall = get_default_wall()
    selected_session = get_object_or_404(AuditSession, id=session_id, wall=wall)
    context = _build_workspace_context(
        wall,
        active_audit=selected_session,
        feedback=f"מציג סריקה מתאריך {selected_session.timestamp.strftime('%d/%m/%Y %H:%M:%S')} (#{selected_session.id})"
    )
    return render(request, "audit/partials/workspace.html", context)


def delete_audit_session(request, session_id):
    """מחיקת סריקה בודדת (כולל קובץ התמונה מהדיסק)"""
    wall = get_default_wall()
    if request.method == "POST":
        session = get_object_or_404(AuditSession, id=session_id, wall=wall)
        if session.annotated_image:
            try:
                if os.path.isfile(session.annotated_image.path):
                    os.remove(session.annotated_image.path)
            except Exception:
                pass
        session.delete()

    context = _build_workspace_context(wall, feedback="הסריקה והתמונה שלה נמחקו בהצלחה.")
    return render(request, "audit/partials/workspace.html", context)

def clean_audit_history(request):
    """הפעלת פקודת הניקוי clean_pics ישירות מהדשבורד"""
    wall = get_default_wall()
    feedback = None
    if request.method == "POST":
        mode = request.POST.get("mode", "keep5")
        if mode == "all":
            call_command("clean_pics", all=True)
            feedback = "כל היסטוריית הסריקות והתמונות נוקתה מהדיסק!"
        else:
            call_command("clean_pics", keep=5)
            feedback = "היסטוריית התמונות נוקתה (נשמרו 5 הסריקות האחרונות בלבד)."

    context = _build_workspace_context(wall, feedback=feedback)
    return render(request, "audit/partials/workspace.html", context)