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
from attendance.filters import filter_ot_request
from utils.utils import pagination
from attendance import serializers
from utils.read_data import get_404_response

logger = logging.getLogger(__name__)


class OtRequestAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AttendanceSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        attendances = Attendance.objects.filter(
            organization=org,
            member__manager=member,
            ot_status="ot_requested"
        )

        page_obj, num_pages, page = pagination(attendances, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        attendances = filter_ot_request(attendances, request)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        attendance = request.data.get("attendance")
        ot_status = request.data.get("ot_status")

        current_ot_status = ("ot_approved", "ot_rejected",)

        if not attendance:
            return HTTP_400("attendance uuid is required.")

        if ot_status not in current_ot_status:
            return HTTP_400("Status must be ot_approved/ot_rejected")

        try:
            attendance = Attendance.objects.get(
                id=attendance, organization=org, member__manager=member
            )
        except Attendance.DoesNotExist:
            return get_404_response("Attendance")

        if attendance.ot_status in current_ot_status:
            return HTTP_400(f"Attendance status is already {attendance.ot_status}")
        
        if attendance.ot_status != "ot_requested":
            return HTTP_400("Ot status is not ot requested.")

        if ot_status == "ot_rejected":
            attendance.ot_status = "ot_rejected"
            attendance.save()
            return HTTP_200({})
        
        attendance.ot_status = "ot_approved"

        # ot approved
        duration = attendance.duration
        overtime = attendance.overtime

        attendance.duration = duration + overtime
        attendance.ot_verified_by = member

        # shift = attendance.shift

        # attendance_duration_in_hours = attendance.duration / 60
        # total_shift_present_hours, total_shift_partial_hours = shift.present_working_hours, shift.partial_working_hours

        # if attendance.status not in ("weekend", "holiday"):
        #     if attendance_duration_in_hours >= total_shift_present_hours:
        #         attendance.status = "present"
        #     elif attendance_duration_in_hours >= total_shift_partial_hours:
        #         attendance.status = "partial"
        #     else:
        #         attendance.status = "absent"

        attendance.save()
        return HTTP_200({})



class RaiseOTAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AttendanceSerializer

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        remarks = request.data.get("remarks")
        attendance_id = request.data.get("attendance_id")

        if not remarks:
            return HTTP_400("Remarks is required.")

        if not attendance_id:
            return HTTP_400("attendance_id is required.")

        if not isinstance(attendance_id, int):
            return HTTP_400("attendance_id must be an integer.")

        try:
            attendance = Attendance.objects.get(
                id=attendance_id, organization=org, member=member
            )
        except Attendance.DoesNotExist:
            return get_404_response("Attendance")

        if attendance.ot_status is None:
            return HTTP_400("OT doesn't found for attendance.")

        if attendance.ot_status != "ot_available":
            return HTTP_400(f"Attendance status is already {attendance.ot_status}.")

        attendance.ot_status = "ot_requested"
        attendance.remarks = remarks
        attendance.save()
        return HTTP_200({})
