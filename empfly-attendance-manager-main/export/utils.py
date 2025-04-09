import json
from typing import List
from attendance.models import Attendance, MemberScan
from utils.date_time import chop_decimal_point, convert_dt_to_another_tz, min_to_hm, NA_or_time
from utils.read_data import round_num

from visitor.models import Visitation, Visitor, VisitorScan
from .models import ExportRequest
from member.models import Member
from django.db.models import Q
import os
import csv
import time
import logging
from django.db.models import QuerySet
from organization.models import Department, Designation, Holiday, SystemLocation
from typing import Union
from django.core.exceptions import ValidationError
from uuid import uuid4

from utils.utils import remove_dt_millie_sec_and_sec, empty_or_data
logger = logging.getLogger(__name__)
from django.db.models.functions import Cast
from django.db.models import TextField
from shift.models import LocationSettings, Shift, ShiftScheduleLog
from datetime import timedelta, datetime
from utils.utils import convert_time_to_formatted_str, convert_string_to_date

def status_bool_to_string(status):
    """Some models status field is bool. In the export csv
    We will not show bool values instead we will user active and inactive.
    """
    return {
        True: "active",
        False: "inactive",
    }.get(status, "")


def string_status_to_bool(status: bool):
    """While doing import csv they send status field. Most of the models have status field.
    That is represented in active/inactive. We want convert to bool if the model status
    field is bool
    """
    return {
        "active": True,
        "inactive": False,
    }.get(status, True)


def get_export_request(member: Member, uuid: uuid4) -> ExportRequest:

    try:
        return ExportRequest.objects.get(uuid=uuid, member=member)
    except (ValidationError, ExportRequest.DoesNotExist) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_export_request"
        )
    return None


def update_export_request(
    export_request: ExportRequest, filename: str
) -> ExportRequest:
    content = json.loads(export_request.content)
    objectType = (
        content.get("object_type", "temp")
        if content.get("object_type", "temp")
        else "temp"
    )

    export_request.status = "completed"
    export_request.link = f"media/{objectType}/csv/{filename}.csv"
    export_request.save()


def extract_data_from_object(
    query_set: QuerySet, lookup: List[str]
) -> Union[str, int, QuerySet]:
    """get specific field from inside the queryset.
    queryset can be any model lookup in the
    relation to that target field
    """
    for field in lookup:
        if not hasattr(query_set, field):
            return "NA"
        query_set = getattr(query_set, field)
    return "NA" if query_set is None else query_set


def get_uuid_from_qs(qs: "Queryset") -> List[str]:
    return list(
        qs.annotate(uuid_as_string=Cast("uuid", TextField())).values_list(
            "uuid_as_string", flat=True
        )
    )

def get_uuid_from_qs_for_fr_image(qs: "Queryset") -> List[str]:
    return list(
        qs.annotate(uuid_as_string=Cast("member__uuid", TextField())).values_list(
            "uuid_as_string", flat=True
        )
    )

def create_export_request(
    member: Member, object_type: str, object_ids: list, filters=None
) -> ExportRequest:

    content = json.dumps({"object_type": object_type, "object_ids": object_ids})

    try:
        is_duplicate = ExportRequest.objects.filter(
            Q(member=member) & Q(content=content) & Q(status="pending")
        ).exists()

        if not is_duplicate:
            export_request = ExportRequest.objects.create(
                member=member, content=content, filter=filters
            )

            # assign task
            # to avoid circular import error
            # added import inside function
            from export.tasks import export_requests_task

            # add task to queue
            export_requests_task.apply_async(
                retry=True,
                retry_policy={
                    "max_retries": 3,
                    "interval_start": 0,
                    "interval_step": 0.2,
                    "interval_max": 0.2,
                },
            )
            return export_request

    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in create_export_request"
        )

    return None


def get_current_time() -> float:
    return time.time()


def generate_file_suffix(export_request: ExportRequest) -> str:
    request_id = export_request.request_id
    current_time = get_current_time()
    return f"{request_id}__{current_time}"


