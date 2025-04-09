from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions
from leave.models import RegularizationWorkflow
from leave import serializers
from leave.utils import get_regularization_workflow
from member.models import Member
from organization.models import Department, Designation, OrgLocation, Role
from utils import read_data, fetch_data

import logging


logger = logging.getLogger(__name__)


class AllRegularizationWorkflowsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RegularizationWorkflowSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        reg_workflows = org.regularization_workflows.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(reg_workflows, per_page)
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

        name = request.data.get("name")
        description = request.data.get("description")
        criteria = request.data.get("criteria")
        approval_types = request.data.get("approval_types")
        exceptions = request.data.get("exceptions")

        reg_workflow = RegularizationWorkflow.objects.create(
            name=name,
            description=description,
            organization=org,
            criteria=criteria,
            approval_types=approval_types,
            exceptions=exceptions,
            created_by=member,
        )

        serializer = self.serializer_class(reg_workflow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RegularizationWorkflowAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RegularizationWorkflowSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        reg_workflow = get_regularization_workflow(org.uuid, uuid)
        if reg_workflow is None:
            return read_data.get_404_response("Regularization Workflow")

        serializer = self.serializer_class(reg_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role != fetch_data.get_admin_role():
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        reg_workflow = get_regularization_workflow(org.uuid, uuid)
        if reg_workflow is None:
            return read_data.get_404_response("Regularization Workflow")

        name = request.data.get("name", reg_workflow.name)
        description = request.data.get("description", reg_workflow.description)
        criteria = request.data.get("criteria", reg_workflow.criteria)
        approval_types = request.data.get("approval_types", reg_workflow.approval_types)
        exceptions = request.data.get("exceptions", reg_workflow.exceptions)

        reg_workflow.name = name
        reg_workflow.description = description
        reg_workflow.criteria = criteria
        reg_workflow.approval_types = approval_types
        reg_workflow.exceptions = exceptions
        reg_workflow.save()

        serializer = self.serializer_class(reg_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role != fetch_data.get_admin_role():
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        reg_workflow = get_regularization_workflow(org.uuid, uuid)
        if reg_workflow is None:
            return read_data.get_404_response("Regularization Workflow")

        reg_workflow.delete()
        return read_data.get_200_delete_response("Regularization Workflow")


class AssignRegularizationWorkflowAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.RegularizationWorkflowSerializer

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        regularization_workflow = get_regularization_workflow(org.uuid, uuid)
        if regularization_workflow is None:
            return read_data.get_404_response("Regularization Workflow")

        # * Members
        member_uuids = request.data.getlist("member_uuids", [])
        members = Member.objects.filter(Q(organization=org) & Q(uuid__in=member_uuids))
        for member in members:
            member.regularization_workflow = regularization_workflow
            member.save()

        # * Departments
        department_uuids = request.data.getlist("department_uuids", [])
        departments = Department.objects.filter(
            Q(organization=org) & Q(uuid__in=department_uuids)
        )
        for department in departments:
            department.regularization_workflow = regularization_workflow
            department.save()

        # * Designations
        designation_uuids = request.data.getlist("designation_uuids", [])
        designations = Designation.objects.filter(
            Q(organization=org) & Q(uuid__in=designation_uuids)
        )
        for designation in designations:
            designation.regularization_workflow = regularization_workflow
            designation.save()

        # * Roles
        role_uuids = request.data.getlist("role_uuids", [])
        roles = Role.objects.filter(Q(organization=org) & Q(uuid__in=role_uuids))
        for role in roles:
            role.regularization_workflow = regularization_workflow
            role.save()

        # * Org Locations
        organization_location_uuids = request.data.getlist(
            "organization_location_uuids", []
        )
        org_locations = Role.objects.filter(
            Q(organization=org) & Q(uuid__in=organization_location_uuids)
        )
        for org_location in org_locations:
            org_location.regularization_workflow = regularization_workflow
            org_location.save()

        serializer = self.serializer_class(regularization_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        regularization_workflow = get_regularization_workflow(org.uuid, uuid)
        if regularization_workflow is None:
            return read_data.get_404_response("Regularization Workflow")

        # * Member
        member_uuids = request.data.getlist("member_uuids", [])
        members = Member.objects.filter(
            Q(organization=org)
            & Q(uuid__in=member_uuids)
            & Q(regularization_workflow=regularization_workflow)
        )
        for member in members:
            member.regularization_workflow = None
            member.save()

        # * Department
        department_uuids = request.data.getlist("department_uuids", [])
        departments = Department.objects.filter(
            Q(organization=org)
            & Q(uuid__in=department_uuids)
            & Q(regularization_workflow=regularization_workflow)
        )
        for department in departments:
            department.regularization_workflow = None
            department.save()

        # * Designation
        designation_uuids = request.data.getlist("designation_uuids", [])
        designations = Designation.objects.filter(
            Q(organization=org)
            & Q(uuid__in=designation_uuids)
            & Q(regularization_workflow=regularization_workflow)
        )
        for designation in designations:
            designation.regularization_workflow = None
            designation.save()

        # * Roles
        role_uuids = request.data.getlist("role_uuids", [])
        roles = Role.objects.filter(
            Q(organization=org)
            & Q(uuid__in=role_uuids)
            & Q(regularization_workflow=regularization_workflow)
        )
        for role in roles:
            role.regularization_workflow = None
            role.save()

        # * Org Locations
        organization_location_uuids = request.data.getlist(
            "organization_location_uuids", []
        )
        org_locations = Role.objects.filter(
            Q(organization=org)
            & Q(uuid__in=organization_location_uuids)
            & Q(regularization_workflow=regularization_workflow)
        )
        for org_location in org_locations:
            org_location.regularization_workflow = None
            org_location.save()

        serializer = self.serializer_class(regularization_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)
