from member.models import Member
from organization.models import Department, Designation, OrgLocation, Organization
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from shift.models import Shift
from shift.serializers import LocationSettingsSerializer
from utils import fetch_data, read_data
from utils.response import HTTP_200, HTTP_400
from organization.serializers import DepartmentSerializer, DesignationSerializer, OrgLocationSerializer
from member.serializers import MinimalMemberSerializer

import logging

from utils.shift import assign_applicable_shift, get_affected_employees
logger = logging.getLogger(__name__)

class AllApplicabilitySettingsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = LocationSettingsSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        priorities = org.settings["applicability_settings_priority"]

        try:
            shift = kwargs["uuid"]
            shift = Shift.objects.get(uuid=shift)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        department = Department.objects.filter(shift=shift, organization=org)

        designation = Designation.objects.filter(shift=shift, organization=org)

        org_location = OrgLocation.objects.filter(shift=shift, organization=org)

        # members = Member.objects.filter(shift=shift, organization=org)

        datas = {
            "data":{
                "department": DepartmentSerializer(department, many=True).data,
                "designation": DesignationSerializer(designation, many=True).data,
                "org_location": OrgLocationSerializer(org_location, many=True).data,
                # "employee": MinimalMemberSerializer(members, many=True).data
            },
            "applicability_settings_priority":priorities
        }

        return HTTP_200(datas)

    # def post(self, request, *args, **kwargs):

    #     org_uuid = request.headers.get('organization-uuid')
    #     org = fetch_data.get_organization(request.user, org_uuid)
    #     member = fetch_data.get_member(request.user, org.uuid)

    #     if fetch_data.is_admin(member) is False:
    #         return read_data.get_403_response()

    #     try:
    #         shift = kwargs["uuid"]
    #         shift = Shift.objects.get(uuid=shift)
    #     except Shift.DoesNotExist:
    #         return read_data.get_404_response("Shift")

    #     department = request.data.get("department", ["93e408a5-dbb5-48e9-bb37-588a804fda0e"])
    #     designation = request.data.get("designation", [])
    #     org_location = request.data.get("org_location", [])
    #     # employee = request.data.get("employee", [])

    #     if not isinstance(department, list):
    #         return HTTP_400({}, {"message": "Department is required."})

    #     if not isinstance(designation, list):
    #         return HTTP_400({}, {"message": "Designation is required."})

    #     if not isinstance(org_location, list):
    #         return HTTP_400({}, {"message": "Organization Location is required."})

    #     all_null = not department and not designation and not org_location
    #     if all_null:
    #         return HTTP_200({})


    #     Department.objects.filter(
    #         uuid__in=department, organization=org
    #     ).update(shift=shift)

    #     Designation.objects.filter(
    #         uuid__in=designation, organization=org
    #     ).update(shift=shift)

    #     OrgLocation.objects.filter(
    #         uuid__in=org_location, organization=org
    #     ).update(shift=shift)

    #     members = Member.objects.filter(organization=org, status="active")
    #     members = get_affected_employees(members, department, designation, org_location)


    #     print(members, "%%%%%%%%%%%%5")

    #     assign_applicable_shift(members, org)

    #     return HTTP_200({})

    def put(self, request, *args, **kwargs):
        """ Instead assigning shift to each member using applicability settings
            we can assign member to a shift with the help department, designation and org location.
            Member came under this priority will assign the selected shift.
        """

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        priorities = org.settings["applicability_settings_priority"]

        try:
            shift = kwargs["uuid"]
            shift = Shift.objects.get(uuid=shift)
        except Shift.DoesNotExist:
            return read_data.get_404_response("Shift")

        if shift.status == "inactive":
            return HTTP_400({}, {"message": "Shift is inactive."})

        department = request.data.get("department", [])
        designation = request.data.get("designation", [])
        org_location = request.data.get("org_location", [])
        # employee = request.data.get("employee", [])

        if not isinstance(department, list):
            return HTTP_400({}, {"message": "Department is required."})

        if not isinstance(designation, list):
            return HTTP_400({}, {"message": "Designation is required."})

        if not isinstance(org_location, list):
            return HTTP_400({}, {"message": "Organization Location is required."})

        # if not isinstance(employee, list):
        #     return HTTP_400({}, {"message": "Employee is required."})

        # remove the give shift fk from all models
        Department.objects.filter(
            shift=shift, organization=org
        ).update(shift=None)

        Designation.objects.filter(
            shift=shift, organization=org
        ).update(shift=None)

        OrgLocation.objects.filter(
            shift=shift, organization=org
        ).update(shift=None)

        arr = [0 , 0, 0]

        for i in priorities:
            arr.insert(i["priority"], i["name"])

        # assign the give shift fk from all models
        if department:
            Department.objects.filter(
                uuid__in=department, organization=org
            ).update(shift=shift)

        if designation:
            Designation.objects.filter(
                uuid__in=designation, organization=org
            ).update(shift=shift)

        if org_location:
            OrgLocation.objects.filter(
                uuid__in=org_location, organization=org
            ).update(shift=shift)


        members = Member.objects.filter(organization=org, status="active")

        members = get_affected_employees(members, department, designation, org_location)

        assign_applicable_shift(members, org)

        return HTTP_200({})
