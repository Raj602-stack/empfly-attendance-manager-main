# code
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import Attendance, MemberScan


#  pre delete attendance model signal
@receiver(pre_delete, sender=Attendance)
def reset_attendance_scans(sender, instance, **kwargs):
    """signal receiver to rest all scans object in attendance instance"""

    # update the scan objects
    instance.scans.update(is_computed=False, status="pending")
