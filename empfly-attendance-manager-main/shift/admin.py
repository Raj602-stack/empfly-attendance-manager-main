from django.contrib import admin

from .models import Shift, LocationSettings, ShiftScheduleLog

admin.site.register(Shift)
admin.site.register(LocationSettings)
admin.site.register(ShiftScheduleLog)
