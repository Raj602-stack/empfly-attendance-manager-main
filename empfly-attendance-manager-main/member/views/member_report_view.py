from member.models import Member
from organization.models import Organization
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.serializers import ShiftScheduleLogSerializer
from utils import fetch_data, read_data
from utils.date_time import curr_date_time_with_tz, curr_dt_with_org_tz
from utils.response import HTTP_200
from attendance.models import Attendance, MemberScan
from attendance.serializers import AttendanceSerializer
from shift.models import ShiftScheduleLog
from datetime import datetime as dt
from django.db.models import Q


import logging
from utils.shift import curr_shift_schedule_log

from visitor.models import Visitor, VisitorScan

logger = logging.getLogger(__name__)


class DashboardAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    # serializer_class = VisitorSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        scans = MemberScan.objects.filter(organization=org).order_by("date_time")
        attendance = Attendance.objects.filter(organization=org).order_by("date")
        members = Member.objects.filter(organization=org, status="active")
        visitors = Visitor.objects.filter(organization=org, status="active")
        visitor_scans = VisitorScan.objects.filter(organization=org)

        # Check in time
        my_scans, last_check_in_time = scans.filter(member=member), None
        last_check_in_time = None
        if my_scans.exists(): # Checked in
            last_scan = my_scans.last()
            last_check_in_time = last_scan.date_time if last_scan else None

        # latest attendance
        my_attendance = attendance.filter(member=member)
        attendance_serializer = AttendanceSerializer(my_attendance.last())

        # TODO check
        today_dt = curr_dt_with_org_tz()
        today = today_dt.date()


        log = curr_shift_schedule_log(member, today_dt, org)[0]
        log_serializer = ShiftScheduleLogSerializer(log)

        data = {
            "last_check_in_time": last_check_in_time,
            "last_attendance": attendance_serializer.data,
            "today_shift": log_serializer.data,
        }

        if fetch_data.is_admin_or_hr(member) is True:
            scans_count = scans.filter(date_time__date=today).values("member").distinct().count()
            members_count = members.count()

            member_scans_percentage = 0
            if members_count > 0:
                member_scans_percentage = (scans_count / members_count) * 100

            data["scans_count"] =  scans_count
            data["scans_count_percentage"] =  member_scans_percentage

            visitor_scans_count = visitor_scans.filter(date=today).values("visitor").distinct().count()
            visitors_count = visitors.count()

            visitor_scans_percentage = 0
            if visitors_count > 0:
                visitor_scans_percentage = (visitor_scans_count / visitors_count) * 100

            data["visitors_count"] =  visitor_scans_count
            data["visitors_count_percentage"] =  visitor_scans_percentage

        return HTTP_200(data)
