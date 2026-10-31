from django.urls import path
from . import views

urlpatterns = [
    path('calibrate/', views.calibrate_studio, name='calibrate_studio'),
    path('calibrate/snap/', views.calibrate_snap, name='calibrate_snap'),
    path('calibrate/slot/add/', views.calibrate_add_slot, name='calibrate_add_slot'),
    path('calibrate/slot/<int:slot_id>/delete/', views.calibrate_delete_slot, name='calibrate_delete_slot'),
    path('calibrate/anchor/clear/', views.calibrate_clear_anchor, name='calibrate_clear_anchor'),
    path('settings/', views.hardware_settings, name='hardware_settings'),
    path('settings/test-cam/', views.test_and_save_camera, name='test_and_save_camera'),
]
