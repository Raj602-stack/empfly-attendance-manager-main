import organization
from organization.filters import filter_holidays
from utils.date_time import curr_dt_with_org_tz
import zoneinfo

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404
from export.utils import create_export_request
from member.models import Member

# import organization
from organization.search import search_department, search_designation, search_holidays
from organization.validations import holiday_validations, organization_validations

from shift.models import Shift
from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db import IntegrityError

from organization.models import (
    CostCenter,
    Department,
    Designation,
    Holiday,
    OrgLocation,
    Organization,
    Role,
)
from export import utils as export_utils


from organization import serializers
from organization.utils import (
    get_department,
    get_designation,
    get_cost_center,
    get_holiday,
)

from api import permissions
from utils import create_data, email_funcs, fetch_data, read_data

import csv
import pandas as pd
import logging
from utils.response import HTTP_200, HTTP_400

from utils.utils import convert_to_date, filter_qs_by_is_active, pagination

logger = logging.getLogger(__name__)


# class OrganizationAPI(views.APIView):

#     permission_classes = [permissions.IsTokenAuthenticated]
#     serializer_class = serializers.OrganizationSerializer

#     def get(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)

#         serializer = self.serializer_class(org)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def put(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         logo = request.data.get("logo")
#         name = request.data.get("name", org.name)
#         description = request.data.get("description", org.description)
#         city_uuid = request.data.get("city_uuid")
#         address = request.data.get("address", org.address)
#         organization_email = request.data.get(
#             "organization_email", org.organization_email
#         )
#         timezone = request.data.get("timezone", org.timezone)
#         settings = request.data.get("settings", org.settings)

#         if city_uuid:
#             city = get_city(city_uuid)
#             if city is None:
#                 return read_data.get_404_response("city")

#         org.logo = logo
#         org.name = name
#         org.namdescriptione = description
#         if city_uuid:
#             org.city = city
#         org.address = address
#         org.organization_email = organization_email
#         org.timezone = timezone
#         org.settings = settings
#         org.save()

#         serializer = self.serializer_class(org)
#         return Response(serializer.data, status=status.HTTP_200_OK)

#     def delete(self, request, *args, **kwargs):

#         org_uuid = request.headers.get("organization-uuid")
#         org = fetch_data.get_organization(request.user, org_uuid)
#         member = fetch_data.get_member(request.user, org.uuid)

#         if fetch_data.is_admin(member) is False:
#             return read_data.get_403_response()

#         org.delete()
#         return Response(
#             {"message": "Successfully delete organization"}, status=status.HTTP_200_OK
#         )


class OrganizationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(org)
        return HTTP_200(serializer.data)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()
        print(request.data)

        try:
            data = organization_validations(request, org)
        except ValidationError as err:
            return HTTP_400({}, {"message": err.message})

        logo = data.get("logo")
        name = data.get("name")
        description = data.get("description")
        location = data.get("location")
        organization_email = data.get("organization_email")
        timezone = data.get("timezone", "UTC")

        org.logo = logo
        org.name = name
        org.location = location
        org.description = description
        org.organization_email = organization_email
        org.timezone = timezone
        org.save()
        # org.address = address
        # org.domain = domain

        # set timezone in session
        # request.session["django_timezone"] = timezone

        serializer = self.serializer_class(org)
        return HTTP_200(serializer.data)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        org.delete()
        return HTTP_200({"message": "Successfully delete organization"})


class RolesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RoleSerializer

    def get(self, request, *args, **kwargs):

        roles = Role.objects.filter(~Q(name="visitor"))
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(roles, per_page)
        page_obj = paginator.get_page(page)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class AllDepartmentsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        departments = org.departments.all()

        search_query = request.GET.get("search")
        departments = search_department(departments, search_query)
        # departments = filter_qs_by_is_active(request, departments, True)

        departments = filter_qs_by_is_active(
            request=request, qs=departments, default=True, choice=(True, False)
        )

        if bool(request.GET.get("export_csv")) is True:

            if not departments.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            departments_ids = export_utils.get_uuid_from_qs(departments)

            export_request = create_export_request(member, "departments", departments_ids)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(departments, request)

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

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        name = str(request.data.get("name")).strip()
        description = str(request.data.get("description")).strip()
        is_active = request.data.get("is_active")
        department_head_uuid = request.data.get("department_head_uuid", [])
        shift = request.data.get("shift")

        if shift:
            try:
                shift = Shift.objects.get(uuid=shift, organization=org)
            except Shift.DoesNotExist:
                return read_data.get_404_response("Shift")
        else:
            shift = None

        if not name:
            return Response(
                {
                    "message": "Name field is required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # if not department_head_uuid:
        #     return HTTP_400({}, {"message": "Department head is required."})

        if isinstance(department_head_uuid, list) is False:
            return HTTP_400({}, {"message": "Department head uuid must be an array."})
        

        department_head_obj = []
        if department_head_uuid:
            department_head_obj = Member.objects.filter(uuid__in=department_head_uuid)

        # if Department.objects.filter(
        #     organization=org, department_head__uuid=department_head_uuid
        # ).exists():
        #     return read_data.get_409_response("Department", "department head")

        # try:
        #     department_head = Member.objects.get(
        #         uuid=department_head_uuid, organization=org
        #     )
        # except Member.DoesNotExist:
        #     return read_data.get_404_response("Department Head")

        # if department_head.status == "inactive":
        #     return HTTP_400({}, {"message": "Department Head is inactive."})

        try:
            department = Department.objects.create(
                organization=org,
                name=name,
                description=description,
                created_by=member,
                is_active=is_active,
                shift=shift
            )

            if department_head_obj:
                department.department_head.add(*department_head_obj)
                department.save()

        except IntegrityError as e:
            print("============")
            print(e)
            print("============")
            return read_data.get_409_response("Department", "name")
        except Exception as e:
            print("=================", e)
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllDepartmentsAPI"
            )
            print("=================")

        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DepartmentAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DepartmentSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org.uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org.uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        name = request.data.get("name", department.name)
        description = request.data.get("description", department.description)
        is_active = request.data.get("is_active", department.is_active)
        shift = request.data.get("shift")

        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift:
            try:
                shift = Shift.objects.get(uuid=shift, organization=org)
            except Shift.DoesNotExist:
                return read_data.get_404_response("Shift")
        else:
            shift = None

        if name == "":
            return Response(
                {
                    "message": "Name field is required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        department_head_uuid = request.data.get("department_head_uuid", [])

        if isinstance(department_head_uuid, list) is False:
            return HTTP_400({}, {"message": "Department head uuid must be an array."})
        
        department_head_obj = []
        if department_head_uuid:
            department_head_obj = Member.objects.filter(uuid__in=department_head_uuid)


        # if not department_head_uuid:
        #     return HTTP_400({}, {"message": "Deaprtment Head not found."})

        # if (
        #     Department.objects.filter(
        #         organization=org, department_head__uuid=department_head_uuid
        #     )
        #     .exclude(id=department.id)
        #     .exists()
        # ):
        #     return read_data.get_409_response("Department", "department head")

        # try:
        #     department_head = Member.objects.get(
        #         uuid=department_head_uuid, organization=org
        #     )
        # except Member.DoesNotExist:
        #     return read_data.get_404_response("Department")

        # if (
        #     department.department_head != department_head
        #     and department_head.status == "inactive"
        # ):
        #     return HTTP_400({}, {"message": "Department Head is inactive."})

        print(department_head_obj)

        try:
            department.name = name
            department.description = description
            department.is_active = is_active
            
            department.department_head.clear()
            if department_head_obj:
                department.department_head.add(*department_head_obj)

            department.shift = shift
            department.save()
        except IntegrityError as err:
            return read_data.get_409_response("Department", "name")

        serializer = self.serializer_class(department)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org.uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        try:
            department.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Department is assigned to a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted department"}, status=status.HTTP_200_OK
        )


class AllCostCentersAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.CostCenterSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org.uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        cost_centers = department.cost_centers.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(cost_centers, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        department_uuid = self.kwargs.get("uuid")
        department = get_department(org.uuid, department_uuid)
        if department is None:
            return read_data.get_404_response("Department")

        name = request.data.get("name")
        description = request.data.get("description")

        try:
            cost_center = CostCenter.objects.create(
                department=department,
                name=name,
                description=description,
                created_by=member,
            )
        except IntegrityError as e:
            return read_data.get_409_response("Cost Center", "name")

        serializer = self.serializer_class(cost_center)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CostCenterAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.CostCenterSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        cost_center_uuid = self.kwargs.get("uuid")
        cost_center = get_cost_center(org.uuid, cost_center_uuid)
        if cost_center is None:
            return read_data.get_404_response("Cost Center")

        serializer = self.serializer_class(cost_center)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        cost_center_uuid = self.kwargs.get("uuid")
        cost_center = get_cost_center(org.uuid, cost_center_uuid)
        if cost_center is None:
            return read_data.get_404_response("Cost Center")

        name = request.data.get("name", cost_center.name)
        description = request.data.get("description", cost_center.description)
        is_active = request.data.get("is_active", cost_center.is_active)
        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cost_center.name = name
        cost_center.description = description
        cost_center.is_active = is_active
        cost_center.save()

        serializer = self.serializer_class(cost_center)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        cost_center_uuid = self.kwargs.get("uuid")
        cost_center = get_cost_center(org.uuid, cost_center_uuid)
        if cost_center is None:
            return read_data.get_404_response("Cost Center")

        cost_center.delete()

        return Response(
            {"message": "Successfully deleted cost center"}, status=status.HTTP_200_OK
        )


class AllDesignationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DesignationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        designations = org.designations.all()
        search_query = request.GET.get("search")
        designations = search_designation(designations, search_query)
        # designations = filter_designation(designations, request)
        designations = filter_qs_by_is_active(
            request=request, qs=designations, default=True, choice=(True, False)
        )

        # designations = filter_qs_by_is_active(request, designations, True)

        if bool(request.GET.get("export_csv")) is True:
            designations_ids = designations.values_list("id", flat=True)
            export_request = create_export_request(
                member, "designation", list(designations_ids)
            )
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(designations, request)

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

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        name = request.data.get("name").strip()
        description = request.data.get("description")
        is_active = request.data.get("is_active")
        shift = request.data.get("shift")

        if shift:
            try:
                shift = Shift.objects.get(uuid=shift, organization=org)
            except Shift.DoesNotExist:
                return read_data.get_404_response("Shift")
        else:
            shift = None

        if name == "":
            return HTTP_400({}, {"message": "Enter a valid name"})

        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            designation = Designation.objects.create(
                organization=org,
                name=name,
                description=description,
                created_by=member,
                is_active=is_active,
                shift=shift
            )
        except IntegrityError as e:
            return read_data.get_409_response("Designation", "name")

        serializer = self.serializer_class(designation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DesignationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.DesignationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        designation_uuid = self.kwargs.get("uuid")
        designation = get_designation(org.uuid, designation_uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        serializer = self.serializer_class(designation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        designation_uuid = self.kwargs.get("uuid")
        designation = get_designation(org.uuid, designation_uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        name = request.data.get("name", designation.name).strip()
        description = request.data.get("description", designation.description)
        is_active = request.data.get("is_active", designation.is_active)
        shift = request.data.get("shift")

        if shift:
            try:
                shift = Shift.objects.get(uuid=shift, organization=org)
            except Shift.DoesNotExist:
                return read_data.get_404_response("Shift")
        else:
            shift = None

        

        if name == "":
            return HTTP_400({}, {"message": "Enter a valid name"})

        if isinstance(is_active, bool) is False:
            return Response(
                {"message": "Status should be true/false"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        designation.name = name
        designation.description = description
        designation.is_active = is_active
        designation.shift = shift

        designation.save()

        serializer = self.serializer_class(designation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        designation_uuid = self.kwargs.get("uuid")
        designation = get_designation(org.uuid, designation_uuid)
        if designation is None:
            return read_data.get_404_response("Designation")

        try:
            designation.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Designation is assigned to a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted designation"}, status=status.HTTP_200_OK
        )


class AllHolidaysListAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.HolidaySerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        holidays = org.holidays.all()

        filtering_status = request.GET.get("status", "active")

        filtering_status = {"active": True, "inactive": False}.get(filtering_status)

        if isinstance(filtering_status, bool):
            holidays = holidays.filter(is_active=filtering_status)

        holidays = filter_holidays(holidays, request)
        holidays = search_holidays(holidays, request.GET.get("search"))

        if bool(request.GET.get("export_csv")) is True:
            if not holidays.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            cluster_uuds = list(holidays.values_list("uuid", flat=True))
            cluster_uuds = [str(uuid) for uuid in cluster_uuds]
            export_request = create_export_request(member, "holidays", cluster_uuds)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(holidays, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class AllHolidaysAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.HolidaySerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        holidays = org.holidays.all()

        lookup = Q(org_location__isnull=True)
        if member.org_location:
            lookup |= Q(org_location=member.org_location)

        curr_dt = curr_dt_with_org_tz()
        lookup &= Q(date__gte=curr_dt.date())
        holidays = holidays.filter(lookup)

        filtering_status = request.GET.get("status", "active")

        filtering_status = {"active": True, "inactive": False}.get(filtering_status)

        if isinstance(filtering_status, bool):
            holidays = holidays.filter(is_active=filtering_status)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(holidays, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        try:
            validated_data = holiday_validations(request, org)
        except ValidationError as err:
            return HTTP_400({}, {"message": err.message})

        print(validated_data)
        org_location = validated_data.get("org_location")
        if org_location and org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org location is inactive."})

        validated_data["created_by"] = member

        date = validated_data["date"]
        if date <= curr_dt_with_org_tz().date():
            return HTTP_400({}, {"message": "Date must be greater than today."})

        try:
            holiday = Holiday.objects.create(**validated_data)
        except IntegrityError as err:
            print("Holiday Error : ", err)
            return read_data.get_409_response("Holiday", "name")

        serializer = self.serializer_class(holiday)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HolidayAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.HolidaySerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        holiday_uuid = self.kwargs.get("uuid")
        holiday = get_holiday(org.uuid, holiday_uuid)
        if holiday is None:
            return read_data.get_404_response("Holiday")

        serializer = self.serializer_class(holiday)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        holiday_uuid = self.kwargs.get("uuid")
        holiday = get_holiday(org.uuid, holiday_uuid)
        if holiday is None:
            return read_data.get_404_response("Holiday")

        try:
            validated_data = holiday_validations(request, org)
        except ValidationError as err:
            return HTTP_400({}, {"message": err.message})

        org_location = validated_data.get("org_location")

        if (
            org_location
            and holiday.org_location != org_location
            and org_location.status == "inactive"
        ):
            return HTTP_400({}, {"message": "Org location is active."})

        validated_data["updated_by"] = member

        date = validated_data["date"]
        if date != holiday.date and date <= curr_dt_with_org_tz().date():
            return HTTP_400({}, {"message": "Date must be greater than today."})

        for key, value in validated_data.items():
            setattr(holiday, key, value)

        holiday.save()

        serializer = self.serializer_class(holiday)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        holiday_uuid = self.kwargs.get("uuid")
        holiday = get_holiday(org.uuid, holiday_uuid)
        if holiday is None:
            return read_data.get_404_response("Holiday")

        try:
            holiday.delete()
        except ProtectedError as e:
            logger.error(e)
            return Response(
                {"message": "Holiday is assigned to a member"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Successfully deleted holiday"}, status=status.HTTP_200_OK
        )


# TODO Update this
class HolidaysUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.HolidaySerializer

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization2(request.user)
        org.uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        csv_file = request.data.get("csv_file")

        try:
            df = pd.read_csv(csv_file, encoding="ISO-8859-1")
            df = df.where(pd.notnull(df), None)
            # Replaces nan values with empty string
            df = df.fillna("")
        except UnicodeDecodeError as e:
            logger.error(e)
            return Response(
                {"message": "Failed to load CSV file"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__}"
                " in HolidaysUploadCSVAPI > read_csv"
            )
            return Response(
                {"message": "Failed to load CSV file"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        added_holidays_count = 0
        failed_holidays = []

        for row in df.values:
            try:
                name = row[0]
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in LocationsUploadCSVAPI"
                )
                failed_holidays.append(
                    {
                        "name": "",
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )
                continue

            try:
                Holiday.objects.create(
                    organization=org,
                    name=name,
                    description=row[1],
                    date=row[2],
                    is_recurring=row[3],
                )
                added_holidays_count += 1
            except IntegrityError as e:
                detailed_reason = "Location with name already exists"
                failed_holidays.append(
                    {
                        "name": name,
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": detailed_reason,
                    }
                )
            except Exception as e:
                logger.error(e)
                logger.exception(
                    f"Add exception for {e.__class__.__name__} in LocationsUploadCSVAPI"
                )
                failed_holidays.append(
                    {
                        "name": name,
                        "reason": str(e.__class__.__name__),
                        "detailed_reason": str(e),
                    }
                )

        return Response(
            {
                "added_holidays_count": added_holidays_count,
                "failed_locations": failed_holidays,
            },
            status=status.HTTP_201_CREATED,
        )


class ApplicabilitySettingsPriorityAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        applicability_settings_priority = org.settings[
            "applicability_settings_priority"
        ]
        return HTTP_200(applicability_settings_priority)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        applicability_settings_priority = request.data.get(
            "applicability_settings_priority"
        )

        RES_400 = HTTP_400(
            {}, {"message": "Applicability Settings Priority is not valid."}
        )

        if isinstance(applicability_settings_priority, list) is False:
            return RES_400

        if len(applicability_settings_priority) != 3:
            return RES_400

        if applicability_settings_priority:
            org.settings[
                "applicability_settings_priority"
            ] = applicability_settings_priority
            org.save()

        return HTTP_200(
            {"applicability_settings": org.settings["applicability_settings_priority"]}
        )


class OrganizationVisitorManagementSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    # def get(self, request, *args, **kwargs):

    #     org_uuid = request.headers.get("organization-uuid")
    #     org = fetch_data.get_organization(request.user, org_uuid)
    #     member = fetch_data.get_member(request.user, org.uuid)

    #     if fetch_data.is_admin(member) is False:
    #         return read_data.get_403_response()

    #     serializer = self.serializer_class(org)
    #     return HTTP_200(serializer.data)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        org_settings = org.settings

        otp_expiry = request.data.get("otp_expiry")
        host_confirmation = request.data.get(
            "host_confirmation", org_settings.get("host_confirmation")
        )
        temperature_integration = request.data.get(
            "temperature_integration", org_settings.get("temperature_integration")
        )
        allow_non_invited_visitors = request.data.get(
            "allow_non_invited_visitors",
            org_settings.get("visitor_management_settings").get(
                "allow_non_invited_visitors"
            ),
        )

        if not otp_expiry:
            return HTTP_400({}, {"message": "Otp Expiry time is required."})

        if isinstance(otp_expiry, int) is False:
            return HTTP_400({}, {"message": "Otp Expiry time must be a integer value."})

        if isinstance(host_confirmation, bool) is False:
            return HTTP_400(
                {}, {"message": "Host confirmation value must be true/false."}
            )

        if isinstance(temperature_integration, bool) is False:
            return HTTP_400(
                {}, {"message": "Temperature Integration value must be true/false."}
            )

        if isinstance(allow_non_invited_visitors, bool) is False:
            return HTTP_400(
                {}, {"message": "Temperature Integration value must be true/false."}
            )

        org_settings["otp_expiry"] = otp_expiry
        org_settings["host_confirmation"] = host_confirmation
        org_settings["temperature_integration"] = temperature_integration
        org_settings["visitor_management_settings"][
            "allow_non_invited_visitors"
        ] = allow_non_invited_visitors

        org.settings = org_settings
        org.save()

        serializer = self.serializer_class(org)
        return HTTP_200(serializer.data)


class OrganizationShiftManagementSettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class(org)
        return HTTP_200(serializer.data)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        enable_geo_fencing = request.data.get("enable_geo_fencing")
        enable_face_rec = request.data.get("enable_face_rec")
        max_loc_settings_count = request.data.get("max_loc_settings_count")
        default_shift = request.data.get("default_shift")
        ot_approval = request.data.get("ot_approval", False)
        automated_ot_approval = request.data.get("automated_ot_approval", False)

        if not max_loc_settings_count:
            return HTTP_400({}, {"message": "Max location settings count is required"})
        if isinstance(max_loc_settings_count, int) is False:
            return HTTP_400(
                {}, {"message": "Max location settings count must be integer."}
            )

        if not default_shift:
            return HTTP_400({}, {"message": "Default Shift is required"})

        try:
            default_shift = Shift.objects.get(uuid=default_shift)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        org.default_shift = default_shift
        shift_management_settings = org.shift_management_settings

        if isinstance(enable_geo_fencing, bool) is False:
            return HTTP_400(
                {}, {"message": "Enable Geo fencing must be a booleans value."}
            )

        if isinstance(enable_face_rec, bool) is False:
            return HTTP_400(
                {}, {"message": "Enable Face Rec must be a booleans value."}
            )

        if isinstance(ot_approval, bool) is False:
            return HTTP_400(
                {}, {"message": "OT approval must be a booleans value."}
            )

        if isinstance(automated_ot_approval, bool) is False:
            return HTTP_400(
                {}, {"message": "Automated OT approval must be a booleans value."}
            )

        shift_management_settings["enable_geo_fencing"] = enable_geo_fencing
        shift_management_settings["enable_face_recognition"] = True
        shift_management_settings["automated_ot_approval"] = automated_ot_approval
        # shift_management_settings["enable_face_recognition"] = enable_face_rec

        shift_management_settings["location_settings"][
            "max_location_settings_count"
        ] = max_loc_settings_count
        shift_management_settings["ot_approval"] = ot_approval

        org.save()

        serializer = self.serializer_class(org)
        return HTTP_200(serializer.data)


class TimeZonesAPIView(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, format=None):
        """
        Return a list of all timezones.
        """
        timezones = zoneinfo.available_timezones()
        return Response(timezones)


class OrgKioskManagementAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrganizationSerializer

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        dit_expiry = request.data.get(
            "dit_expiry", org.kiosk_management_settings["dit_expiry"]
        )
        if type(dit_expiry) not in (float, int):
            return HTTP_400(
                {},
                {"message": f"dit expiry type cannot be {type(dit_expiry).__name__}."},
            )

        org.kiosk_management_settings["dit_expiry"] = dit_expiry
        org.save()

        serializer = self.serializer_class(org)
        return HTTP_200(serializer.data)
