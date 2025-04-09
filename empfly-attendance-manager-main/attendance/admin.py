from django.contrib import admin
from attendance.models import MemberScan, Attendance, AttendanceComputationHistory, PresentByDefault

admin.site.register(MemberScan)
admin.site.register(Attendance)
admin.site.register(PresentByDefault)
admin.site.register(AttendanceComputationHistory)
