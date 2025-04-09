import datetime as dt
import math, random
from typing import Tuple, Union
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
import base64
from account.models import User
from organization.models import Organization
from utils.response import HTTP_400
from django.db.models.functions import Lower
from member.models import Member
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
import logging
from dateutil import parser
from member.constants import MEMBER_MAX_IMAGE_COUNT
from core.settings import APPLICATION_NAME
from django.db.models import Q

logger = logging.getLogger(__name__)


def pagination(queryset: "Queryset", request) -> Paginator:
    """ page_obj, num_pages, page =

        Send any queryset to this function and request. Request contains
        per_page and page according to that paginate the response.
    """
    per_page = request.GET.get("per_page", 10)
    page = request.GET.get("page", 1)
    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page)
    return page_obj, paginator.num_pages, page


def base64_to_contentfile(image: str) -> ContentFile:
    """ Convert base 64 string to image
    """
    try:
        # Split the string into file format and image string
        format, imgstr = image.split(";base64,")
        # Get file extension
        ext = format.split("/")[-1]
        # Decoding the base64 encoded text and
        # converting it into a ContentFile
        return ContentFile(base64.b64decode(imgstr), name="temp." + ext)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception in base64_to_contentfile")
        return HTTP_400({}, {"message": "Invalid image"})


def generateOTP() -> str:
    """ Generate random 4 digit otp for visitor email verification.
    """
    digits = "0123456789"
    OTP = ""
    for i in range(4):
        OTP += digits[math.floor(random.random() * 10)]
    return OTP


def convert_to_time(
    time: str, time_format: str = "%H:%M:%S"
) -> Tuple[Union[dt.datetime, None], bool]:
    """ return:  valid_time, is_valid =
        Covert string to time.
    """
    if time.count(":") == 1:
        # if string have 1 ':' means %H:%M only required.
        time_format = "%H:%M"

    try:
        validtime = dt.datetime.strptime(time, time_format).time()
        return validtime, True
    except ValueError:
        return None, False


def convert_to_date(date: str) -> Tuple[Union[dt.datetime, None], bool]:
    """ return: valid_date, is_valid
        string date to date time
    """
    try:
        valid_date = dt.datetime.fromisoformat(date).date()
        return valid_date, True
    except ValueError:
        return None, False


def is_user_email_exists(email: str) -> Union[User, None]:
    """ Check user email exists in user model
    """

    # Lower email and strip space. All email are lowered in user model.
    email = email.lower().strip()

    try:
        return User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return None


def filter_qs_by_status(
    request, qs, default: Union[bool, str], choice: tuple
) -> "Queryset":
    """ Get active and inactive datas.
    """
    status = request.GET.get("status", default)
    if status in choice:
        return qs.filter(status=status)
    return qs


def filter_qs_by_is_active(
    request, qs, choice: tuple, default: bool = True
) -> "Queryset":
    """ Get active and inactive datas.
    """

    status = request.GET.get("status", "active")

    status = {"active": True, "inactive": False}.get(status)
    print(status, "@@@@@@@@@")

    if status in choice:
        return qs.filter(is_active=status)
    return qs


def is_member_inactive(member: Member) -> bool:
    """
    if is_member_inactive(member) is True:
        return HTTP_400({} , {"message": "Member is Inactive."})
    """
    return member.status == "inactive"


# def models_filter_by_status(qs: "Queryset", field_name:str, selected_status) -> "Queryset":
#     if not hasattr(qs, field_name):
#         raise ValueError(f"Qs Does't have no field called {field_name}.")
    
#     field = hasattr(qs, field_name)

#     if isinstance(field, str):
#         if selected_status in ("active", "inactive"):
#             return qs.filter({
#                 field_name: selected_status
#             })
#     elif isinstance(field, bool):
#         if selected_status
#         if selected_status in (True, False):
#             return qs.filter({
#                 field_name: selected_status
#             })
#     else:
#         raise ValueError("models_filter_by_status Function Doest Found any status in model")



def is_allowed_to_add_members(org: Organization) -> bool:
    """ Org have limit to add member. Using identify the count is passed.
    """
    print("%%%%%%%%%%%%%%%%%%%%%"*5)
    member_limit = org.limit.get("member")
    print(member_limit)
    all_org_member = org.members.all()
    all_org_active_member = all_org_member.filter(status="active")
    if member_limit != 0 and all_org_active_member.count() >= member_limit:
        return False
    return True


def create_email_content(org: Organization, email) -> dict:
    return {
        "org_name": org.name,
        "users_allowed_limit": org.limit.get("member"),
        "email": email,
        "domain": settings.UI_DOMAIN_URL
    }


def send_limit_exceeded_notification(org: Organization, user) -> bool:

    subject = f"AVL Users Limit Exceeded for {org.name} | Empfly"
    content = create_email_content(org, user.email)
    email_recipients = ["bs@empfly.com", "mk@peerxp.com"]
    # email_recipients = ["mk@peerxp.com"]

    try:
        email_template_name = "organization/email/limit_exceeded.html"
        email_message = render_to_string(email_template_name, content)
    except Exception as err:
        logger.error(err)
        err_msg = f"Add exception for {err.__class__.__name__} in send_limit_exceeded_notification"
        logger.exception(err_msg)
        return False

    try:
        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            email_recipients,
            fail_silently=False,
            html_message=email_message,
        )
        return True

    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in send_limit_exceeded_notification"
        )

    return False

def string_to_dt(datetime_str):

    try:
        return parser.parse(datetime_str)
    except Exception as err:
        print("Error in string_to_dt function")
        print(err)
    return datetime_str

def convert_string_to_date(datetime_str):

    try:
        return parser.parse(datetime_str).date(), True
    except Exception as err:
        print("Error in string_to_dt function")
        print(err)
    return None, False

def remove_dt_millie_sec_and_sec(date_time: dt):
    """ Remove millie sec from date time obj
    """
    if date_time is None:
        return
    try:
        print(type(date_time))
        if isinstance(date_time, str):
            date_time = string_to_dt(date_time)
            print("#################################")
            print(date_time)
            print(type(date_time))
        return date_time.replace(second=0, microsecond=0)
    except Exception as err:
        print("Error in remove_dt_millie_sec function")
        print(err)

    return date_time

def empty_or_data(data):
    """
    Given data to the fun is null return empty string other wise return the same data
    """
    if data:
        return data

    if data in (0,):
        return data

    return ""

def is_fr_image_limit_reached(member: Member) -> bool:
    member_image_count = member.member_images.all().count()
    return member_image_count >= MEMBER_MAX_IMAGE_COUNT

def application_name_is_wrong(request) -> bool:
    """
        For resolving the cross app login issue we are adding this function
        From frontend we will get the application name if that mismatch with
        Our application name in the settings we will throw error
    """
    try:
        requesting_application_name: str = request.data.get("application_name")

        # Application not found
        if not requesting_application_name:
            return False

        if APPLICATION_NAME.lower() == requesting_application_name.lower():
            return False

        return True
    except Exception as err:
        print(err)
        return False

def create_search_filter(fields: list, search_query):
    search_query = search_query.strip().lower()

    filters = None
    for field in fields:
        field_data = f"{field}__icontains"
        data = {field_data: search_query}

        if filters is None:
            filters = Q(**data)

        filters |= Q(**data)

    return filters

def convert_time_to_formatted_str(time, str_time_format="%I:%M %p"):
    date_and_time_obj = dt.datetime(
        2022,
        1,
        1,
        time.hour,
        time.minute
    )
    return date_and_time_obj.strftime(str_time_format)
