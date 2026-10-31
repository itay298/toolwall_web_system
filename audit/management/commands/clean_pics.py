import os
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from audit.models import AuditSession
from inventory.models import WallConfig, ToolSlot


class Command(BaseCommand):
    help = "ניקוי תמונות סריקה ישנות וקבצי מדיה יתומים מהדיסק וממסד הנתונים"

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            type=int,
            default=20,
            help="מספר הסריקות האחרונות שיש לשמור (ברירת מחדל: 20)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="מחיקת כל היסטוריית הסריקות והתמונות שלהן לחלוטין",
        )

    def handle(self, *args, **options):
        keep = 0 if options["all"] else max(0, options["keep"])

        # 1. מחיקת סשנים ישנים ממסד הנתונים ומהדיסק
        sessions = list(AuditSession.objects.order_by("-timestamp"))
        to_delete = sessions[keep:]

        deleted_sessions_count = 0
        for session in to_delete:
            if session.annotated_image:
                try:
                    if os.path.isfile(session.annotated_image.path):
                        os.remove(session.annotated_image.path)
                except Exception as e:
                    self.stderr.write(f"שגיאה במחיקת קובץ סריקה: {e}")
            session.delete()
            deleted_sessions_count += 1

        # 2. איתור ומחיקת קבצים יתומים (Orphaned Files) בתיקיית media/
        media_root = Path(settings.MEDIA_ROOT)
        referenced_files = set()

        for s in AuditSession.objects.exclude(annotated_image=""):
            if s.annotated_image:
                referenced_files.add(Path(s.annotated_image.path).resolve())

        for slot in ToolSlot.objects.exclude(reference_image=""):
            if slot.reference_image:
                referenced_files.add(Path(slot.reference_image.path).resolve())

        for wall in WallConfig.objects.all():
            if wall.calibration_frame:
                referenced_files.add(Path(wall.calibration_frame.path).resolve())
            if wall.anchor_image:
                referenced_files.add(Path(wall.anchor_image.path).resolve())

        orphan_files_deleted = 0
        for subfolder in ["audits", "tools_ref"]:
            folder_path = media_root / subfolder
            if not folder_path.exists():
                continue
            for file_path in folder_path.iterdir():
                if file_path.is_file() and file_path.name != ".gitkeep":
                    if file_path.resolve() not in referenced_files:
                        try:
                            file_path.unlink()
                            orphan_files_deleted += 1
                        except Exception as e:
                            self.stderr.write(f"שגיאה במחיקת קובץ יתום {file_path.name}: {e}")

        self.stdout.write(
            self.style.SUCCESS(
                f"ניקוי הושלם: נמחקו {deleted_sessions_count} סריקות ישנות ו-{orphan_files_deleted} קבצים יתומים (נשמרו {keep} אחרונות)."
            )
        )