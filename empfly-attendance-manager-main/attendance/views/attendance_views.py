from django.forms import BooleanField
from datetime import date, timedelta
from django.db import IntegrityError
from requests import request
from attendance.filters import filter_attendance, filter_my_attendance
from attendance.search import search_attendance
from organization.models import Organization, SystemLocation
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch

from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions
from attendance.models import MemberScan, Attendance, PresentByDefault
from attendance import serializers
from member.models import Member
from organization.serializers import OrganizationSerializer

from utils import read_data, fetch_data, create_data, email_funcs

from export.utils import create_export_request
from utils.create_data import add_first_and_last_check_in
import logging
from utils.response import HTTP_200, HTTP_400

from utils.utils import pagination


logger = logging.getLogger(__name__)


class AttendanceReportAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AttendanceSerializer2

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        filter_query = Q(organization=org)

        filter_status = request.GET.get("status", "active")
        if filter_status in ("active", "inactive"):
            filter_query &= Q(member__status=filter_status)

        attendance = Attendance.objects.filter(filter_query).prefetch_related(
            Prefetch(
                "scans",
                queryset=MemberScan.objects.filter(
                    organization=org
                ).select_related(
                    "system_location"
                ).order_by("date_time"),
            )
        ).select_related(
            "member",
            "member__user",
            "shift",
        )


        is_mobile = BooleanField().to_python(request.GET.get("is_mobile", "False"))

        print(f"is_mobile : {is_mobile}, type : {type(is_mobile)}")

        if is_mobile is True:                                # Mobile app only required logged in user only data
            attendance = attendance.filter(member=member)

        elif member.role.name not in ("admin", "hr"):        # Check for member is manager
            org_location_obj = member.org_location_head.all()
            department_obj = member.department_head.all()
            employees = member.members.all()

            if org_location_obj.exists() or department_obj.exists() or employees.exists():
                attendance = attendance.filter(
                    Q(member__org_location__in=org_location_obj) | Q(member__department__in=department_obj) | Q(member__manager=member)
                )
            else:                                            # Only curr member data will show
                attendance = attendance.filter(member=member)

        attendance = filter_attendance(attendance, request)
        attendance = search_attendance(attendance, request.GET.get("search"))

        if bool(request.GET.get("export_csv")) is True:

            # print(attendance)

            if not attendance.exists():
                return HTTP_400({}, {"message": "No data found for export csv."})

            attendance_ids = attendance.values_list("id", flat=True)
            export_request = create_export_request(member, "attendance", list(attendance_ids))
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        # print(attendance)
        page_obj, num_pages, page = pagination(attendance, request)
        serializer = self.serializer_class(
            page_obj.object_list,
            many=True,
            fields=[
                "date",
                "duration",
                "early_check_out",
                "late_check_in",
                "overtime",
                "ot_status",
                "status",
                "member",
                "scans",
                "shift",
                "late_check_out",
                "ot_verified_by",
                "remarks",
                "id"
            ]
        )

        res_data = serializer.data
        # res_data = add_first_and_last_check_in(res_data)
        return Response(
            {
                "data": res_data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )



class MyAttendanceReportAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AttendanceSerializer2

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        attendance = Attendance.objects.filter(
            organization=org, member=member
        ).prefetch_related(
            Prefetch(
                "scans",
                queryset=MemberScan.objects.filter(
                    organization=org, member=member
                ).select_related(
                    "system_location"
                ).order_by("date_time"),
            )
        ).select_related(
            "member",
            "member__user",
            "shift",
        )

        attendance = filter_my_attendance(attendance, request)
        attendance = search_attendance(attendance, request.GET.get("search"))

        page_obj, num_pages, page = pagination(attendance, request)
        serializer = self.serializer_class(
            page_obj.object_list,
            many=True,
            fields=[
                "date",
                "duration",
                "early_check_out",
                "late_check_in",
                "overtime",
                "ot_status",
                "status",
                "member",
                "scans",
                "shift",
                "late_check_out",
                "ot_verified_by",
                "remarks",
                "id"
            ]
        )

        res_data = serializer.data
        # res_data = add_first_and_last_check_in(res_data)
        return Response(
            {
                "data": res_data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class GetMyAttendanceObjAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.AttendanceSerializer2

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        try:
            attendance = Attendance.objects.get(
                organization=org, member=member, id=kwargs.get("id")
            )
        except Attendance.DoesNotExist:
            return HTTP_400("Attendance not found.")

        serializer = self.serializer_class(
            attendance,
            fields=[
                "ot_status",
                "status",
                "id"
            ]
        )

        return Response(
            {
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
