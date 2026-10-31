from django.contrib import admin
from .models import AuditSession, AuditItemResult

admin.site.register(AuditSession)
admin.site.register(AuditItemResult)
