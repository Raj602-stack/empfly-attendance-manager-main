from asyncore import read

# import datetime
from typing import Union
from xml.dom import ValidationErr
# from export.utils import get_current_time
from member.models import Member
from member.serializers import MemberSerializer
from organization.models import Organization, SystemLocation
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.exceptions import EditShiftError
from shift.filters import filter_shift, filter_shift_schedule_log
from shift.serializers import (
    MinimalMemberSerializer,
    ShiftScheduleLogSerializer,
    ShiftSerializer,
)
from datetime import datetime, date, timedelta
from shift.shift_schedule_logic import (
    create_log_mapping,
    deactivate_shift,
    priority_analysis,
)
from shift.utils import is_shift_editable, validate_shift_status_changing
from shift.validations import shift_validation
from utils import fetch_data, read_data
from utils.date_time import curr_date_time_with_tz, curr_dt_with_org_tz
from utils.response import HTTP_200, HTTP_400
from shift.models import LocationSettings, Shift, ShiftScheduleLog
import logging
from django.db.models import ProtectedError
from django.db import IntegrityError
from shift.search import search_employee, search_shift, search_ssl_employees
from django.db.models import Prefetch
from django.db.models import Q
from utils.utils import convert_to_date, convert_to_time, pagination
from django.core.exceptions import ValidationError
from utils import date_time
from export.utils import create_export_request
from export import utils as export_utils
import calendar
from datetime import date


logger = logging.getLogger(__name__)


class AllShiftsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        # if fetch_data.is_admin_or_hr(member) is False:
        #     return read_data.get_403_response()

        shifts = Shift.objects.filter(organization=org)

        shift_status = request.GET.get("status", "active")
        if shift_status in ("active", "inactive"):
            shifts = shifts.filter(status=shift_status)

        shifts = search_shift(shifts, request.GET.get("search"))

        page_obj, num_pages, page = pagination(shifts, request)

        serializer = self.serializer_class(page_obj.object_list, many=True)

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

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        response_or_data = shift_validation(request, org)

        if isinstance(response_or_data, Response):
            return response_or_data
        validated_data = response_or_data

        validated_data["created_by"] = member
        validated_data["organization"] = org

        try:
            shift = Shift.objects.create(**validated_data)
        except IntegrityError:
            return HTTP_400(
                {}, {"message": "Shift with name already exists in this organization."}
            )

        serializer = ShiftSerializer(shift)
        return HTTP_200(serializer.data)


class ShiftsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            uuid = kwargs["uuid"]
            shift = Shift.objects.get(uuid=uuid)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        serializer = self.serializer_class(shift)
        return HTTP_200(serializer.data)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            shift = Shift.objects.get(uuid=kwargs["uuid"])
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        try:
            is_shift_editable(shift)
        except EditShiftError as err:
            return HTTP_400({}, {"message": err.error()})

        response_or_data = shift_validation(request, org)

        if isinstance(response_or_data, Response):
            return response_or_data
        validated_data = response_or_data

        name = validated_data.get("name")
        description = validated_data.get("description")
        start_time = validated_data.get("start_time")
        end_time = validated_data.get("end_time")
        computation_time = validated_data.get("computation_time")
        enable_geo_fencing = validated_data.get("enable_geo_fencing", True)
        skip_days = validated_data.get("skip_days")
        default_location = validated_data.get("default_location")

        present_working_hours = validated_data.get("present_working_hours")
        partial_working_hours = validated_data.get("partial_working_hours")

        shift_start_time_restriction = validated_data.get(
            "shift_start_time_restriction"
        )

        loc_settings_start_time_restriction = validated_data.get(
            "loc_settings_start_time_restriction", True
        )

        if enable_geo_fencing is True and not default_location:
            return HTTP_400({}, {"message": "Default Location is required."})

        if default_location and default_location !=  shift.default_location and default_location.status == "inactive":
            return HTTP_400({}, {"message": "Default Location is inactive."})

        shift.name = name
        shift.description = description
        shift.start_time = start_time
        shift.end_time = end_time
        shift.computation_time = computation_time
        shift.present_working_hours = present_working_hours
        shift.partial_working_hours = partial_working_hours
        shift.enable_geo_fencing = enable_geo_fencing
        shift.skip_days = skip_days
        shift.default_location = default_location
        shift.updated_by = member
        shift.shift_start_time_restriction = shift_start_time_restriction
        shift.loc_settings_start_time_restriction = loc_settings_start_time_restriction

        try:
            shift.save()
        except IntegrityError:
            return HTTP_400("Shift with name already exists in this organization.")

        serializer = ShiftSerializer(shift)

        return HTTP_200(serializer.data)


class ShiftCalendarAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = MinimalMemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        req_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(req_member) is False:
            return read_data.get_403_response()

        shift_start_date = request.GET.get("shift_start_date")
        shift_end_date = request.GET.get("shift_end_date")

        if not shift_start_date:
            return HTTP_400({}, {"message": "Start Date is required"})

        if not shift_end_date:
            return HTTP_400({}, {"message": "End Date is required"})

        logs_filter_query = Q(status="active", organization=org,)

        # if req_member.role.name == "member":
        #     logs_filter_query &= Q(employee=req_member)

        all_logs = ShiftScheduleLog.objects.filter(logs_filter_query).order_by("start_date")

        org_location_obj, department_obj = [], []

        if req_member.role.name == "member":

            org_location_obj = req_member.org_location_head.all()
            department_obj = req_member.department_head.all()

            if org_location_obj.exists() or department_obj.exists():
                all_logs = all_logs.filter(
                    Q(employee__org_location__in=org_location_obj) | Q(employee__department__in=department_obj)
                )
            else:
                # Only see his data
                all_logs = all_logs.filter(employee=req_member)

        all_employees = all_logs.values_list("employee__uuid", flat=True)
        all_employees = set(all_employees)
        print("######"*10)
        valid_ssl_ids = []
        print("all employees ====== ", all_employees)

        # Get all the employees weekly SSL.
        for employee in all_employees:
            employee_logs = all_logs.filter(employee__uuid=employee)

            head = employee_logs.filter(start_date__lte=shift_start_date, end_date__gte=shift_start_date)
            if head.first() is None:
                head = employee_logs.filter(start_date__lte=shift_start_date, end_date__isnull=True)

            tail = employee_logs.filter(start_date__lte=shift_end_date, end_date__gte=shift_end_date)
            if tail.first() is None:
                tail = employee_logs.filter(start_date__lte=shift_end_date, end_date__isnull=True)
            print("head : ",head)
            print("tail : ",tail)

            head_start_date = None
            if head.first():
                head_start_date = head.first().start_date

            tail_start_date = None
            if tail.first():
                tail_start_date = tail.first().start_date

            print("employee : ", employee)

            print("head_start_date : ",head_start_date)
            print("tail_start_date : ",tail_start_date)

            if head_start_date and tail_start_date:
                employee_selected_logs = employee_logs.filter(start_date__range=[head_start_date, tail_start_date])
                valid_ssl_ids = valid_ssl_ids + list(employee_selected_logs.values_list("id", flat=True))
                print("employee ids : ", employee_selected_logs.values_list("id", flat=True))

            elif head_start_date is None and tail_start_date:
                employee_selected_logs = employee_logs.filter(start_date__lte=tail_start_date)
                valid_ssl_ids = valid_ssl_ids + list(employee_selected_logs.values_list("id", flat=True))
                print("employee ids : ", employee_selected_logs.values_list("id", flat=True))

        all_logs = all_logs.filter(id__in=valid_ssl_ids)

        shift_uuid = request.GET.getlist("shift_uuid")
        members = Member.objects.filter(organization=org)

        filter_status = request.GET.get("status", "active")
        if filter_status in ("active", "inactive"):
            members = members.filter(status=filter_status)

        if shift_uuid:
            logs = all_logs.filter(Q(shift__uuid__in=shift_uuid))
            members = members.filter(id__in=logs.values_list("employee__id"))

        members = members.prefetch_related(
            Prefetch(
                "shift_schedule_logs",
                queryset=all_logs.order_by("start_date"),
            )
        )

        print(req_member.role, "#@@@@@@@@@@@@@"*5)
        if req_member.role.name == "member":
            if org_location_obj or department_obj:
                members = members.filter(Q(org_location__in=org_location_obj) | Q(department__in=department_obj))
            else:
                members = members.filter(uuid=req_member.uuid)

        print(members)
        members = filter_shift(members, request)
        members = search_ssl_employees(members, request.GET.get("search"))

        if bool(request.GET.get("export_csv")) is True:
            if not members.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            members_ids = export_utils.get_uuid_from_qs(members)

            filters_for_export = {
                "shift_start_date": shift_start_date,
                "shift_end_date": shift_end_date,
            }

            export_request = create_export_request(req_member, "shift_calendar", members_ids, filters_for_export)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(members, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class EmployeeShiftMappingAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = MemberSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        # if fetch_data.is_admin_or_hr(member) is False:
        #     return read_data.get_403_response()

            

        try:
            month = int(request.GET.get("month"))
            if not (month >= 1 and month <= 12):
                raise ValueError
        except:
            return HTTP_400({}, {"message": "Month is not valid."})

        try:
            year = int(request.GET.get("year"))
        except:
            return HTTP_400({}, {"message": "Year is not valid."})

        if isinstance(year, int) is False:
            return HTTP_400({}, {"message": "Year must be Integer."})

        last_day = calendar.monthrange(year, month)[1]

        date_obj = date(year, month, last_day)

        all_logs = ShiftScheduleLog.objects.filter(
            organization=org,
            start_date__lte=date_obj
            # start_date__month__lte=month,
            # start_date__year__lte=year,
        ).order_by("start_date")

        org_location_obj, department_obj = [], []

        if member.role.name == "member":
            org_location_obj = member.org_location_head.all()
            department_obj = member.department_head.all()

            if org_location_obj.exists() or department_obj.exists():
                all_logs = all_logs.filter(
                    Q(employee__org_location__in=org_location_obj) | Q(employee__department__in=department_obj)
                )
            else:
                # Only see his data
                all_logs = all_logs.filter(employee=member)


        log_status = request.GET.get("status", "active")
        if log_status in ("active", "inactive"):
            all_logs = all_logs.filter(status=log_status)

        all_logs = filter_shift_schedule_log(all_logs, request)

        all_logs = all_logs.filter(
            Q(end_date__isnull=True)
            | Q(end_date__month__gte=month, end_date__year__gte=year)
        )

        members = Member.objects.filter(organization=org).prefetch_related(
            Prefetch(
                "shift_schedule_logs",
                queryset=all_logs.order_by("start_date"),
            )
        )

        if member.role.name == "member":
            if org_location_obj or department_obj:
                members = members.filter(Q(org_location__in=org_location_obj) | Q(department__in=department_obj))
            else:
                members = members.filter(user=member.user)


        filter_status = request.GET.get("status", "active")
        if filter_status in ("active", "inactive"):
            members = members.filter(status=filter_status)

        members = filter_shift(members, request)
        search_query = request.GET.get("search")
        members = search_employee(members, search_query)

        page_obj, num_pages, page = pagination(members, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)
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

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        shift = request.data.get("shift")
        employees = request.data.get("employees")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        if not shift:
            return HTTP_400({}, {"message": "Shift is required."})

        if not employees:
            return HTTP_400({}, {"message": "employees is required."})

        if not start_date:
            return HTTP_400({}, {"message": "start_date is required."})

        if isinstance(employees, list) is False:
            return HTTP_400({}, {"message": "Employees must be a array."})

        start_date, is_valid = convert_to_date(start_date)
        if is_valid is False:
            return HTTP_400({}, {"message": "Start Date is not valid."})

        if end_date:
            end_date, is_valid = convert_to_date(end_date)
            if is_valid is False:
                return HTTP_400({}, {"message": "End Date is not valid."})

            if start_date > end_date:
                return HTTP_400({}, {"message": "Start date cannot be greater than end date."})

        try:
            shift = Shift.objects.get(uuid=shift)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        if shift.status == "inactive":
            return HTTP_400({}, {"message": "Shift is deactivated."})

        print(start_date, end_date, "-----------*********************")

        employees = Member.objects.filter(uuid__in=employees, status="active")

        # Modify shift schedule log of members.
        for employee in employees:
            create_log_mapping(shift, employee, start_date, end_date)

        return HTTP_200({})


class AllEmployeeShiftMappingAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftScheduleLogSerializer

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        uuid = kwargs["uuid"]

        try:
            log = ShiftScheduleLog.objects.get(uuid=uuid)
        except ShiftScheduleLog.DoesNotExist:
            return read_data.get_404_response("Shift Schedule Log")

        if log.status == "inactive":
            log.delete()
            return HTTP_200({})

        employee = log.employee

        start_date = log.start_date
        end_date = log.end_date

        today = date_time.today_date()

        if end_date and end_date < today:
            return HTTP_400({}, {"message": "Past records can't delete."})

        if start_date >= today:
            shift = priority_analysis(employee)

            print("===========", shift)
            if not shift:
                shift = employee.organization.default_shift
            if not shift:
                return HTTP_400({}, {"message": "Shift not found."})

            print("------------------------", shift, "----------------------")

            # delete and assign new shift
            ShiftScheduleLog.objects.create(
                start_date=start_date,
                end_date=end_date,
                shift=shift,
                is_esm=False,
                organization=org,
                employee=employee,
            )

            log.delete()

        elif start_date < today and (
            end_date is None or end_date and end_date >= today
        ):

            during_shift = priority_analysis(employee)
            print("----------during_shift", during_shift)
            if not during_shift:
                during_shift = employee.organization.default_shift
            if not during_shift:
                return HTTP_400({}, {"message": "Shift not found."})

            print("----------final", during_shift)

            # split upto yesterday
            before_start_date = start_date
            before_end_date = today - timedelta(days=1)
            before_shift = log.shift
            before_is_esm = log.is_esm

            print(before_start_date)
            print(before_end_date)
            print(before_shift)
            print(before_is_esm)

            employee = log.employee

            ShiftScheduleLog.objects.create(
                start_date=before_start_date,
                end_date=before_end_date,
                shift=before_shift,
                is_esm=before_is_esm,
                organization=org,
                employee=employee,
            )

            during_start_date = today
            during_end_date = log.end_date

            print(during_start_date)
            print(during_end_date)
            print(during_shift)

            ShiftScheduleLog.objects.create(
                start_date=during_start_date,
                end_date=during_end_date,
                shift=during_shift,
                is_esm=False,
                organization=org,
                employee=employee,
            )

            log.delete()

        return HTTP_200({})


class DeActivateShiftAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftSerializer

    def put(self, request, *args, **kwargs):
        """ Alternate shift will replace in place of deactivated shift.
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        alternative_shift = request.data.get("alternative_shift")
        shift = request.data.get("shift")

        if not alternative_shift:
            return HTTP_400({}, {"message": "Alternative shift is required."})

        if not shift:
            return HTTP_400({}, {"message": "Shift is required."})

        all_shifts = Shift.objects.filter(default_location__organization=org)

        try:
            alternative_shift = all_shifts.get(uuid=alternative_shift)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Alternative Shift")

        if alternative_shift.status == "inactive":
            return HTTP_400({}, {"message": "Alternative Shift is inactive."})

        try:
            shift = all_shifts.get(uuid=shift)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        if org.default_shift == shift:
            return HTTP_400({}, {"message": "Shift assigned as default shift in organization. Please unassign this Shift from Organization."})

        logs = ShiftScheduleLog.objects.filter(
            organization=org, status="active", shift=shift
        )

        date_time = curr_dt_with_org_tz()
        today = date_time.today()
        # now = datetime.now().time()

        employees = Member.objects.filter(
            id__in=logs.values_list("employee__id").distinct()
        )

        logs = logs.filter(start_date__gte=today, shift=shift)
        for member in employees:

            # my_date = create_log_for_deactivate(shift, member, alternative_shift)
            deactivate_start_date = deactivate_shift(shift, member, alternative_shift)

            print("---------- Date : ", deactivate_start_date, "-----------------")

            logs_for_update = ShiftScheduleLog.objects.filter(
                start_date__gte=deactivate_start_date,
                employee=member,
                organization=org,
                status="active",
                shift=shift,
            )

            for curr_log in logs_for_update:
                curr_log.location_settings.clear()

            logs_for_update.update(shift=alternative_shift)

        shift.status = "inactive"
        shift.save()

        return HTTP_200({})


class EmployeeShiftScheduleLogAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftScheduleLogSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        req_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(req_member) is False:
            return read_data.get_403_response()

        uuid = kwargs["uuid"]
        try:
            member = Member.objects.get(uuid=uuid, organization=org)
        except Member.DoesNotExist:
            return read_data.get_404_response("Member")

        logs = ShiftScheduleLog.objects.filter(
            employee=member,
            organization=org
        )

        log_status = request.GET.get("status", "active")
        if log_status in ("active", "inactive"):
            logs = logs.filter(status=log_status)

        page_obj, num_pages, page = pagination(logs, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )



class ActivateShiftAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ShiftSerializer

    def patch(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            shift = Shift.objects.get(organization=org, uuid=kwargs["uuid"])
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        shift.status="active"
        shift.save()

        serializer = self.serializer_class( shift )
        return HTTP_200(serializer.data)
