from utils import read_data
from utils.response import HTTP_400
from utils.utils import base64_to_contentfile, convert_to_date
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from rest_framework.response import Response
from organization.models import OrgLocation, Organization


def organization_validations(request, org):

    logo = request.data.get("logo")
    name = (request.data.get("name", "")).strip().lower()
    description = request.data.get("description")
    location = request.data.get("location")
    organization_email = request.data.get("organization_email")
    timezone = request.data.get("timezone", "UTC")

    if not name:
        raise ValidationError("Name is required.")

    if not location:
        raise ValidationError("Location is required.")

    if not organization_email:
        raise ValidationError("Organization Email is required.")

    if org.name != name and Organization.objects.filter(name=name).exists():
        raise ValidationError("Organization name already exists.")

    if logo:
        logo = base64_to_contentfile(logo)

        if isinstance(logo, Response):
            raise ValidationError("Invalid image.")

    return {
        "name": name,
        "description": description,
        "location": location,
        "logo": logo,
        "timezone": timezone,
        "organization_email": organization_email,
    }


def holiday_validations(request, org):


    name = request.data.get("name")
    description = request.data.get("description")
    date = request.data.get("date")
    org_location = request.data.get("org_location")
    holiday_status = request.data.get("status")

    print(name, "@@@@@@@@@@@ Name @@@@@@@@@@")

    if not name:
        print("############# name not found @@@@@@@@@@@@")
        raise ValidationError("Holiday name is required.")

    if not date:
        raise ValidationError("Date is required.")

    if org_location:
        try:
            org_location = OrgLocation.objects.get(uuid=org_location, organization=org)
        except OrgLocation.DoesNotExist:
            raise ValidationError("Org Location not found.")
    else:
        org_location = None

    if isinstance(holiday_status, bool) is False:
        raise ValidationError("Status must be True/False.")



    valid_date, is_valid = convert_to_date(date)
    if not is_valid:
        raise ValidationError("Date is not valid.")

    return {
        "name": name,
        "description": description,
        "date": valid_date,
        "org_location": org_location,
        "is_active": holiday_status,
        "organization": org
    }
