from typing import Dict, Tuple, Union
from member.models import Member
from organization.models import Organization, SystemLocation
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.exceptions import ValidateLocSettingsErr
from utils import fetch_data, read_data
from utils.response import HTTP_200, HTTP_400
import datetime
import pytz
from .models import Shift, ShiftScheduleLog
from utils.date_time import day_start_time, day_end_time
import logging

from utils.utils import convert_to_date, convert_to_time

logger = logging.getLogger(__name__)


def shift_validation(request, org) -> Union[Dict, Response]:

    name = request.data.get("name")
    description = request.data.get("description")
    start_time = request.data.get("start_time")
    end_time = request.data.get("end_time")
    computation_time = request.data.get("computation_time")
    present_working_hours = float(request.data.get("present_working_hours", 8))
    partial_working_hours = float(request.data.get("partial_working_hours", 4))
    enable_geo_fencing = request.data.get("enable_geo_fencing", True)
    skip_days = request.data.get("skip_days")
    default_location = request.data.get("default_location")

    # enable_check_in_time_restriction = request.data.get(
    #     "enable_check_in_time_restriction", True
    # )

    shift_start_time_restriction = request.data.get(
        "shift_start_time_restriction", True
    )

    loc_settings_start_time_restriction = request.data.get(
        "loc_settings_start_time_restriction", True
    )

    if not isinstance(shift_start_time_restriction, bool):
        return HTTP_400(
            {}, {"message": "Shift Start Time Restriction must true/false."}
        )

    if not isinstance(loc_settings_start_time_restriction, bool):
        return HTTP_400(
            {}, {"message": "Location Settings Start Time Restriction must true/false."}
        )

    try:
        present_working_hours = datetime.timedelta(hours=present_working_hours)
        present_working_hours = (present_working_hours.total_seconds() / 60) / 60
    except ValueError:
        return HTTP_400({}, {"message": "Present working hours is not valid."})

    try:
        partial_working_hours = datetime.timedelta(hours=partial_working_hours)
        partial_working_hours = (partial_working_hours.total_seconds() / 60) / 60
    except ValueError:
        return HTTP_400({}, {"message": "Partial working hours is not valid."})

    if not skip_days:
        skip_days = []



    if isinstance(skip_days, list) is False:
        return HTTP_400({}, {"message": "Invalid skip days."})

    if not name:
        return HTTP_400({}, {"message": "Name is required field."})

    if not start_time:
        return HTTP_400({}, {"message": "Start time is required field."})

    if not end_time:
        return HTTP_400({}, {"message": "End time is required field."})

    if not computation_time:
        return HTTP_400({}, {"message": "Computation time is required field."})

    if not default_location:
        return HTTP_400({}, {"message": "Default location is required field."})

    try:
        default_location = SystemLocation.objects.get(uuid=default_location)
    except SystemLocation.DoesNotExist:
        return read_data.get_404_response("System Location")

    if default_location and default_location.status == "inactive":
        return HTTP_400({}, {"message": "Default Location is inactive."})


    start_time, is_valid = convert_to_time(start_time)
    if is_valid is False:
        return HTTP_400({}, {"message": "Start Time is not valid."})

    end_time, is_valid = convert_to_time(end_time)
    if is_valid is False:
        return HTTP_400({}, {"message": "End Time is not valid."})

    computation_time, is_valid = convert_to_time(computation_time)
    if is_valid is False:
        return HTTP_400({}, {"message": "Computation Time is not valid."})

    print(computation_time.minute, "@@@@@@@@@")
    if computation_time.minute != 0:
        return HTTP_400({}, {"message": "Computation time must be in hour only. Minute are not allowded."})

    if start_time > end_time:
        if (computation_time >= start_time and computation_time <= day_end_time) or (
            computation_time >= day_start_time and computation_time < end_time
        ):
            return HTTP_400(
                {},
                {
                    "message": "Computation time cannot be within the start time and end time."
                },
            )
    elif start_time < end_time:
        if computation_time >= start_time and computation_time < end_time:
            return HTTP_400(
                {},
                {
                    "message": "Computation time cannot be within the start time and end time."
                },
            )
    
    if start_time.hour == computation_time.hour:
        return HTTP_400(
            {},
            {
                "message": "Computation time and shift start time hour cannot be same."
            },
        )

    if end_time.hour == computation_time.hour:
        return HTTP_400(
            {},
            {
                "message": "Computation time and shift end time hour cannot be same."
            },
        )

    return {
        "name": name,
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "computation_time": computation_time,
        "present_working_hours": present_working_hours,
        "partial_working_hours": partial_working_hours,
        "enable_geo_fencing": enable_geo_fencing,
        "skip_days": skip_days,
        "default_location": default_location,
        "shift_start_time_restriction": shift_start_time_restriction,
        "loc_settings_start_time_restriction": loc_settings_start_time_restriction,
    }


