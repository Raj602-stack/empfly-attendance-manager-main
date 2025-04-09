from datetime import date, datetime, timedelta
from genericpath import exists

from shift.exceptions import EditShiftError
from attendance.models import AttendanceComputationHistory
from django.db.models import Min, Q, Max
from django.core.exceptions import ValidationError
from utils.utils import convert_to_time
from env import SHIFT_HISTORY_LIMIT
from . import models
from utils import date_time



def allow_geo_fencing_if_location_exists(shift):
    location_settings = shift.location_settings.all()

    if location_settings.count() > 0:
        shift.enable_geo_fencing = True
        shift.save()

        system_location = location_settings.first().system_location
        org = system_location.organization
        settings = org.shift_management_settings
        settings["enable_geo_fencing"] = True
        org.shift_management_settings = settings
        org.save()


def validate_shift_status_changing(shift, org):
    print("-------------" * 10)

    shift_schedule_log = models.ShiftScheduleLog

    history = AttendanceComputationHistory.objects.filter(shift=shift)

    log = shift_schedule_log.objects.filter(
        organization=org, status="active", shift=shift
    )
    min_date = log.aggregate(Min("start_date"))["start_date__min"]

    if min_date is None:
        print("################# Success Shift not assigned yet. ###################")
        return

    max_date = date_time.today_date()
    current_log = log.filter(start_date__lte=max_date, end_date__gte=max_date)

    if current_log.count() == 1:
        current_log = current_log.first()
    else:
        current_log = log.filter(start_date__lte=max_date, end_date__isnull=True)
        if current_log.count() == 1 and current_log.first().start_date <= max_date:
            current_log = current_log.first()

    print("min_date", min_date, type(min_date))

    if min_date > max_date:
        return

    print("max_date", max_date, type(max_date))

    history = history.filter(created_at__date__lte=max_date)

    if history.filter(status="failed").exists():
        raise ValidationError(
            "Cannot edit shift. Shift computation is failed in past days."
        )

    diff = max_date - min_date
    no_days = diff.days

    print(diff)
    print(no_days)

    print(datetime.now().time())
    print(datetime.now())

    # if datetime.now().time() < shift.start_time:
    #     no_days -= 1

    if history.count() != no_days:
        raise ValidationError("Cannot edit shift. Some attendance history not found.")
    print("###################### Sucess ######################")


# def is_shift_editable(shift, org):
#     attendance_computation_history = models.AttendanceComputationHistory
#     shift_schedule_log = models.ShiftScheduleLog

#     history = attendance_computation_history.objects.filter(shift=shift)
#     logs = shift_schedule_log.objects.filter(shift=shift)

#     today = date.today()
#     curr_time = datetime.now().time()

#     logs = logs.filter(start_date__lte=today)

#     min_date = logs.aggregate(Min("start_date"))["start_date__min"]
#     max_date = logs.aggregate(Max("end_date"))["start_date__max"]

#     if max_date is None or max_date and max_date > today:
#         max_date = today

#     if min_date is None:
#         return

#     if max_date == today:
#         today_log = logs.filter(start_date__lte=max_date, end_date__gte=max_date)

#         if today_log.count() == 1:
#             today_log = today_log.first()
#         else:
#             today_log = logs.filter(start_date__lte=max_date, end_date__isnull=True)
#             if today_log.count() == 1 and today_log.first().star_date >= today:
#                 today_log = today_log.first()

#         today_shift = today_log.shift

#         if curr_time < today_shift.start_time:
#             pass

#     diff = max_date - min_date


def is_shift_editable(shift):

    """ Shift cannot edit if in the past days shift computation is failed.
    """

    history = AttendanceComputationHistory.objects.filter(shift=shift)

    today = date_time.today_date()
    curr_time = date_time.curr_time()

    if curr_time < shift.computation_time:
        today = today - timedelta(days=1)

    min_date = today - timedelta(days=SHIFT_HISTORY_LIMIT)

    history = history.filter(created_at__date__range=[min_date, today])

    if history.filter(~Q(status="completed")).exists():
        raise EditShiftError(
            "Cannot edit shift. History exists with started or failed status."
        )
