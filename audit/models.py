from django.db import models
from django.utils import timezone
from inventory.models import WallConfig, ToolSlot


class AuditSession(models.Model):
    wall = models.ForeignKey(WallConfig, on_delete=models.CASCADE, related_name="audits")
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    annotated_image = models.ImageField(upload_to="audits/")
    total_tools = models.IntegerField(default=0)
    present_tools = models.IntegerField(default=0)
    missing_tools = models.IntegerField(default=0)
    drift_dx = models.IntegerField(default=0)
    drift_dy = models.IntegerField(default=0)
    camera_displaced = models.BooleanField(default=False)
    duration_ms = models.IntegerField(default=0)

    class Meta:
        ordering = ["-timestamp"]


class AuditItemResult(models.Model):
    session = models.ForeignKey(AuditSession, on_delete=models.CASCADE, related_name="items")
    slot = models.ForeignKey(ToolSlot, on_delete=models.CASCADE)
    is_present = models.BooleanField()
    score = models.FloatField()
