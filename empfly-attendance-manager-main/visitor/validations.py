from typing import Dict, Tuple, Union
from utils.fetch_data import is_front_desk
from utils.utils import HTTP_400, convert_to_date, convert_to_time
from visitor.models import Visitor
from member.models import Member
from organization.models import OrgLocation
from django.core.exceptions import ValidationError
from datetime import datetime
from utils import date_time


def validate_visitation(request, user_role:str, requesting_member:Member) -> Tuple[HTTP_400, Dict]:
    print(user_role, "#######3")
    organization = requesting_member.organization

    name = request.data.get("name", "").strip()
    description = request.data.get("description", "").strip()
    visitor = request.data.get("visitor")
    host = request.data.get("host")
    visitation_date = request.data.get("visitation_date")
    start_time = request.data.get("start_time")
    end_time = request.data.get("end_time")
    org_location = request.data.get("org_location")

    if not name:
        return HTTP_400({},{"message": "Enter a valid name"})

    if not visitor:
        return HTTP_400({},{"message": "Enter a valid visitor"})

    if not host:
        return HTTP_400({},{"message": "Enter a valid host"})

    if not visitation_date:
        return HTTP_400({},{"message": "Enter a valid visitation_date"})

    if not start_time:
        return HTTP_400({},{"message": "Enter a valid start_time"})

    visit_date, is_valid = convert_to_date(visitation_date)
    if is_valid is False:
        return HTTP_400({},{"message": "Visitation date is not valid."})

    if visit_date < date_time.today_date():
        return HTTP_400({},{"message": "Visitation date cannot be less than today."})

    if not org_location:
        return HTTP_400({},{"message": "Enter a valid org_location"})

    valid_start_time, is_valid = convert_to_time(start_time, "%H:%M")
    if is_valid is False:
        return HTTP_400({},{"message": "Start time is not valid."})

    if end_time:
        valid_end_time, is_valid = convert_to_time(end_time, "%H:%M")
        if is_valid is False:
            return HTTP_400({},{"message": "Enter a valid end time."})
    else:
        end_time = None

    if end_time and valid_end_time <= valid_start_time :
        return HTTP_400({}, {"message": "End time should not be less than start time."})

    visitor = Visitor.objects.filter(uuid=visitor, organization=organization)
    if not visitor.exists():
        return HTTP_400({},{"message": "Enter a valid Visitor"})

    visitor = visitor.first()

    host = Member.objects.filter(uuid=host, organization=organization)
    if not host.exists():
        return HTTP_400({},{"message": "Enter a valid Host"})

    # Host's allowed_to_meet must be true for create visitation. 
    if host.first().allowed_to_meet is False:
        return HTTP_400({},{"message": "Selected Host is not allowed to meet."})

    host = host.first()

    if user_role == "member" and host.user != request.user:
        return HTTP_400({},{"message": "Member cannot select other Hosts."})

        # if requesting_member.is_front_desk is False:
        #     return HTTP_400({},{"message": "Member cannot select other other Hosts."})

    try:
        org_location = OrgLocation.objects.get(uuid=org_location)
    except (OrgLocation.DoesNotExist, ValidationError):
        return HTTP_400({},{"message": "Enter a valid Organization Location"})

    if user_role == "member" and host.org_location != org_location:
        return HTTP_400({},{"message": "Member cannot select other Organization Location."})

    if org_location.enable_visitation is False:
        return HTTP_400({},{"message": "Visitations are disabled for this Organization Location."})

    if org_location != host.org_location:
        return HTTP_400({},{"message": "Host not belongs to the selected Organization."})

    if user_role == "visitor":
        allow_non_invited_visitors = visitor.organization.settings.get("visitor_management_settings").get("allow_non_invited_visitors")
        if allow_non_invited_visitors is False:
            return HTTP_400({},{"message": "You dont have permission to create visitation."})

    return {
        "name": name,
        "visitor": visitor,
        "host": host,
        "visitation_date": visitation_date,
        "start_time": start_time,
        "org_location": org_location,
        "description": description,
        "end_time": end_time
    }
