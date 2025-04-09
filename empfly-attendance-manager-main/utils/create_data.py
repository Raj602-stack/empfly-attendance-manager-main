from typing import Tuple
from django.core.exceptions import ValidationError
from django.contrib.auth import logout
from django.db import IntegrityError
from django.utils import crypto
from django.db.models import Q
from django.http import HttpResponse
import pytz
from account.models import User
from member.models import Member, Profile
from organization.models import Department, Designation, Organization, OrgLocation, Role
from organization.utils import get_member_role
import pandas as pd

# from shift.models import Shift
from django.db.models.functions import Lower
from shift.models import Shift, ShiftScheduleLog
from datetime import date

from utils import fetch_data

from six import text_type
import datetime as dt
import secrets
import time
import logging
import uuid
from utils import date_time

logger = logging.getLogger(__name__)

from utils.date_time import curr_dt_with_org_tz

def generate_token(length: int = 8) -> str:
    token = secrets.token_hex(length)
    return token[:length]


def generate_random_string(length: int = 6) -> str:
    return crypto.get_random_string(length)


def generate_hash_value(user: User) -> str:

    timestamp = time.time()
    return text_type(user.uid) + text_type(timestamp) + text_type(user.email)


def create_organization(
    name: str,
) -> Organization:

    unique = False
    while unique is False:
        domain = generate_random_string(12)
        try:
            org = Organization.objects.create(name=name, domain=domain)
        except (IntegrityError) as e:
            logger.error(e)
        except Exception as e:
            logger.exception(
                f"Add exception for {e.__class__.__name__} in"
                "UserRegistrationAPIView > creating organization"
            )
            logger.error(e)

        unique = True

    return org


def create_org_loc(name: str, org: Organization):
    return OrgLocation.objects.create(name=name, organization=org)


# TODO deprecated
def create_default_shift(org):

    time_z = pytz.timezone(org.timezone)

    start_time = dt.datetime(2023, 2, 13, 10, 00, 00, tzinfo=time_z).time()
    end_time = dt.datetime(2023, 2, 13, 18, 00, 00, tzinfo=time_z)
    computation_time = (end_time + dt.timedelta(hours=1)).time()

    return Shift.objects.create(
        name="Default Shift",
        start_time=start_time,
        end_time=end_time.time(),
        computation_time=computation_time,
        organization=org,
        enable_geo_fencing=False,
    )

# TODO deprecated
def create_member(org: Organization, user: User, role: Role = None) -> Member:

    if role is None:
        role = get_member_role()

    member = Member.objects.filter(Q(organization=org) & Q(user=user))
    if member.exists():
        logger.warning(f"Member for {user} already exists in {org}")
        return member.first()

    if role.name not in ("admin", "hr", "member"):
        raise ValidationError("Role must be in Admin/Hr/Member.")

    member = Member.objects.create(organization=org, user=user, role=role)
    try:
        Profile.objects.create(member=member)
    except IntegrityError as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in create_member")

    return member


def convert_string_to_datetime(string: str, format: str = "%Y-%m-%d") -> dt.datetime:
    try:
        return dt.datetime.strptime(string, format)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in convert_string_to_datetime"
        )
    return None


def create_pandas_dataframe(csv_file) -> pd.DataFrame:

    try:
        df = pd.read_csv(csv_file, encoding="ISO-8859-1")
        df = df.where(pd.notnull(df), None)
        # Replaces nan values with empty string
        df = df.fillna("")
        return df
    except UnicodeDecodeError as e:
        logger.error(e)
        return None
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in create_pandas_dataframe"
        )
        return None


def validate_and_save_user(
    all_users: User,
    user: User,
    email: str = "",
    phone: str = "",
    first_name: str = "",
    last_name: str = "",
    is_bulk_update: bool = False,
):
    """validate user object"""

    is_stripped = False
    if isinstance(email, str):
        is_stripped = True

        email = email.lower().strip()

    if (
        email
        and email not in ("", "NA")
        and is_stripped
        and isinstance(email, str)
        and (not all_users.filter(email=email).exists())
    ):
        user.email = email.strip()

    if not phone or phone in ("", "NA"):
        user.phone = None
    elif phone and phone.isdigit() and not all_users.filter(phone=phone).exists():
        user.phone = phone

    if not first_name or first_name in ("", "NA"):
        user.first_name = None
    else:
        user.first_name = first_name

    if not last_name or last_name in ("", "NA"):
        user.last_name = None
    else:
        user.last_name = last_name
    user.save()


