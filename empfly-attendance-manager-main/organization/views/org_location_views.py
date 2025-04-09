from functools import partial
from django.db import IntegrityError
from member.models import Member
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from utils.response import HTTP_200, HTTP_400
from api import permissions
from organization.models import OrgLocation
from organization import serializers, search
from organization.utils import get_org_location
from utils import read_data, fetch_data, create_data, email_funcs
from shift.models import Shift

import logging

from utils.utils import filter_qs_by_status


logger = logging.getLogger(__name__)


class AllOrgLocationsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrgLocationSerializer
    serializer_fields = ["name", "organization", "description", "status"]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)

        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        locations = org.org_locations.all()

        search_query = request.GET.get("search")
        locations = search.search_org_locations(locations, search_query)

        locations = filter_qs_by_status(request=request, qs=locations, default="active", choice=("active", "inactive"))

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)

        paginator = Paginator(locations, per_page)
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
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")
        loc_status = request.data.get("status")
        shift = request.data.get("shift")
        enable_visitation = request.data.get("enable_visitation", True)
        org_location_head_uuid = request.data.get("org_location_head_uuid", [])

        if shift:
            try:
                shift = Shift.objects.get(uuid=shift, organization=org)
            except Shift.DoesNotExist:
                return read_data.get_404_response("Shift")
        else:
            shift = None

        if not name:
            return HTTP_400({}, {"message": "Name is required."})

        if loc_status not in ("active", "inactive"):
            return HTTP_400({}, {"message": "Status must be active/inactive."})
        
        if isinstance(enable_visitation, bool) is False:
            return HTTP_400({}, {"message": "Enable visitation must be True/False."})

        if org.org_locations.all().filter(name=name).exists():
            return HTTP_400(
                {}, {"message": "Org Location with this name already exists."}
            )

        if isinstance(org_location_head_uuid, list) is False:
            return HTTP_400({}, {"message": "Org location uuid must be an array."})

        org_location_obj = []        
        if org_location_head_uuid:
            org_location_obj = Member.objects.filter(uuid__in=org_location_head_uuid)

        try:
            location = OrgLocation.objects.create(
                name=name,
                description=description,
                status=loc_status,
                organization=org,
                shift=shift,
                enable_visitation=enable_visitation
            )

            if org_location_obj:
                location.org_location_head.add(*org_location_obj)
                location.save()

        except Exception as err:
            print(err)
            return HTTP_400({}, {"message": "Unknown error occurred."})

        serializer = self.serializer_class(location)
        return HTTP_200(serializer.data)
        # return Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)


class OrgLocationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.OrgLocationSerializer
    serializer_fields = ["name", "organization", "description", "status"]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        location_uuid = self.kwargs.get("uuid")
        location = get_org_location(location_uuid)
        if location is None:
            return read_data.get_404_response("Organization Location")

        serializer = self.serializer_class(location)
        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        name = request.data.get("name")
        description = request.data.get("description")
        loc_status = request.data.get("status")
        shift = request.data.get("shift")
        enable_visitation = request.data.get("enable_visitation")
        org_location_head_uuid = request.data.get("org_location_head_uuid", [])

        if isinstance(enable_visitation, bool) is False:
            return HTTP_400({}, {"message": "Enable visitation must be True/False."})

        if shift:
            try:
                shift = Shift.objects.get(uuid=shift, organization=org)
            except Shift.DoesNotExist:
                return read_data.get_404_response("Shift")
        else:
            shift = None

        if not name:
            return HTTP_400({}, {"message": "Name is required."})

        if isinstance(loc_status, bool):
            return HTTP_400({}, {"message": "Status is required."})

        location_uuid = self.kwargs.get("uuid")
        try:
            location = org.org_locations.get(uuid=location_uuid)
        except (OrgLocation.DoesNotExist, ValidationError) as err:
            return read_data.get_404_response("Organization Location")

        if loc_status is False and org.default_org_location == location:
            return HTTP_400({}, {"message": "Org location is assigned as default org location in organization. Please unassign from organization for deactivate this org location."})

        if org.org_locations.all().exclude(id=location.id).filter(name=name).exists():
            return HTTP_400(
                {}, {"message": "Org Location with this name already exists."}
            )


        if isinstance(org_location_head_uuid, list) is False:
            return HTTP_400({}, {"message": "Org location uuid must be an array."})

        org_location_obj = []        
        if org_location_head_uuid:
            org_location_obj = Member.objects.filter(uuid__in=org_location_head_uuid)

 
        location.name = name
        location.description = description
        location.status = loc_status
        location.shift = shift
        location.enable_visitation = enable_visitation

        location.org_location_head.clear()
        if org_location_obj:
            location.org_location_head.add(*org_location_obj)

        location.save()

        serializer = self.serializer_class(location)
        return HTTP_200(serializer.data)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        location_uuid = self.kwargs.get("uuid")
        try:
            location = org.org_locations.get(uuid=location_uuid)
        except (OrgLocation.DoesNotExist, ValidationError) as err:
            return read_data.get_404_response("Organization Location")

        if org.default_org_location == location:
            return HTTP_400(
                {},
                {
                    "message": "Org default org location cannot be delete. Please unassign this Org Locaiton from Organization."
                },
            )

        location.delete()

        return Response(
            {"message": "Successfully deleted Organization Location"},
            status=status.HTTP_200_OK,
        )
