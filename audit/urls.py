from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('scan/', views.run_scan, name='run_scan'),
    path('audit/<int:session_id>/view/', views.view_audit_session, name='view_audit_session'),
    path('audit/<int:session_id>/delete/', views.delete_audit_session, name='delete_audit_session'),
    path('audit/clean/', views.clean_audit_history, name='clean_audit_history'),
]