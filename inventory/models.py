from django.db import models


class WallConfig(models.Model):
    name = models.CharField(max_length=100, default="קיר כלים ראשי")
    camera_index = models.IntegerField(default=0)
    frame_width = models.IntegerField(default=1920)
    frame_height = models.IntegerField(default=1080)
    warmup_frames = models.IntegerField(default=45, help_text="מספר פריימים לייצוב פוקוס וחשיפה")

    alert_email = models.EmailField(max_length=254, blank=True, null=True, default="")
    calibration_frame = models.ImageField(upload_to="calibration/", null=True, blank=True)

    anchor_x = models.IntegerField(default=0)
    anchor_y = models.IntegerField(default=0)
    anchor_w = models.IntegerField(default=0)
    anchor_h = models.IntegerField(default=0)
    anchor_image = models.ImageField(upload_to="anchors/", null=True, blank=True)

    def __str__(self):
        return f"{self.name} (Cam #{self.camera_index})"


class ToolSlot(models.Model):
    wall = models.ForeignKey(WallConfig, on_delete=models.CASCADE, related_name="slots")
    name = models.CharField(max_length=100, db_index=True)
    roi_x = models.IntegerField()
    roi_y = models.IntegerField()
    roi_w = models.IntegerField()
    roi_h = models.IntegerField()

    reference_image = models.ImageField(upload_to="tools_ref/")
    reference_embedding = models.JSONField(null=True, blank=True)
    similarity_threshold = models.FloatField(default=0.75)

    is_present = models.BooleanField(default=True)
    last_score = models.FloatField(default=100.0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name
