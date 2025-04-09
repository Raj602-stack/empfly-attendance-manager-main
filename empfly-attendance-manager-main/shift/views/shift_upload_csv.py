from django.db import IntegrityError
from export.utils import create_export_request
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q
from api import permissions
from organization.models import Department, Designation, OrgLocation, Role, SystemLocation
from account.models import User
from member.models import Member
from shift.exceptions import UploadCSVLocSettingsErr
from shift.models import LocationSettings, Shift, ShiftScheduleLog
from utils import date_time
from utils.response import HTTP_200, HTTP_400
from utils import read_data, fetch_data, create_data
from utils.date_time import day_start_time, day_end_time
import logging

from utils.utils import convert_string_to_date, convert_to_date, convert_to_time, string_to_dt

logger = logging.getLogger(__name__)


class LocationSettingsUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "system location": "Kerala",
                "start time (hh:mm)": "10:00",
                "end time (hh:mm)": "19:00",
                "employee username": "admin@peerxp.com",
                "shift": "General",
                "date (yyyy-mmd-dd)": "2023-12-01",
            },
            {
                "system location": "Bangalore",
                "start time (hh:mm)": "10:00",
                "end time (hh:mm)": "19:00",
                "employee username": "shahin.salim@peerxp.com",
                "shift": "General",
                "date (yyyy-mmd-dd)": "2023-12-01",
            },
        ]
        return HTTP_200(schema)

    def post(self, request, *args, **kwargs):
        print("-----------"*10)
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        if df is None:
            return HTTP_400({}, {})

        failed_rows, failed_location_settings = [], []
        created_count, row_count = 0, 1

        all_system_location = SystemLocation.objects.filter(organization=org)
        org_members = Member.objects.filter(organization=org).select_related("user")
        
        shifts = Shift.objects.filter(organization=org)
        logs = ShiftScheduleLog.objects.filter(organization=org)

        today_date = date_time.curr_dt_with_org_tz().date()
        max_location_settings_count = org.shift_management_settings["location_settings"]["max_location_settings_count"]


        for row in df.values:
            row_len = len(row)
            row_count += 1

            try:
                if row_len != 6:
                    pass

                system_location_name = row[0]
                start_time = row[1]
                end_time = row[2]
                employee_username = row[3]
                shift_name = row[4]
                applicable_date = row[5]

                system_location = all_system_location.get(name=system_location_name)


                if read_data.is_inactive_system_location(system_location):
                    UploadCSVLocSettingsErr("System location is inactive.")

                start_time, is_valid = convert_to_time(start_time)
                if is_valid is False:
                    raise UploadCSVLocSettingsErr("Start time is not valid.")

                end_time, is_valid = convert_to_time(end_time)
                if is_valid is False:
                    raise UploadCSVLocSettingsErr("End time is not valid.")

                selected_member = org_members.get(user__username=employee_username)

                shift = shifts.get(name=shift_name)

                applicable_date, is_valid = convert_string_to_date(applicable_date)
                if is_valid is False:
                    raise UploadCSVLocSettingsErr("Start date is not valid.")

                if applicable_date < today_date:
                    raise UploadCSVLocSettingsErr("Date is already passed.")


                filtered_logs = logs.filter(shift=shift, employee=selected_member, status="active")
                log = filtered_logs.get(
                    Q(start_date__lte=applicable_date, end_date__gte=applicable_date) |
                    Q(start_date__lte=applicable_date, end_date__isnull=True)
                )

                if log.location_settings.all().count() >= int(max_location_settings_count):
                    raise UploadCSVLocSettingsErr("Max Location settings count reached.")

                shift_start_time = shift.start_time
                shift_end_time = shift.end_time
                shift_computation_time = shift.computation_time

                # Location settings start time and end time cannot be greater than shift start time and end time.
                if shift_start_time >= shift_end_time:
                    # Night Shift
                    if not (
                        start_time >= shift_start_time
                        and start_time <= day_end_time
                        or start_time >= day_start_time
                        and start_time <= shift_end_time
                    ):
                        raise UploadCSVLocSettingsErr(
                            "Location settings start time must be withing in the shift start time and end time."
                        )
                elif not (
                    start_time >= shift_start_time and start_time <= shift_end_time
                ):
                    # Normal day shift
                    raise UploadCSVLocSettingsErr(
                        "Location settings start time must be withing in the shift start time and end time."
                    )


                valid_start_time = start_time
                valid_end_time = end_time

                if shift_start_time >= shift_end_time:
                    # Night Shift
                    if not (
                        valid_end_time >= shift_start_time
                        and valid_end_time <= day_end_time
                        or valid_end_time >= day_start_time
                        and valid_end_time <= shift_end_time
                    ):
                        raise UploadCSVLocSettingsErr(
                            "Location settings end time must be withing in the shift start time and end time."
                        )
                elif not (valid_end_time >= shift_start_time and valid_end_time <= shift_end_time):
                    raise UploadCSVLocSettingsErr(
                        "Location settings end time must be withing in the shift start time and end time."
                    )

                if valid_end_time > shift_computation_time:
                    if valid_start_time > valid_end_time and valid_start_time < day_end_time or valid_start_time > day_start_time and valid_start_time < shift_computation_time:
                        raise UploadCSVLocSettingsErr("Location settings start time cannot be greater than location settings end time")

                elif valid_start_time > valid_end_time and valid_start_time < shift_computation_time:
                    raise UploadCSVLocSettingsErr("Location settings start time cannot be greater than location settings end time")


                location_settings = LocationSettings.objects.create(
                    system_location=system_location,
                    organization=org,
                    start_time=start_time,
                    end_time=end_time,
                    applicable_start_date=applicable_date,
                    applicable_end_date=applicable_date,
                    created_by=requesting_member
                )


                log.location_settings.add(location_settings)
                log.save()

                created_count += 1

            except Exception as err:
                failed_rows.append(row_count)
                try:
                    failed_location_settings.append(
                        {
                            "email": row[0],
                            "reason": str(err.__class__.__name__),
                            "detailed_reason": str(err),
                        }
                    )
                except Exception:
                    pass
                logger.error(err)
                logger.exception(
                    f"Add exception for {err.__class__.__name__} in LocationSettingsUploadCSVAPI"
                )

        return Response(
            {
                "failed_location_settings": failed_location_settings,
                "created_count": created_count,
                "failed_rows": failed_rows,
                # "updated_count": update_count,
            },
            status=status.HTTP_201_CREATED,
        )
