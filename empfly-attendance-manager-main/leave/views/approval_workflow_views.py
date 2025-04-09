from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions
from leave.models import ApprovalWorkflow
from leave import serializers
from leave.utils import get_approval_workflow
from member.models import Member
from organization.models import Department, Designation, OrgLocation, Role
from utils import read_data, fetch_data

import logging


logger = logging.getLogger(__name__)


class AllApprovalWorkflowsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.ApprovalWorkflowSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        approval_workflows = org.approval_workflows.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(approval_workflows, per_page)
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

        approval_workflow = ApprovalWorkflow.objects.create(
            name=name,
            description=description,
            organization=org,
            criteria=criteria,
            approval_types=approval_types,
            exceptions=exceptions,
            created_by=member,
        )

        serializer = self.serializer_class(approval_workflow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ApprovalWorkflowAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.ApprovalWorkflowSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        approval_workflow = get_approval_workflow(org.uuid, uuid)
        if approval_workflow is None:
            return read_data.get_404_response("Approval Workflow")

        serializer = self.serializer_class(approval_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role != fetch_data.get_admin_role():
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        approval_workflow = get_approval_workflow(org.uuid, uuid)
        if approval_workflow is None:
            return read_data.get_404_response("Approval Workflow")

        name = request.data.get("name", approval_workflow.name)
        description = request.data.get("description", approval_workflow.description)
        criteria = request.data.get("criteria", approval_workflow.criteria)
        approval_types = request.data.get(
            "approval_types", approval_workflow.approval_types
        )
        exceptions = request.data.get("exceptions", approval_workflow.exceptions)

        approval_workflow.name = name
        approval_workflow.description = description
        approval_workflow.criteria = criteria
        approval_workflow.approval_types = approval_types
        approval_workflow.exceptions = exceptions
        approval_workflow.save()

        serializer = self.serializer_class(approval_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if member.role != fetch_data.get_admin_role():
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        approval_workflow = get_approval_workflow(org.uuid, uuid)
        if approval_workflow is None:
            return read_data.get_404_response("Approval Workflow")

        approval_workflow.delete()
        return read_data.get_200_delete_response("Approval Workflow")


class AssignApprovalWorkflowAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.ApprovalWorkflowSerializer

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        approval_workflow = get_approval_workflow(org.uuid, uuid)
        if approval_workflow is None:
            return read_data.get_404_response("Approval Workflow")

        # * Members
        member_uuids = request.data.getlist("member_uuids", [])
        members = Member.objects.filter(Q(organization=org) & Q(uuid__in=member_uuids))
        for member in members:
            member.approval_workflow = approval_workflow
            member.save()

        # * Departments
        department_uuids = request.data.getlist("department_uuids", [])
        departments = Department.objects.filter(
            Q(organization=org) & Q(uuid__in=department_uuids)
        )
        for department in departments:
            department.approval_workflow = approval_workflow
            department.save()

        # * Designations
        designation_uuids = request.data.getlist("designation_uuids", [])
        designations = Designation.objects.filter(
            Q(organization=org) & Q(uuid__in=designation_uuids)
        )
        for designation in designations:
            designation.approval_workflow = approval_workflow
            designation.save()

        # * Roles
        role_uuids = request.data.getlist("role_uuids", [])
        roles = Role.objects.filter(Q(organization=org) & Q(uuid__in=role_uuids))
        for role in roles:
            role.approval_workflow = approval_workflow
            role.save()

        # * Org Locations
        organization_location_uuids = request.data.getlist(
            "organization_location_uuids", []
        )
        org_locations = Role.objects.filter(
            Q(organization=org) & Q(uuid__in=organization_location_uuids)
        )
        for org_location in org_locations:
            org_location.approval_workflow = approval_workflow
            org_location.save()

        serializer = self.serializer_class(approval_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        approval_workflow = get_approval_workflow(org.uuid, uuid)
        if approval_workflow is None:
            return read_data.get_404_response("Approval Workflow")

        # * Member
        member_uuids = request.data.getlist("member_uuids", [])
        members = Member.objects.filter(
            Q(organization=org)
            & Q(uuid__in=member_uuids)
            & Q(approval_workflow=approval_workflow)
        )
        for member in members:
            member.approval_workflow = None
            member.save()

        # * Department
        department_uuids = request.data.getlist("department_uuids", [])
        departments = Department.objects.filter(
            Q(organization=org)
            & Q(uuid__in=department_uuids)
            & Q(approval_workflow=approval_workflow)
        )
        for department in departments:
            department.approval_workflow = None
            department.save()

        # * Designation
        designation_uuids = request.data.getlist("designation_uuids", [])
        designations = Designation.objects.filter(
            Q(organization=org)
            & Q(uuid__in=designation_uuids)
            & Q(approval_workflow=approval_workflow)
        )
        for designation in designations:
            designation.approval_workflow = None
            designation.save()

        # * Roles
        role_uuids = request.data.getlist("role_uuids", [])
        roles = Role.objects.filter(
            Q(organization=org)
            & Q(uuid__in=role_uuids)
            & Q(approval_workflow=approval_workflow)
        )
        for role in roles:
            role.approval_workflow = None
            role.save()

        # * Org Locations
        organization_location_uuids = request.data.getlist(
            "organization_location_uuids", []
        )
        org_locations = Role.objects.filter(
            Q(organization=org)
            & Q(uuid__in=organization_location_uuids)
            & Q(approval_workflow=approval_workflow)
        )
        for org_location in org_locations:
            org_location.approval_workflow = None
            org_location.save()

        serializer = self.serializer_class(approval_workflow)
        return Response(serializer.data, status=status.HTTP_200_OK)
