from django.contrib import admin
from leave.models import ApprovalWorkflow, LeaveBalanceActivity, LeaveType, LeaveBalance, LeaveRequest, Applicability

admin.site.register(LeaveType)
admin.site.register(LeaveBalance)
admin.site.register(LeaveRequest)
admin.site.register(Applicability)
admin.site.register(LeaveBalanceActivity)
admin.site.register(ApprovalWorkflow)