def modify_member_model_data(
    filter_ins: "Object",
    member: Member,
    Modal: "Modal_Object",
    organization: Organization,
    name="",
    curr_val: str = "",
    field_name: str = "",
    bulk_update: bool = False,
):
    name_is_valid = True
    is_bulk_upload_have_obj = False
    if name and isinstance(name, str) and name.strip() and name != "NA":
        # print(name, "is valid")
        obj = filter_ins.filter(name=name.strip())
        # print(obj, "obj===")
        if obj.exists():
            obj = obj.first()
            is_bulk_upload_have_obj = True
        elif bulk_update:
            obj = None
        elif not bulk_update:
            obj = Modal.objects.create(name=name, organization=organization)
        # print(obj)
    else:
        name_is_valid = False
        obj = None

    # print(obj)

    logger.error(
        f"name = {name}, obj = {obj}, curr_val ={curr_val}, field_name = {field_name}, bulk_update={bulk_update}"
    )

    if field_name == "department":
        if obj:
            member.department = obj
        elif bulk_update and not is_bulk_upload_have_obj and name:
            pass
        elif name in ("", "NA"):
            member.department = None

    elif field_name == "designation":
        if obj:
            member.designation = obj
        elif bulk_update and not is_bulk_upload_have_obj and name:
            pass
        elif name in ("", "NA"):
            member.designation = None
    

    elif field_name == "org_location":
        if obj:
            member.org_location = obj
        elif bulk_update and not is_bulk_upload_have_obj and name:
            pass
        elif name in ("", "NA"):
            member.org_location = None


def create_csv_response(file_name: str) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    file_name = f"{file_name}__{time.time()}"
    response["Content-Disposition"] = f'attachment; filename="{file_name}.csv"'
    return response


def get_user_name(user: User):
    """ Get the full name or username from User obj
    """
    if user.first_name and user.last_name:
        user_name = user.first_name + " " + user.last_name
    elif user.first_name:
        user_name = user.first_name
    elif user.last_name:
        user_name = user.last_name
    else:
        # user_name = user.email
        user_name = ""
    return user_name


def create_user(email: str, first_name: str) -> Tuple[User, bool]:
    """ Create User obj
    """
    # Lower all the email.
    email = email.lower().strip()

    try:
        # Check user is exists or not
        user = User.objects.get(email__iexact=email)
        user_created = False
    except User.DoesNotExist:
        # create user. User email doestn't exists.
        user = User.objects.create(email=email, first_name=first_name)
        user_created = True

    return user, user_created


def initial_employee_log(member: Member) -> ShiftScheduleLog:
    """ When employee is created Create shift schedule log for employees using org default shift.
    """
    org = member.organization

    # Employee already have SSL. This function only user when employee is creating.
    if ShiftScheduleLog.objects.filter(employee=member, organization=org).exists():
        logger.warning(f"{member.user.email} already have shift schedule log in this {org}")
        return

    shift = org.default_shift
    return ShiftScheduleLog.objects.create(
        employee=member, start_date=curr_dt_with_org_tz().date(), shift=shift, organization=org
    )


def add_first_and_last_check_in(attendance_report):
    """Add first check in and last check in into attendance report data"""
    for report in attendance_report:
        scans = report.get("scans", {})

        check_in_dt = []
        check_out_dt = []

        for scan in scans:
            scan_type = scan.get("scan_type")
            scan_dt = scan.get("date_time")

            if scan_type == "check_in":
                check_in_dt.append(scan_dt)
            elif scan_type == "check_out":
                check_out_dt.append(scan_dt)

        first_check_in_dt = None
        last_check_out_dt = None

        print(check_in_dt)
        print(check_out_dt)
        print("############################################")

        if check_in_dt:
            first_check_in_dt = min(check_in_dt)
        if check_out_dt:
            last_check_out_dt = max(check_out_dt)

        report["first_check_in_dt"] = first_check_in_dt
        report["last_check_out_dt"] = last_check_out_dt

    return attendance_report