def location_settings_validations(datas:dict, org:Organization, member:Member) -> Tuple[ShiftScheduleLog, Dict]:

    print("#####################")

    shift_schedule_log = datas.get("shift_schedule_log")
    system_location = datas.get("system_location")
    start_time = datas.get("start_time")
    end_time = datas.get("end_time")
    applicable_start_date = datas.get("applicable_start_date")
    applicable_end_date = datas.get("applicable_end_date")

    datas = {
        "Shift Schedule Log": shift_schedule_log,
        "System Location": system_location,
        "Start Time": start_time,
        "End Time": end_time,
        "Applicable Start Date": applicable_start_date,
    }

    for key, value in datas.items():
        if not value:
            raise ValidateLocSettingsErr(f"{key} is required.")

    try:
        log = ShiftScheduleLog.objects.get(organization=org, uuid=shift_schedule_log)
    except ShiftScheduleLog.DoesNotExist:
        raise ValidateLocSettingsErr("Shift Schedule Log not found.")

    
    print(org.shift_management_settings, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    max_location_settings_count = org.shift_management_settings["location_settings"]["max_location_settings_count"]
    print(max_location_settings_count)

    # User can't created location settings more than max_location settings count config in org.
    if log.location_settings.all().count() >= int(max_location_settings_count):
        raise ValidateLocSettingsErr("Max Location settings count reached.")

    if log.status == "inactive":
        raise ValidateLocSettingsErr("Shift Schedule Log is inactive.")

    valid_start_time, is_valid = convert_to_time(start_time)
    if is_valid is False:
        raise ValidateLocSettingsErr("Start time is not valid.")

    shift_start_time = log.shift.start_time
    shift_end_time = log.shift.end_time

    # Location settings start time and end time cannot be greater than shift start time and end time.
    if shift_start_time >= shift_end_time:
        # Night Shift
        if not (
            valid_start_time >= shift_start_time
            and valid_start_time <= day_end_time
            or valid_start_time >= day_start_time
            and valid_start_time <= shift_end_time
        ):
            raise ValidateLocSettingsErr(
                "Location settings start time must be withing in the shift start time and end time."
            )
    elif not (
        valid_start_time >= shift_start_time and valid_start_time <= shift_end_time
    ):
        # Normal day shift
        raise ValidateLocSettingsErr(
            "Location settings start time must be withing in the shift start time and end time."
        )

    valid_end_time, is_valid = convert_to_time(end_time)
    if is_valid is False:
        raise ValidateLocSettingsErr("End time is not valid.")

    if shift_start_time >= shift_end_time:
        # Night Shift
        if not (
            valid_end_time >= shift_start_time
            and valid_end_time <= day_end_time
            or valid_end_time >= day_start_time
            and valid_end_time <= shift_end_time
        ):
            raise ValidateLocSettingsErr(
                "Location settings end time must be withing in the shift start time and end time."
            )
    elif not (valid_end_time >= shift_start_time and valid_end_time <= shift_end_time):
        raise ValidateLocSettingsErr(
            "Location settings end time must be withing in the shift start time and end time."
        )

    computation_time = log.shift.computation_time
    if valid_end_time > computation_time:
        if valid_start_time > valid_end_time and valid_start_time < day_end_time or valid_start_time > day_start_time and valid_start_time < computation_time:
            raise ValidateLocSettingsErr("Location settings start time cannot be greater than location settings end time")

    elif valid_start_time > valid_end_time and valid_start_time < computation_time:
        raise ValidateLocSettingsErr("Location settings start time cannot be greater than location settings end time")

    # Location settings start date and end date cannot be greater than SSL start date and end date.

    applicable_start_date, is_valid = convert_to_date(applicable_start_date)
    if is_valid is False:
        raise ValidateLocSettingsErr("Applicable start date is not valid.")

    log_start_date = log.start_date
    log_end_date = log.end_date

    if applicable_start_date < log_start_date:
        raise ValidateLocSettingsErr(
            "Location settings start date must be greater than shift schedule log start date."
        )

    if log_end_date and applicable_start_date > log_end_date:
        raise ValidateLocSettingsErr(
            "Location settings end date must be less than shift schedule log end date."
        )


    print(log_start_date, "#############", applicable_start_date)
    print(applicable_end_date, "++++++++++++++++++++++++=")

    if applicable_end_date:
        applicable_end_date, is_valid = convert_to_date(applicable_end_date)
        if is_valid is False:
            raise ValidateLocSettingsErr("Start time is not valid.")

        if applicable_start_date > applicable_end_date:
            raise ValidateLocSettingsErr(
                "Applicable start date cannot be greater than applicable end date."
            )

        if log_end_date and applicable_end_date > log_end_date:
            raise ValidateLocSettingsErr(
                "Applicable end date cannot be greater than shift Schedule Log end date."
            )
    else:
        applicable_end_date = log_end_date

    try:
        system_location = SystemLocation.objects.get(
            uuid=system_location, organization=org
        )
    except SystemLocation.DoesNotExist:
        return ValidateLocSettingsErr("System Location not found.")

    return log, {
        "system_location":system_location,
        "start_time":start_time,
        "end_time":end_time,
        "applicable_start_date":applicable_start_date,
        "applicable_end_date":applicable_end_date,
        "created_by":member,
        "updated_by":member,
        "organization":org,
    }
