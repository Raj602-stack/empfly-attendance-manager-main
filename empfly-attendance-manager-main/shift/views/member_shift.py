import pytz
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.models import ShiftScheduleLog
from utils import fetch_data, read_data
from utils import date_time
from utils.response import HTTP_200
from shift.serializers import LocationSettingsSerializer, ShiftScheduleLogSerializer
from datetime import datetime as dt, timedelta
from django.db.models import Q
from utils.shift import curr_shift_schedule_log


import logging
logger = logging.getLogger(__name__)


class TodayShiftAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftScheduleLogSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        today_dt = date_time.curr_dt_with_org_tz()

        log, location_settings, log_date = curr_shift_schedule_log(member, today_dt, org)

        serializer = self.serializer_class(log, exclude=["location_settings"])
        loc_settings_serializer = LocationSettingsSerializer(location_settings, many=True)

        data = serializer.data
        data["location_settings"] = loc_settings_serializer.data
        return HTTP_200({
            "log": data,
            "date": log_date,
            "location_settings": loc_settings_serializer.data
        })
