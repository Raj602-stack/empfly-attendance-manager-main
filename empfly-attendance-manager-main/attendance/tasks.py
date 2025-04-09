from django.db.models import Q
from django.conf import settings
from celery import shared_task

from attendance.models import Attendance, MemberScan, PresentByDefault
from member.models import Member
from organization.models import Organization
# from roster.models import Roster
from leave.models import LeaveRequest
from utils import create_data, read_data

import datetime as dt
import logging


logger = logging.getLogger(__name__)


def get_current_leave_request(member: Member) -> LeaveRequest:
    current_date = read_data.get_current_date()
    return LeaveRequest.objects.filter(
        Q(member=member)
        & Q(status="approved")
        & Q(start_date__lte=current_date)
        & Q(end_date__gte=current_date)
    ).first()


def check_present_by_default(member):
    current_date = read_data.get_current_date()
    # OPTIMIZE
    return PresentByDefault.objects.filter(
        Q(organization=member.organization)
        & Q(start_date__lte=current_date)
        & Q(end_date__gte=current_date)
        & Q(members__in=[member])
    ).exists()


def mark_attendance(
    member: Member,
    # roster: Roster,
    status: str,
    duration: dt.timedelta = None,
    is_on_leave: bool = False,
    is_holiday: bool = False,
    scans: MemberScan = None,
) -> None:

    current_date = read_data.get_current_date()
    shift = roster.shift
    attendance = Attendance.objects.get_or_create(
        member=member,
        date=current_date,
        duration=duration,
        roster=roster,
        status=status,
    )

    if is_on_leave:
        attendance.status_details = {"leave_type": status}
    if is_holiday:
        attendance.status_details = {"holiday": status}

    # OPTIMIZE
    if scans is not None:
        for scan in scans:
            attendance.scans.add(scan)

    attendance.difference = duration - shift.duration
    if duration > shift.overtime:
        overtime_duration = duration - shift.overtime
        attendance.overtime = overtime_duration

    attendance.save()


def calculate_duration(scans: MemberScan) -> float:

    i = 0
    total_duration = 0
    scans_list = list(scans)

    while i < len(scans_list):

        start_scan, end_scan = scans[i], scans[i + 1]

        duration = start_scan.datetime - end_scan.datetime
        duration = duration.total_seconds() / 3600

        total_duration += duration
        end_scan.save()
        i += 2

    return total_duration


def compute_attendance(
    member: Member,
    # roster: Roster,
    scans: MemberScan,
) -> None:

    current_date = read_data.get_current_datetime().date()
    shift = roster.shift

    # If odd scans, create a scan set at shift's end time
    if scans % 2 != 0:

        current_date_str = str(current_date)
        shift_end_time = shift.end_time
        shift_end_time_str = str(shift_end_time)
        scan_time_str = f"{current_date} {shift_end_time_str}"
        scan_time = create_data.convert_string_to_datetime(
            scan_time_str, format="%Y-%m-%d %H:%M:%S"
        )

        MemberScan.objects.create(
            member=member,
            datetime=scan_time,
            metadata={"message": "Created by system"},
        )
        scans = member.scans.filter(is_computed=False)

    # Calculate duration between scans
    total_duration = calculate_duration(scans)
    return total_duration


@shared_task(name="attendance_task")
def attendance_task():

    current_datetime = read_data.get_current_datetime()
    current_date = current_datetime.date()
    current_time = current_datetime.time()
    logging.info(f"Executing at {current_datetime}")

    orgs = Organization.objects.all()
    for org in orgs:

        # Get shifts whose computation time is now
        lookup = (
            Q(computation_time__hour=current_time.hour)
            & Q(computation_time__minute=current_time.minute)
            & Q(is_active=True)
        )

        # Check if current day is a working day for the shift
        weekday = current_date.weekday()
        lookup &= Q(settings__days__icontains=weekday)

        # If today is a holiday
        holiday = org.holidays.filter(Q(date=current_date) & Q(is_active=True)).first()

        is_holiday = False
        holiday_name = None
        if holiday is not None:
            is_holiday = True
            holiday_name = holiday.name

        shifts = org.shifts.filter(lookup)
        # Get rosters associated with the shifts
        # rosters = Roster.objects.filter(shift__in=shifts)

        # OPTIMIZE
        for roster in rosters:

            # Get members associated with the rosters
            members = org.members.filter(rosters__in=roster)

            for member in members:

                # Get member's scans that are not computed
                scans = member.scans.filter(is_computed=False)

                # If member is on leave
                leave_request = get_current_leave_request(member)
                if leave_request is not None:
                    leave_type_name = leave_request.leave_type.name
                    mark_attendance(
                        member, roster, status=leave_type_name, is_on_leave=True
                    )

                if scans.count() > 0:
                    total_duration = compute_attendance(member, roster, scans)

                    if total_duration >= roster.shift.duration:
                        mark_attendance(member, roster, scans, "present")
                    else:
                        mark_attendance(member, roster, scans, "partial")
                else:
                    if is_holiday:
                        mark_attendance(
                            member, roster, status=holiday_name, is_holiday=True
                        )
                    elif check_present_by_default(member):
                        mark_attendance(member, roster, status="present")
                    else:
                        mark_attendance(member, roster, status="absent")
