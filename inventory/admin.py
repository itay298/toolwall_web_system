from django.contrib import admin
from .models import WallConfig, ToolSlot

@admin.register(WallConfig)
class WallConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'camera_index', 'frame_width', 'frame_height', 'warmup_frames')

@admin.register(ToolSlot)
class ToolSlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'wall', 'roi_x', 'roi_y', 'roi_w', 'roi_h', 'is_present', 'last_score')