def export_system_location_csv(
    export_request: ExportRequest, location_ids: list
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"system_locations__{file_suffix}"
    if not os.path.exists("media/system_locations/csv/"):
        os.makedirs("media/system_locations/csv/")
    with open(f"media/system_locations/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "UUID",
                "name",
                "description",
                "latitude",
                "longitude",
                "radius",
                "status",
            ]
        )

        system_locations = SystemLocation.objects.filter(uuid__in=location_ids)

        for location in system_locations:

            data = [
                extract_data_from_object(location, ["uuid"]),
                extract_data_from_object(location, ["name"]),
                extract_data_from_object(location, ["description"]),
                extract_data_from_object(location, ["latitude"]),
                extract_data_from_object(location, ["longitude"]),
                extract_data_from_object(location, ["radius"]),
                extract_data_from_object(location, ["status"]),
            ]
            writer.writerow(data)

    return filename


def export_members_csv(export_request: ExportRequest, member_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"members__{file_suffix}"
    if not os.path.exists("media/members/csv/"):
        os.makedirs("media/members/csv/")
    with open(f"media/members/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "UUID",
                "email",
                "phone_number",
                "first_name",
                "last_name",
                "designation",
                "department",
                "org_location",
                "employee_id",
                "manager",
                "role",
                "status",
            ]
        )

        members = Member.objects.filter(uuid__in=member_ids)

        for member in members:

            data = [
                extract_data_from_object(member, ["uuid"]),
                extract_data_from_object(member, ["user", "email"]),
                extract_data_from_object(member, ["user", "phone"]),
                extract_data_from_object(member, ["user", "first_name"]),
                extract_data_from_object(member, ["user", "last_name"]),
                extract_data_from_object(member, ["designation", "name"]),
                extract_data_from_object(member, ["department", "name"]),
                extract_data_from_object(member, ["org_location", "name"]),
                extract_data_from_object(member, ["employee_id"]),
                extract_data_from_object(member, ["manager", "user", "email"]),
                extract_data_from_object(member, ["role", "name"]),
                extract_data_from_object(member, ["status"]),
            ]
            writer.writerow(data)

    return filename

def get_department_head_names(department):
    department_head = department.department_head.all()
    department_head = department_head.values_list("user__username", flat=True)
    department_head = list(department_head)

    if not department_head:
        return ""

    return ", ".join(department_head)

