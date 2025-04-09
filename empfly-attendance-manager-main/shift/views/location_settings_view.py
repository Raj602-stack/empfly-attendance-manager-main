from datetime import datetime, date
from email import message
from member.models import Member
from organization.models import (
    Department,
    Designation,
    OrgLocation,
    Organization,
    SystemLocation,
)
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.exceptions import ValidateLocSettingsErr
from shift.models import LocationSettings, Shift, ShiftScheduleLog
from shift.serializers import (
    LocationSettingsSerializer,
    ShiftScheduleLogSerializer,
    ShiftSerializer,
)
from shift.shift_schedule_logic import (
    create_log_for_deactivate,
    create_log_for_shift,
    deactivate_shift,
)
from shift.validations import location_settings_validations
from utils import fetch_data, read_data
from utils.response import HTTP_200, HTTP_400
from utils.utils import convert_to_date, convert_to_time, pagination
from django.db.models import Q
from utils.utils import convert_to_time
from utils.date_time import day_start_time, day_end_time

import logging

logger = logging.getLogger(__name__)


# class AllLocationSettingsAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]
#     serializer_class = LocationSettingsSerializer

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         uuid = request.GET.get("uuid")
#         locations = LocationSettings.objects.filter(shift__uuid=uuid)

#         serializer = self.serializer_class(locations, many=True)
#         return HTTP_200(serializer.data)

#     def post(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         shift = request.data.get("shift")
#         if not shift:
#             return HTTP_400({}, {"message": "shift is required"})
#         try:
#             shift = Shift.objects.get(uuid=shift)
#         except Shift.DoesNotExist:
#             return read_data.get_404_response("Shift")

#         loc_settings_count = LocationSettings.objects.filter(shift=shift).count()
#         max_loc_count = org.shift_management_settings["location_settings"][
#             "max_location_settings_count"
#         ]

#         if loc_settings_count >= int(max_loc_count):
#             return HTTP_400({}, {"message": "Max location limit is reached."})

#         system_location = request.data.get("system_location")
#         start_time = request.data.get("start_time")
#         end_time = request.data.get("end_time")
#         applicable_start_date = request.data.get("applicable_start_date")
#         applicable_end_date = request.data.get("applicable_end_date")

#         if not system_location:
#             return HTTP_400({}, {"message": "System Location is required"})

#         if not start_time:
#             return HTTP_400({}, {"message": "Start time is required"})

#         if not end_time:
#             return HTTP_400({}, {"message": "End time is required"})

#         if not applicable_start_date:
#             return HTTP_400({}, {"message": "Applicable start date is required"})

#         try:
#             system_location = SystemLocation.objects.get(uuid=system_location)
#         except SystemLocation.DoesNotExist:
#             return read_data.get_404_response("System Location")

#         start_time, is_valid = convert_to_time(start_time)
#         if is_valid is False:
#             return HTTP_400({}, {"message": "Start time is not valid."})

#         end_time, is_valid = convert_to_time(end_time)
#         if is_valid is False:
#             return HTTP_400({}, {"message": "End time is not valid."})

#         if start_time >= end_time:
#             return HTTP_400({}, {"message": "Start time cannot be greater than End time."})

#         applicable_start_date, is_valid = convert_to_date(applicable_start_date)
#         if is_valid is False:
#             return HTTP_400({}, {"message": "Applicable start date is not valid."})

#         shift_start_time = shift.start_time
#         shift_end_time = shift.end_time

#         if start_time < shift_start_time:
#             return HTTP_400(
#                 {},
#                 {
#                     "message": "Location settings start time cannot be less than shift start time."
#                 },
#             )

#         if end_time > shift_end_time:
#             return HTTP_400(
#                 {},
#                 {
#                     "message": "Location settings start time cannot be greater than shift end time."
#                 },
#             )

#         if applicable_end_date:

#             applicable_end_date, is_valid = convert_to_date(applicable_end_date)

#             if is_valid is False:
#                 return HTTP_400({}, {"message": "Applicable end date is not valid"})
#             if applicable_start_date > applicable_end_date:
#                 return HTTP_400(
#                     {},
#                     {
#                         "message": "Location settings applicable start date cannot be greater than applicable end date."
#                     },
#                 )

