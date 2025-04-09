from datetime import datetime, timedelta
from account.models import User
from export.utils import extract_data_from_object
from member.models import Member
from organization.models import Organization
from shift.shift_schedule_logic import create_log_for_shift
from utils import create_data, date_time
from utils.create_data import get_user_name
from utils.email_funcs import (
    send_bulk_visitation_update_email,
    send_visitation_request_mail,
)
from django.db.models.query import QuerySet
from collections.abc import Iterable
from visitor.models import Visitation
from shift.models import Shift, ShiftScheduleLog
from django.db.models import Q
from datetime import date


import logging

# configure logging
logging.basicConfig(
    filename="logs/shift_utils.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)

def check_model_is_active(model_name, model_ins):
    """ For check department, designation and org_location models ins
        active or not.
    """

    print(f"model_name : {model_name}, model_ins : {model_ins}")
    if model_name == "department":
        return model_ins.is_active
    elif model_name == "designation":
        return model_ins.is_active
    elif model_name == "org_location":
        return model_ins.status == "active"

def assign_shift(members, lookup):
    """ Assign shift to member using priorty anaysisc.
    """

    # If member got assigned by a shift they can remove the filtering.
    exclude_ids = []

    for employee in members:
        # Get shift
        shift = extract_data_from_object(employee, lookup)

        # Get Department, Designation, Org Location and check obj status. If inactive this will skip.
        model_ins = extract_data_from_object(employee, [lookup[0]])
        is_model_active = check_model_is_active(model_name=lookup[0], model_ins=model_ins)

        if is_model_active and isinstance(shift, Shift) and shift.status == "active":
            # Member got assigned the shift.
            exclude_ids.append(employee.id)

            # starting the shift log logic
            create_log_for_shift(shift, employee)

    members = members.exclude(id__in=exclude_ids)
    return members


def assign_shift_to_one_object(members, lookup):
    """ Assign shift to a single member.
    """
    shift = extract_data_from_object(members, lookup)
    is_found = False
    if isinstance(shift, Shift) and shift.status == "active":
        members.save()
        is_found = True
    return members, is_found


def assign_applicable_shift(employees: Member, org: Organization) -> Member:
    """ Assign shift to members. With applicability settings. This settings saved in org model.
        Higher priority models shift will assign.
    """

    print(employees)

    is_iterable = False
    if isinstance(employees, Iterable):
        is_iterable = True

    arr = [0, 0, 0]
    priorities = org.settings["applicability_settings_priority"]

    # Get the priority and assign in right position. Higher priority assign in the first place of array.
    for priority in priorities:
        position = priority["priority"]
        print(position)
        arr[position - 1] = priority["name"]


    # Lookup in the field
    get_priority = {
        "department": ["department", "shift"],
        "designation": ["designation", "shift"],
        "org_location": ["org_location", "shift"],
    }

    # We will get each employee and check whether they have the model ins. if not
    # they will not assign shift if they have any shift in according to priority
    # they will get assing.
    for value in arr:
        lookup = get_priority.get(value)


        if is_iterable:
            employees = assign_shift(employees, lookup)
            if employees.count() == 0:
                break
        elif is_iterable is False:
            employees, is_found = assign_shift_to_one_object(employees, lookup)
            if is_found is True:
                break

    return employees


def get_affected_employees(
    members: Member,
    department: list = None,
    designation: list = None,
    org_location: list = None,
) -> Member:
    """ Filter employees match with department, designation and org location.
    """

    if department:
        members = members.filter(department__uuid__in=department)
    if designation:
        members = members.filter(designation__uuid__in=designation)
    if org_location:
        members = members.filter(org_location__uuid__in=org_location)

    return members


def send_visitation_email_on_update(
    visitation: Visitation, req_user: User, role: str = None
):
    """ Send visitation request email and accept and decline email to visitor and host
    """

    if (
        visitation.visitation_status == "scheduled"
        and visitation.visitor_status == "accepted"
        and visitation.host_status == "accepted"
    ):
        # visitation is scheduled. sent update email to host and visitor
        email_content = [
            {
                "to": visitation.host.user,
                "visitation": visitation,
                "message": "Visitation is scheduled",
            },
            {
                "to": visitation.visitor.user,
                "visitation": visitation,
                "message": "Visitation is scheduled",
            },
        ]
        send_bulk_visitation_update_email(email_content)

    elif (
        visitation.visitation_status == "created"
        and visitation.visitor_status == "pending"
        and visitation.host_status == "pending"
    ):
        # admin is created visitation. First Host confirmation is required.
        user = visitation.host.user
        user_name = create_data.get_user_name(req_user)
        message = f"{user_name} sent you a Visitation Request"
        email_content = {"to": user, "visitation": visitation, "message": message}
        send_visitation_request_mail(email_content)

    elif (
        visitation.visitation_status == "created"
        and visitation.visitor_status == "pending"
        and visitation.host_status == "accepted"
    ):
        # Host accepted visitation. visitor conf is required. send email to visitor
        user = visitation.visitor.user
        user_name = create_data.get_user_name(visitation.host.user)

        message = f"{user_name} sent you a Visitation Request"
        email_content = {"to": user, "visitation": visitation, "message": message}
        send_visitation_request_mail(email_content)

    elif (
        visitation.visitation_status == "created"
        and visitation.visitor_status == "accepted"
        and visitation.host_status == "pending"
    ):
        # send email to Host. Visitor accepted.
        user = visitation.host.user
        user_name = create_data.get_user_name(visitation.visitor.user)

        message = f"{user_name} sent you a Visitation Request"
        email_content = {"to": user, "visitation": visitation, "message": message}
        send_visitation_request_mail(email_content)

    elif (
        visitation.visitation_status == "cancelled"
        and visitation.visitor_status == "accepted"
        and visitation.host_status == "rejected"
    ):
        # send email to visitor. Host rejected request.
        email_content = [
            {
                "to": visitation.visitor.user,
                "visitation": visitation,
                "message": "Your Visitation is declined by host",
            },
        ]
        send_bulk_visitation_update_email(email_content)

    elif (
        visitation.visitation_status == "cancelled"
        and visitation.visitor_status == "rejected"
        and visitation.host_status == "accepted"
    ):
        # send email to Host. Visitor rejected.
        email_content = [
            {
                "to": visitation.host.user,
                "visitation": visitation,
                "message": "Visitation is declined by visitor",
            },
        ]
        send_bulk_visitation_update_email(email_content)

    elif (
        visitation.visitation_status == "cancelled"
        and visitation.visitor_status == "pending"
        and visitation.host_status == "pending"
    ):
        # send email to Host. Admin cancelled the visitation.
        name = role if role else get_user_name(req_user)
        email_content = [
            {
                "to": visitation.host.user,
                "visitation": visitation,
                "message": f"Visitation is declined by {name}",
            },
        ]
        send_bulk_visitation_update_email(email_content)


def notify_on_visitation_update(visitation: Visitation, req_user: User) -> None:
    """Notify only if the some one update the visitation"""

    email_content = None
    user_name = get_user_name(req_user)
    if visitation.host_status == "pending" and visitation.visitor_status == "pending":
        email_content = [
            {
                "to": visitation.host.user,
                "visitation": visitation,
                "message": f"{user_name} updated your visitation",
            },
        ]
    else:
        email_content = [
            {
                "to": visitation.visitor.user,
                "visitation": visitation,
                "message": f"{user_name} updated your visitation",
            },
            {
                "to": visitation.host.user,
                "visitation": visitation,
                "message": f"{user_name} updated your visitation",
            },
        ]

    if email_content:
        send_bulk_visitation_update_email(email_content)


def find_ids_effected(logs, head_id, tail_id):
    """ Find ids become inactive. For SSL a new ssl
        replace old ssl old ssl become inactive.
    """
    is_found = False
    effected_ids = []

    for i in logs:
        if i.id == head_id:
            is_found = True

        if is_found is True:
            effected_ids.append(i.id)

        if i.id == tail_id:
            break
    return effected_ids


def curr_shift_schedule_log(member: Member, d_t: datetime, org: Organization):
    """ Get user current shift.
        Log can be yesterday, today, tomorrow
        If logs computation time is passed we will go for other ssl
        # Flow = yesterday_log -> today_log -> tomorrow_log
    """

    logging.info(" ")
    logging.info(
        " ============ curr_shift_schedule_log function started working ==========="
    )
    logging.info(f"datetime : {d_t}")

    today_date = d_t.date()
    curr_time = d_t.time()
    yesterday_date = today_date - timedelta(days=1)
    tomorrow_date = today_date + timedelta(days=1)

    logging.info(f"yesterday_date : {yesterday_date}")
    logging.info(f"today_date : {today_date}")
    logging.info(f"tomorrow_date : {tomorrow_date}")

    logs = ShiftScheduleLog.objects.filter(
        status="active", employee=member, organization=org
    )

    try:
        yesterday_log = logs.get(
            Q(
                start_date__lte=yesterday_date,
                end_date__gte=yesterday_date,
            )
            | Q(start_date__lte=yesterday_date, end_date__isnull=True)
        )
    except ShiftScheduleLog.DoesNotExist:
        yesterday_log = None

    try:
        today_log = logs.get(
            Q(
                start_date__lte=today_date,
                end_date__gte=today_date,
            )
            | Q(start_date__lte=today_date, end_date__isnull=True),
        )
    except ShiftScheduleLog.DoesNotExist:
        today_log = None

    try:
        tomorrow_log = logs.get(
            Q(
                start_date__lte=tomorrow_date,
                end_date__gte=tomorrow_date,
            )
            | Q(start_date__lte=tomorrow_date, end_date__isnull=True),
        )
    except ShiftScheduleLog.DoesNotExist:
        tomorrow_log = None

    logging.info(f"yesterday_log : {yesterday_log}")
    logging.info(f"today_log : {today_log}")
    logging.info(f"tomorrow_log : {tomorrow_log}")

    if (
        (yesterday_log is not None)
        and (yesterday_log.shift.start_time > yesterday_log.shift.computation_time)
        and (curr_time >= date_time.day_start_time)
        and (curr_time <= yesterday_log.shift.computation_time)
    ):
        logging.info(
            "=============== Yesteray log is not ended. yesterday night shift founded =============="
        )
        employee_log = yesterday_log
        location_settings_date = yesterday_date

    elif (
        (today_log)
        and (today_log.shift.start_time >= today_log.shift.computation_time)
        or (
            today_log.shift.start_time <= today_log.shift.computation_time
            and curr_time <= today_log.shift.computation_time
        )
    ):  # Computation time cannot be passed
        logging.info("=========== Today log =============")
        employee_log = today_log
        location_settings_date = today_date

    elif (
        today_log.shift.start_time <= today_log.shift.computation_time
        and curr_time > today_log.shift.computation_time
    ):  # today log Computation time is passed
        logging.info("========= tomorrow log =========")
        employee_log = tomorrow_log
        location_settings_date = tomorrow_date

    logging.info("")
    logging.info(f"Applicable employee_log : {employee_log}")
    logging.info(f"SHIFT : {employee_log.shift}")
    logging.info("")

    location_settings = employee_log.location_settings.all().filter(
        Q(
            applicable_start_date__lte=location_settings_date,
            applicable_end_date__gte=location_settings_date,
        )
        | Q(
            applicable_start_date__lte=location_settings_date,
            applicable_end_date__isnull=True,
        )
    )

    logging.info(f"Location settings Date : {location_settings_date}")
    logging.info(f"Location settings : {location_settings}")
    logging.info("=========================================== Funtion ended ===========================================")

    return employee_log, location_settings, location_settings_date