def export_department_csv(export_request: ExportRequest, department_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"departments__{file_suffix}"
    if not os.path.exists("media/departments/csv/"):
        os.makedirs("media/departments/csv/")
    with open(f"media/departments/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(["UUID", "name", "description", "department head", "status"])

        departments = Department.objects.filter(uuid__in=department_ids)

        for department in departments:

            data = [
                extract_data_from_object(department, ["uuid"]),
                extract_data_from_object(department, ["name"]),
                extract_data_from_object(department, ["description"]),
                get_department_head_names(department),
                status_bool_to_string(department.is_active),
            ]
            writer.writerow(data)

    return filename


def export_designation_csv(export_request: ExportRequest, designation_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"designation__{file_suffix}"
    if not os.path.exists("media/designation/csv/"):
        os.makedirs("media/designation/csv/")
    with open(f"media/designation/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "UUID",
                "name",
                "description",
            ]
        )

        designations = Designation.objects.filter(uuid__in=designation_ids)

        for designation in designations:

            data = [
                extract_data_from_object(designation, ["id"]),
                extract_data_from_object(designation, ["name"]),
                extract_data_from_object(designation, ["description"]),
            ]
            writer.writerow(data)

    return filename


def export_visitor_csv(export_request: ExportRequest, visitor_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"visitor__{file_suffix}"
    if not os.path.exists("media/visitor/csv/"):
        os.makedirs("media/visitor/csv/")

    with open(f"media/visitor/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "uuid",
                "first_name",
                "last_name",
                "email",
                "phone number",
                "status",
            ]
        )

        visitors = Visitor.objects.filter(id__in=visitor_ids)

        for visitor in visitors:

            data = [
                extract_data_from_object(visitor, ["uuid"]),
                extract_data_from_object(visitor, ["user", "first_name"]),
                extract_data_from_object(visitor, ["user", "last_name"]),
                extract_data_from_object(visitor, ["user", "email"]),
                extract_data_from_object(visitor, ["user", "phone"]),
                extract_data_from_object(visitor, ["status"]),
            ]
            writer.writerow(data)

    return filename


def get_scans_sys_location(attendance):
    scans = attendance.scans.all().select_related("system_location")
    system_location_names = (
        scans.filter(system_location__isnull=False)
        .values_list("system_location__name", flat=True)
        .distinct()
    )
    system_location_names = list(system_location_names)
    system_location_names = set(system_location_names)
    system_location_names = list(system_location_names)
    locations = "; ".join(system_location_names)
    return locations


def get_check_in_out_time(attendance: Attendance):
    scans = attendance.scans.all()
    check_in, check_out = None, None

    check_in_scan = scans.filter(scan_type="check_in")
    check_out_scan = scans.filter(scan_type="check_out")

    org_tz = attendance.organization.timezone
    print(org_tz)

    if check_in_scan.exists():
        check_in = check_in_scan.order_by("date_time").first()
        print(check_in.date_time)

        check_in_dt = convert_dt_to_another_tz(check_in.date_time, org_tz)
        check_in = check_in_dt.time()

    if check_out_scan.exists():
        check_out = check_out_scan.order_by("date_time").last()
        print(check_out.date_time)

        check_out_dt = convert_dt_to_another_tz(check_out.date_time, org_tz)

        check_out = check_out_dt.time()

    return check_in, check_out


def export_attendance_csv(export_request: ExportRequest, attendance_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"attendance__{file_suffix}"
    if not os.path.exists("media/attendance/csv/"):
        os.makedirs("media/attendance/csv/")

    with open(f"media/attendance/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "first name",
                "last name",

                "username",
                "employee id",

                "visited system locations",
                "shift",

                "department",
                "designation",

                "date",
                "status",

                "duration (H:M)",
                "overtime (H:M)",

                "difference",
                "late check in (H:M)",

                "early check out (H:M)",
                "late check out (H:M)",

                "check in",
                "check out",
            ]
        )

        attendances = Attendance.objects.filter(id__in=attendance_ids)

        for attendance in attendances:

            check_in_time, check_out_time = get_check_in_out_time(attendance)

            data = [
                extract_data_from_object(attendance, ["member", "user", "first_name"]),
                extract_data_from_object(attendance, ["member", "user", "last_name"]),

                extract_data_from_object(attendance, ["member", "user", "username"]),
                extract_data_from_object(attendance, ["member", "employee_id"]),

                get_scans_sys_location(attendance),
                extract_data_from_object(attendance, ["shift", "name"]),

                extract_data_from_object(attendance, ["member", "department", "name"]),
                extract_data_from_object(attendance, ["member", "designation", "name"]),

                extract_data_from_object(attendance, ["date"]),
                extract_data_from_object(attendance, ["status"]),

                NA_or_time(
                    min_to_hm(
                        round_num(
                                extract_data_from_object(attendance, ["duration"])
                        )
                    ),
                ),
                NA_or_time(
                    min_to_hm(
                        round_num(
                            extract_data_from_object(attendance, ["overtime"])
                        )
                    )
                ),

                extract_data_from_object(attendance, ["difference"]),
                NA_or_time(
                    min_to_hm(
                        round_num(
                            extract_data_from_object(attendance, ["late_check_in"])
                        )
                    ),
                ),

                NA_or_time(
                    min_to_hm(
                        round_num(
                            extract_data_from_object(attendance, ["early_check_out"])
                        )
                    )
                ),
                NA_or_time(
                    min_to_hm(
                        round_num(
                            extract_data_from_object(attendance, ["late_check_out"])
                        )
                    )
                ),

                empty_or_data(remove_dt_millie_sec_and_sec(check_in_time)),
                empty_or_data(remove_dt_millie_sec_and_sec(check_out_time)),
            ]
            writer.writerow(data)

    return filename


def export_visitations_csv(export_request: ExportRequest, visitation_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"visitations__{file_suffix}"
    if not os.path.exists("media/visitations/csv/"):
        os.makedirs("media/visitations/csv/")

    with open(f"media/visitations/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Name",
                "Visitor",
                "Host",
                "Date",
                "Start Time",
                "End Time",
                "Host Status",
                "Visitor Status",
                "Visitation Status",
                "Org location",
            ]
        )

        visitations = Visitation.objects.filter(id__in=visitation_ids)

        for visitation in visitations:

            data = [
                extract_data_from_object(visitation, ["name"]),
                extract_data_from_object(visitation, ["visitor", "user", "username"]),
                extract_data_from_object(visitation, ["host", "user", "username"]),
                extract_data_from_object(visitation, ["visitation_date"]),
                extract_data_from_object(visitation, ["start_time"]),
                extract_data_from_object(visitation, ["end_time"]),
                extract_data_from_object(visitation, ["host_status"]),
                extract_data_from_object(visitation, ["visitor_status"]),
                extract_data_from_object(visitation, ["visitation_status"]),
                extract_data_from_object(visitation, ["org_location", "name"]),
            ]
            writer.writerow(data)

    return filename


def export_visitation_register_csv(
    export_request: ExportRequest, visitation_register_ids: list
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"visitation_register__{file_suffix}"
    if not os.path.exists("media/visitation_register/csv/"):
        os.makedirs("media/visitation_register/csv/")

    with open(f"media/visitation_register/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Visitor Username",
                "Host Username",
                "Visitation",
                "Date",
                "Time",
                "Location",
                "kiosk",
            ]
        )

        visitation_registers = VisitorScan.objects.filter(
            id__in=visitation_register_ids
        )

        for visitation_register in visitation_registers:

            data = [
                extract_data_from_object(
                    visitation_register, ["visitor", "user", "username"]
                ),
                extract_data_from_object(
                    visitation_register, ["visitation", "host", "user", "username"]
                ),
                extract_data_from_object(visitation_register, ["visitation", "name"]),
                extract_data_from_object(visitation_register, ["date"]),
                extract_data_from_object(visitation_register, ["time"]),
                extract_data_from_object(visitation_register, ["location"]),
                extract_data_from_object(visitation_register, ["kiosk", "kiosk_name"]),
            ]
            writer.writerow(data)

    return filename


def google_map_url(latitude, longitude):
    print(latitude, longitude, "!!!!!!!!!!!!!!!!!!!!!!!!!")

    if latitude in ("NA", None) or longitude in ("NA", None):
        return "NA"

    return f"https://maps.google.com/?q={latitude},{longitude}"


def format_scan_type(scan_type: str):
    print(scan_type)
    scan_types = {
        "check_in": "Check In",
        "check_out": "Check Out",
    }

    return scan_types.get(scan_type, "NA")


def export_attendance_register_csv(
    export_request: ExportRequest, attendance_register_ids: list
) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"attendance_register__{file_suffix}"
    if not os.path.exists("media/attendance_register/csv/"):
        os.makedirs("media/attendance_register/csv/")

    with open(f"media/attendance_register/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "First Name",
                "Last Name",
                "Username",
                "Employee id",
                "Scan Date and Time",
                "Visited System Locations",
                "Scan Type",
                "Scan Location",
                "Kiosk",
                # "Department",
                # "Designation",
            ]
        )

        attendance_registers = MemberScan.objects.filter(id__in=attendance_register_ids)

        for attendance_register in attendance_registers:

            org_tz = attendance_register.organization.timezone

            data = [
                extract_data_from_object(
                    attendance_register, ["member", "user", "first_name"]
                ),
                extract_data_from_object(
                    attendance_register, ["member", "user", "last_name"]
                ),
                extract_data_from_object(
                    attendance_register, ["member", "user", "username"]
                ),
                extract_data_from_object(
                    attendance_register, ["member", "employee_id"]
                ),
                remove_dt_millie_sec_and_sec(
                    convert_dt_to_another_tz(
                        extract_data_from_object(attendance_register, ["date_time"]), org_tz
                    )
                ),
                extract_data_from_object(
                    attendance_register, ["system_location", "name"]
                ),
                format_scan_type(
                    extract_data_from_object(attendance_register, ["scan_type"])
                ),
                google_map_url(
                    latitude=extract_data_from_object(
                        attendance_register, ["latitude"]
                    ),
                    longitude=extract_data_from_object(
                        attendance_register, ["longitude"]
                    ),
                ),
                extract_data_from_object(attendance_register, ["kiosk", "kiosk_name"]),
                # extract_data_from_object(attendance_register, ["member", "department", "name"]),
                # extract_data_from_object(attendance_register, ["member", "designation", "name"]),
            ]
            writer.writerow(data)

    return filename


def get_system_loc_names(system_location: SystemLocation):
    print(system_location, "??????????????????????????????????????????/")
    uniq_locations = list(system_location.values_list("name", flat=True))
    print(uniq_locations)
    return "; ".join(uniq_locations)


def get_managers_names(managers: Member):
    print(managers, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    uniq_manager_names = list(managers.values_list("user__username", flat=True))
    print(uniq_manager_names, "######################")
    return "; ".join(uniq_manager_names)


# def export_cluster_csv(export_request: ExportRequest, cluster_ids: list) -> csv:

#     file_suffix = generate_file_suffix(export_request)
#     filename = f"cluster__{file_suffix}"
#     if not os.path.exists("media/cluster/csv/"):
#         os.makedirs("media/cluster/csv/")

#     with open(f"media/cluster/csv/{filename}.csv", "w") as f:
#         writer = csv.writer(f)
#         writer.writerow(
#             [
#                 "UUID",
#                 "name",
#                 "description",
#                 "system locations",
#                 "managers",
#                 "status",
#             ]
#         )

#         clusters = Cluster.objects.filter(uuid__in=cluster_ids)

#         for cluster in clusters:

#             data = [
#                 cluster.uuid,
#                 extract_data_from_object(cluster, ["name"]),
#                 extract_data_from_object(cluster, ["description"]),
#                 get_system_loc_names(cluster.locations.all()),
#                 get_managers_names(cluster.managers.all()),
#                 extract_data_from_object(cluster, ["status"]),
#             ]
#             writer.writerow(data)

#     return filename


def export_holidays_csv(export_request: ExportRequest, holidays_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"holidays__{file_suffix}"
    if not os.path.exists("media/holidays/csv/"):
        os.makedirs("media/holidays/csv/")

    with open(f"media/holidays/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "uuid",
                "Name",
                "Description",
                "Date",
                "Org Location",
            ]
        )

        holidays = Holiday.objects.filter(uuid__in=holidays_ids)

        for holiday in holidays:

            data = [
                holiday.uuid,
                extract_data_from_object(holiday, ["name"]),
                extract_data_from_object(holiday, ["description"]),
                extract_data_from_object(holiday, ["date"]),
                extract_data_from_object(holiday, ["org_location", "name"]),
            ]
            writer.writerow(data)

    return filename

def get_user_full_name(user):
    full_name = ""
    first_name = user.first_name
    last_name = user.last_name

    if first_name:
        full_name += first_name

    if last_name:
        full_name += f" {last_name}"

    return full_name

def export_fr_image_csv(export_request: ExportRequest, member_ids: list) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"fr_image__{file_suffix}"
    if not os.path.exists("media/fr_image/csv/"):
        os.makedirs("media/fr_image/csv/")

    with open(f"media/fr_image/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Name",
                "Email",
                "status",
                "FR images count",
            ]
        )

        fr_images = Member.objects.filter(uuid__in=member_ids)

        for member in fr_images:
            member_fr_images_count: int = member.member_images.all().count()

            data = [
                empty_or_data(get_user_full_name(member.user)),
                empty_or_data(extract_data_from_object(member, ["user", "email"])),
                extract_data_from_object(member, ["status"]),
                member_fr_images_count,
            ]
            writer.writerow(data)

    return filename


def export_shift_calendar_csv(export_request: ExportRequest, member_ids: list, filters) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"shift_calendar__{file_suffix}"
    if not os.path.exists("media/shift_calendar/csv/"):
        os.makedirs("media/shift_calendar/csv/")

    with open(f"media/shift_calendar/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)

        members = Member.objects.filter(uuid__in=member_ids)

        ssl = ShiftScheduleLog.objects.filter(employee__uuid__in=member_ids, status="active")

        shift_start_date = filters.get("shift_start_date")
        shift_end_date = filters.get("shift_end_date")

        shift_start_date = datetime.strptime(shift_start_date, "%Y-%m-%d")
        shift_end_date = datetime.strptime(shift_end_date, "%Y-%m-%d")

        shift_dates = []
        diff_days = (shift_end_date - shift_start_date).days + 1

        csv_heading = ["Employee"]

        for day in range(diff_days):
            shift_dt_obj = (shift_start_date + timedelta(days=day)).date()
            shift_dates.append(shift_dt_obj)

            date = datetime.strptime(str(shift_dt_obj), "%Y-%m-%d")
            formatted_date = date.strftime("%b %d (%a)")
            csv_heading.append(formatted_date)

        # Heading
        writer.writerow(
            csv_heading
        )

        for member in members:
            data = [
                member.user.email
            ]

            member_ssl = ssl.filter(employee=member)

            for shift_date in shift_dates:

                try:
                    member_shift_date_ssl = member_ssl.get(
                        Q(
                            start_date__lte=shift_date,
                            end_date__gte=shift_date,
                        )
                        | Q(start_date__lte=shift_date, end_date__isnull=True),
                    )
                except ShiftScheduleLog.DoesNotExist:
                    member_shift_date_ssl = None
                except Exception as err:
                    print(err)
                    member_shift_date_ssl = None

                if not member_shift_date_ssl:
                    data.append("")
                    continue

                system_location_name = None
                shift = member_shift_date_ssl.shift
                shift_name, system_location_str = shift.name, ""

                cell_data = f"Shift Name: {shift_name}"

                location_settings = member_shift_date_ssl.location_settings.filter(
                    Q(
                        applicable_start_date__lte=shift_date,
                        applicable_end_date__gte=shift_date,
                    )
                    | Q(
                        applicable_start_date__lte=shift_date,
                        applicable_end_date__isnull=True
                    ),
                ).order_by("start_time")

                if not location_settings.exists():
                    system_location = shift.default_location
                    system_location_name = system_location.name if system_location else None

                    shift_start_time = shift.start_time
                    shift_end_time = shift.end_time

                    if system_location_name:
                        system_location_str += f"{system_location_name} ({convert_time_to_formatted_str(shift_start_time)} - {convert_time_to_formatted_str(shift_end_time)})"

                else:
                    system_locations_data_for_member = []
                    for location_setting in location_settings:
                        system_location = location_setting.system_location
                        system_location_name = system_location.name
                        location_settings_start_time = location_setting.start_time
                        location_settings_end_time = location_setting.end_time


                        system_locations_data_for_member.append(
                            f"{system_location_name} ({convert_time_to_formatted_str(location_settings_start_time)} - {convert_time_to_formatted_str(location_settings_end_time)})"
                        )

                    system_location_str = " && ".join(system_locations_data_for_member)

                if system_location_str:
                    cell_data += f", System Locations: {system_location_str}"

                data.append(cell_data)

            writer.writerow(data)

    return filename


def member_curr_day_attendance_status_csv(export_request: ExportRequest, member_ids: list, filters) -> csv:

    file_suffix = generate_file_suffix(export_request)
    filename = f"member_curr_day_attendance_status__{file_suffix}"
    if not os.path.exists("media/member_curr_day_attendance_status/csv/"):
        os.makedirs("media/member_curr_day_attendance_status/csv/")

    with open(f"media/member_curr_day_attendance_status/csv/{filename}.csv", "w") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Full Name",
                "Email",
                "Department",
                "Designation",
                "Org Location",
                "Role",
                "Status ( Check In / Check Out / Yet To Check In )",
            ]
        )


        filter_date = filters.get("date")
        filter_date, _ = convert_string_to_date(filter_date)

        members = Member.objects.filter(uuid__in=member_ids)
        members_day_scans = MemberScan.objects.filter(
            date_time__date=filter_date,
            member__status="active",
            status="pending",
            is_computed=False,
            organization=export_request.member.organization
        )

        for member in members:
            member_scan = members_day_scans.filter(member=member)
            if not member_scan.exists():
                check_in_status = "Yet To Check In"
            else:
                last_scan = member_scan.order_by("date_time").last()
                if last_scan.scan_type == "check_in":
                    check_in_status = "Check In"
                elif last_scan.scan_type == "check_out":
                    check_in_status = "Check Out"

            data = [
                empty_or_data(get_user_full_name(member.user)),
                empty_or_data(extract_data_from_object(member, ["user", "email"])),
                empty_or_data(extract_data_from_object(member, ["department", "name"])),
                empty_or_data(extract_data_from_object(member, ["designation", "name"])),
                empty_or_data(extract_data_from_object(member, ["org_location", "name"])),
                empty_or_data(extract_data_from_object(member, ["role", "name"])),
                check_in_status
            ]
            writer.writerow(data)

    return filename