#         location = LocationSettings.objects.create(
#             system_location=system_location,
#             shift=shift,
#             start_time=start_time,
#             end_time=end_time,
#             applicable_start_date=applicable_start_date,
#             applicable_end_date=applicable_end_date,
#             created_by=member,
#             updated_by=member,
#         )

#         serializer = self.serializer_class(location)
#         return HTTP_200(serializer.data)

#     def put(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         try:
#             uuid = request.data.get("uuid")
#             location_settings = LocationSettings.objects.get(uuid=uuid)
#         except LocationSettings.DoesNotExist:
#             return read_data.get_404_response("Location Settings")

#         system_location = request.data.get("system_location")
#         shift = request.data.get("shift")
#         start_time = request.data.get("start_time")
#         end_time = request.data.get("end_time")
#         applicable_start_date = request.data.get("applicable_start_date")
#         applicable_end_date = request.data.get("applicable_end_date")

#         if not system_location:
#             return HTTP_400({}, {"message": "System Location is required"})

#         if not shift:
#             return HTTP_400({}, {"message": "shift is required"})

#         if not start_time:
#             return HTTP_400({}, {"message": "start_time is required"})

#         if not end_time:
#             return HTTP_400({}, {"message": "end_time is required"})

#         if not applicable_start_date:
#             return HTTP_400({}, {"message": "applicable_start_date is required"})

#         try:
#             system_location = SystemLocation.objects.get(uuid=system_location)
#         except SystemLocation.DoesNotExist:
#             return read_data.get_404_response("System Location")

#         try:
#             shift = Shift.objects.get(uuid=shift)
#         except Shift.DoesNotExist:
#             return read_data.get_404_response("Shift")

#         start_time, is_valid = convert_to_time(start_time)
#         if is_valid is False:
#             return HTTP_400({}, {"message": "Start time is not valid."})

#         end_time, is_valid = convert_to_time(end_time)
#         if is_valid is False:
#             return HTTP_400({}, {"message": "End time is not valid."})

#         applicable_start_date, is_valid = convert_to_date(applicable_start_date)
#         if is_valid is False:
#             return HTTP_400({}, {"message": "Applicable start date is not valid."})

#         shift_start_time = shift.start_time
#         shift_end_time = shift.end_time

#         if start_time < shift_start_time:
#             return HTTP_400(
#                 {},
#                 {
#                     "message": "location settings start time cannot less than shift start time."
#                 },
#             )

#         if end_time > shift_end_time:
#             return HTTP_400(
#                 {},
#                 {
#                     "message": "location settings start time cannot greater than shift end time."
#                 },
#             )

#         if applicable_end_date:
#             applicable_end_date, is_valid = convert_to_date(applicable_end_date)
#             if is_valid is False:
#                 return HTTP_400({}, {"message": "Applicable end date is not valid"})

#             if applicable_start_date > applicable_end_date:
#                 return HTTP_400(
#                     {},
#                     {
#                         "message": "location settings applicable start date cannot greater than applicable end date."
#                     },
#                 )

#         location_settings.system_location = system_location
#         location_settings.shift = shift
#         location_settings.start_time = start_time
#         location_settings.end_time = end_time
#         location_settings.applicable_start_date = applicable_start_date
#         location_settings.applicable_end_date = applicable_end_date
#         location_settings.updated_by = member
#         location_settings.save()

#         serializer = self.serializer_class(location_settings)
#         return HTTP_200(serializer.data)


# class LocationSettingsAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]
#     serializer_class = LocationSettingsSerializer

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         try:
#             uuid = kwargs["uuid"]
#             location = LocationSettings.objects.get(uuid=uuid)
#         except LocationSettings.DoesNotExist:
#             return read_data.get_404_response("Location Settings")

#         serializer = self.serializer_class(location)
#         return HTTP_200(serializer.data)

#     def delete(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin_or_hr(member) is False:
#             return read_data.get_403_response()

#         try:
#             uuid = kwargs.get("uuid")
#             location_settings = LocationSettings.objects.get(uuid=uuid)
#         except LocationSettings.DoesNotExist:
#             return read_data.get_404_response("Location Settings")
#         location_settings.delete()
#         return HTTP_200({})


class ShiftLocationSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = LocationSettingsSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        shift_uuid = kwargs["uuid"]
        locations = LocationSettings.objects.filter(shift__uuid=shift_uuid)

        serializer = self.serializer_class(locations, many=True)
        return HTTP_200(serializer.data)


class CheckShiftExistAsFK(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = LocationSettingsSerializer

    warning = {
        "message": "This action will assign Shift to all the selected Applicability options."
    }

    def check_will_override(self, Queryset: Member, shift: Shift):
        return Queryset.filter(~Q(shift__isnull=False) & ~Q(shift=shift)).exists()

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        department = request.data.get("department", [])
        designation = request.data.get("designation", [])
        org_location = request.data.get("org_location", [])
        employee = request.data.get("employee", [])
        shift_uuid = request.data.get("shift")

        try:
            shift = Shift.objects.get(uuid=shift_uuid)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        arr = [0, 0, 0]

        priorities = org.settings["applicability_settings_priority"]

        for i in priorities:
            arr.insert(i["priority"], i["name"])

        members = Member.objects.filter(organization=org)

        for i in arr:
            if i == "department":
                if department:
                    members = members.filter(department__uuid__in=department)

                    is_override = members.filter(
                        Q(department__shift__isnull=False) & ~Q(department__shift=shift)
                    ).exists()
                    if is_override is True:
                        return HTTP_400({}, self.warning)

            elif i == "designation":
                if designation:
                    members = members.filter(designation__uuid__in=designation)

                    is_override = members.filter(
                        Q(designation__shift__isnull=False)
                        & ~Q(designation__shift=shift)
                    ).exists()
                    if is_override is True:
                        return HTTP_400({}, self.warning)

            elif i == "org_location":
                if org_location:
                    members = members.filter(org_location__uuid__in=org_location)

                    is_override = members.filter(
                        Q(org_location__shift__isnull=False)
                        & ~Q(org_location__shift=shift)
                    ).exists()
                    if is_override is True:
                        return HTTP_400({}, self.warning)

            # elif i == "employee":
            #     if employee:
            #         members = members.filter(uuid__in=employee)

            #         is_override = members.filter(
            #             Q(shift__isnull=False) & ~Q(shift=shift)
            #         ).exists()
            #         if is_override is True:
            #             return HTTP_400({}, self.warning)

        if members.count() >= 1:
            is_override = members.filter(
                ~Q(applicable_shift__isnull=False) & ~Q(applicable_shift=shift)
            )
            if is_override.exists():
                return HTTP_400({}, self.warning)

        return HTTP_200({})


class LocationSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = LocationSettingsSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        shift_schedule_log = request.GET.get("shift_schedule_log")
        if not shift_schedule_log:
            return HTTP_400({}, {"message": "Shift Schedule Log is required."})

        try:
            logs = ShiftScheduleLog.objects.get(
                organization=org, uuid=shift_schedule_log
            )
        except ShiftScheduleLog.DoesNotExist:
            return read_data.get_404_response("Shift Schedule Log")

        logs_loc_settings = logs.location_settings.all()
        serializer = LocationSettingsSerializer(logs_loc_settings, many=True)

        return HTTP_200(serializer.data)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            print("==========================")
            log, validated_data = location_settings_validations(request.data, org, member)
        except ValidateLocSettingsErr as err:
            print(err)
            return HTTP_400({}, {"message": err.message})
        print(log, validated_data)

        location_settings = LocationSettings.objects.create(**validated_data)

        log.location_settings.add(location_settings)
        log.save()

        serializer = self.serializer_class(location_settings)
        return HTTP_200(serializer.data)


class AllLocationSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = LocationSettingsSerializer

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        system_location = request.data.get("system_location")
        start_time = request.data.get("start_time")
        end_time = request.data.get("end_time")
        applicable_start_date = request.data.get("applicable_start_date")
        applicable_end_date = request.data.get("applicable_end_date")

        datas = {
            "System Location": system_location,
            "Start Time": start_time,
            "End Time": end_time,
            "Applicable Start Date": applicable_start_date,
        }

        for key, value in datas.items():
            if not value:
                return HTTP_400({}, {"message": f"{key} is required."})

        try:
            location_settings = LocationSettings.objects.get(uuid=kwargs["uuid"])
        except LocationSettings.DoesNotExist:
            return read_data.get_404_response("Location Settings")

        try:
            log = location_settings.shift_schedule_log.get()
        except ShiftScheduleLog.DoesNotExist:
            return read_data.get_404_response("Shift Schedule Log")
        except ShiftScheduleLog.MultipleObjectsReturned:
            return HTTP_400(
                {},
                {
                    "message": "Location settings configured for multiple shift schedule logs. Please unassign from the logs."
                },
            )

        valid_start_time, is_valid = convert_to_time(start_time)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start time is not valid."})

        shift_start_time = log.shift.start_time
        shift_end_time = log.shift.end_time

        if shift_start_time >= shift_end_time:
            # Night Shift
            if not (
                valid_start_time >= shift_start_time
                and valid_start_time <= day_end_time
                or valid_start_time >= day_start_time
                and valid_start_time <= shift_end_time
            ):
                return HTTP_400({}, {"message": "Location settings start time must be withing in the shift start time and end time."})
        elif not (
            valid_start_time >= shift_start_time and valid_start_time <= shift_end_time
        ):
            # Normal day shift
            return HTTP_400({}, {"message": "Location settings start time must be withing in the shift start time and end time."})

        valid_end_time, is_valid = convert_to_time(end_time)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start time is not valid."})


        if shift_start_time >= shift_end_time:
            # Night Shift
            if not (
                valid_end_time >= shift_start_time
                and valid_end_time <= day_end_time
                or valid_end_time >= day_start_time
                and valid_end_time <= shift_end_time
            ):
                return HTTP_400({}, {"message": "Location settings end time must be withing in the shift start time and end time."})
        elif not (valid_end_time >= shift_start_time and valid_end_time <= shift_end_time):
            return HTTP_400({}, {"message": "Location settings end time must be withing in the shift start time and end time."})

        computation_time = log.shift.computation_time
        if valid_end_time > computation_time:
            if valid_start_time > valid_end_time and valid_start_time <= day_end_time or valid_start_time >= day_start_time and valid_start_time < computation_time:
                return HTTP_400({}, {"message": "Location settings start time cannot be greater than location settings end time"})
        elif valid_start_time > valid_end_time and valid_start_time < computation_time:
            return HTTP_400({}, {"message": "Location settings start time cannot be greater than location settings end time"})


        applicable_start_date, is_valid = convert_to_date(applicable_start_date)
        if is_valid is False:
            return HTTP_400({}, {"message": "Applicable start date is not valid."})

        log_start_date = log.start_date
        if applicable_start_date < log_start_date:
            return HTTP_400(
                {},
                {
                    "message": "Location settings start date can't be less than the Shift Start date."
                },
            )

        if applicable_end_date:
            applicable_end_date, is_valid = convert_to_date(applicable_end_date)
            if is_valid is False:
                return HTTP_400({}, {"message": "Start time is not valid."})

            if applicable_start_date > applicable_end_date:
                return HTTP_400(
                    {},
                    {
                        "message": "Applicable start date cannot be greater than applicable end date."
                    },
                )

            log_end_date = log.end_date

            if log_end_date and applicable_end_date > log_end_date:
                return HTTP_400(
                    {},
                    {
                        "message": "Applicable end date cannot be greater than shift end date."
                    },
                )
        else:
            applicable_end_date = log.end_date

        try:
            system_location = SystemLocation.objects.get(
                uuid=system_location, organization=org
            )
        except SystemLocation.DoesNotExist:
            return read_data.get_404_response("System Location")

        location_settings.system_location = system_location
        location_settings.start_time = start_time
        location_settings.end_time = end_time
        location_settings.applicable_start_date = applicable_start_date
        location_settings.applicable_end_date = applicable_end_date
        location_settings.updated_by = member
        location_settings.save()

        serializer = self.serializer_class(location_settings)
        return HTTP_200(serializer.data)

    def delete(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            loc_setting = LocationSettings.objects.get(uuid=kwargs["uuid"])
        except LocationSettings.DoesNotExist:
            return read_data.get_404_response("Location Settings")

        loc_setting.delete()
        return HTTP_200({})
