import os
import cv2
from django.shortcuts import render, get_object_or_404, redirect
from django.core.files.base import ContentFile
from .models import WallConfig, ToolSlot
from vision.engine import engine


def get_default_wall():
    wall, _ = WallConfig.objects.get_or_create(id=1)
    return wall


def calibrate_studio(request):
    wall = get_default_wall()
    slots = wall.slots.all()
    return render(request, "inventory/calibrate.html", {
        "wall": wall,
        "slots": slots,
    })


def calibrate_snap(request):
    wall = get_default_wall()
    error_message = None
    if request.method == "POST":
        try:
            frame = engine.capture_frame(wall)
            _, buf = cv2.imencode(".jpg", frame)
            wall.calibration_frame.save("calib_base.jpg", ContentFile(buf.tobytes()), save=True)
        except Exception as e:
            error_message = str(e)

    return render(request, "inventory/partials/canvas_box.html", {
        "wall": wall,
        "error_message": error_message,
    })


def calibrate_add_slot(request):
    wall = get_default_wall()
    feedback = None

    if request.method == "POST" and wall.calibration_frame:
        try:
            x = max(0, int(float(request.POST.get("x", 0))))
            y = max(0, int(float(request.POST.get("y", 0))))
            w = max(0, int(float(request.POST.get("w", 0))))
            h = max(0, int(float(request.POST.get("h", 0))))
            target_type = request.POST.get("target_type", "tool")
            name = request.POST.get("name", "").strip()
            threshold = float(request.POST.get("threshold", 0.75))

            full_img = cv2.imread(wall.calibration_frame.path)
            if full_img is not None and w > 5 and h > 5:
                img_h, img_w = full_img.shape[:2]
                x = min(x, img_w - 1)
                y = min(y, img_h - 1)
                w = min(w, img_w - x)
                h = min(h, img_h - y)

                crop = full_img[y:y+h, x:x+w]
                _, buf = cv2.imencode(".jpg", crop)

                if target_type == "anchor":
                    wall.anchor_x, wall.anchor_y, wall.anchor_w, wall.anchor_h = x, y, w, h
                    wall.anchor_image.save("anchor_ref.jpg", ContentFile(buf.tobytes()), save=True)
                    feedback = "נקודת העוגן נשמרה בהצלחה!"
                else:
                    if not name:
                        name = f"כלי #{wall.slots.count() + 1}"
                    embedding = engine.compute_single_embedding(crop)
                    slot = ToolSlot(
                        wall=wall,
                        name=name,
                        roi_x=x,
                        roi_y=y,
                        roi_w=w,
                        roi_h=h,
                        reference_embedding=embedding,
                        similarity_threshold=threshold,
                        is_present=True,
                        last_score=100.0,
                    )
                    slot.reference_image.save(f"tool_ref_{wall.slots.count() + 1}.jpg", ContentFile(buf.tobytes()), save=True)
                    feedback = f"הכלי '{name}' נגזר, קודד ב-SigLIP ונשמר!"
            else:
                feedback = "שגיאה: יש לסמן מלבן תקין על גבי התמונה."
        except Exception as e:
            feedback = f"שגיאה בשמירה: {e}"

    return render(request, "inventory/partials/slots_panel.html", {
        "wall": wall,
        "slots": wall.slots.all(),
        "feedback": feedback,
    })


def calibrate_delete_slot(request, slot_id):
    wall = get_default_wall()
    slot = get_object_or_404(ToolSlot, id=slot_id, wall=wall)
    slot.delete()
    return render(request, "inventory/partials/slots_panel.html", {
        "wall": wall,
        "slots": wall.slots.all(),
        "feedback": "הכלי הוסר מהלוח.",
    })


def calibrate_clear_anchor(request):
    wall = get_default_wall()
    wall.anchor_w = 0
    wall.anchor_h = 0
    wall.save()
    return render(request, "inventory/partials/slots_panel.html", {
        "wall": wall,
        "slots": wall.slots.all(),
        "feedback": "נקודת העוגן אופסה.",
    })


def hardware_settings(request):
    wall = get_default_wall()
    return render(request, "inventory/settings.html", {"wall": wall})


def test_and_save_camera(request):
    wall = get_default_wall()
    error_message = None
    success_message = None

    if request.method == "POST":
        try:
            wall.name = request.POST.get("name", wall.name).strip() or wall.name
            wall.alert_email = request.POST.get('alert_email', "").strip()
            wall.camera_index = int(request.POST.get("camera_index", wall.camera_index))
            wall.frame_width = int(request.POST.get("frame_width", wall.frame_width))
            wall.frame_height = int(request.POST.get("frame_height", wall.frame_height))
            wall.warmup_frames = max(1, int(request.POST.get("warmup_frames", wall.warmup_frames)))
            wall.save()

            frame = engine.capture_frame(wall)
            _, buf = cv2.imencode(".jpg", frame)
            wall.calibration_frame.save("calib_base.jpg", ContentFile(buf.tobytes()), save=True)
            success_message = f"המצלמה באינדקס {wall.camera_index} אומתה בהצלחה ({wall.warmup_frames} פריימי ייצוב)!"
        except Exception as e:
            error_message = str(e)

    return render(request, "inventory/partials/cam_preview.html", {
        "wall": wall,
        "error_message": error_message,
        "success_message": success_message,
    })
