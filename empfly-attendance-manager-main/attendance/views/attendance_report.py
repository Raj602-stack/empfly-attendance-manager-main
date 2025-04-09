from attendance.filters import filter_report_for_attendance
from attendance.models import Attendance, MemberScan
from member.models import Member
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import fetch_data, read_data
from utils import date_time
from utils.response import HTTP_200, HTTP_400
from django.db.models import Avg, Count, Max, F
from utils.date_time import curr_dt_with_org_tz
import logging
from export.utils import create_export_request
from export import utils as export_utils

logger = logging.getLogger(__name__)


class MemberAttendanceReportAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        attendances = Attendance.objects.filter(organization=org)

        attendances = filter_report_for_attendance(attendances, request)

        attendances = list(
            attendances.values("status").annotate(status_count=Count("status"))
        )

        avail_attendance_status = {"present", "partial", "absent", "weekend", "holiday"}

        for attendance in attendances:
            if attendance.get("status") not in avail_attendance_status:
                continue
            avail_attendance_status.remove(attendance.get("status"))

        for attendance_status in avail_attendance_status:
            attendances.append({"status": attendance_status, "status_count": 0})

        sum_of_total_count = sum(item["status_count"] for item in attendances)
        print(sum_of_total_count)

        attendance_with_percentage = map(
            lambda data: {
                "percentage": (data["status_count"] / sum_of_total_count) * 100 if sum_of_total_count != 0 else 0,
                "status": str(data["status"]).capitalize(),
            },
            attendances,
        )

        print(attendance_with_percentage)

        return HTTP_200(attendance_with_percentage)


class MemberCheckInStatusAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        """ Show data in report page. Check in, check out, yet to check in status
        """
        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        curr_dt = curr_dt_with_org_tz()
        print(curr_dt)

        members_today_scans = MemberScan.objects.filter(
            date_time__date=curr_dt.date(),
            member__status="active", status="pending",
            is_computed=False, organization=org
        )
        members = Member.objects.filter(organization=org, status="active")


        if bool(request.GET.get("export_csv")) is True:
            if not members.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            members_ids = export_utils.get_uuid_from_qs(members)
            filters = {
                "date": str(curr_dt.date())
            }

            export_request = create_export_request(
                member, "member_curr_day_attendance_status", members_ids, filters=filters
            )
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        yet_to_check_in = 0
        check_in = 0
        check_out = 0

        for member in members:
            member_scan = members_today_scans.filter(member=member)
            if not member_scan.exists():
                yet_to_check_in += 1
                continue

            last_scan = member_scan.order_by("date_time").last()
            if last_scan.scan_type == "check_in":
                check_in += 1
            elif last_scan.scan_type == "check_out":
                check_out += 1


        return HTTP_200({
            "check_in": check_in,
            "check_out": check_out,
            "yet_to_check_in": yet_to_check_in,
        })
