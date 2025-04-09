from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions
from leave.models import LeaveType, LeaveBalance, LeaveRequest, Applicability
from leave import serializers
from leave.utils import get_leave_balance, get_leave_balance, get_leave_type
from member.models import Member
from organization.models import Department, Designation, Role
from organization.serializers import DesignationSerializer
from roster.models import Location
from utils import read_data, fetch_data, create_data, email_funcs

import logging


logger = logging.getLogger(__name__)


class AllLeaveTypesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveTypeSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_types = org.leave_types.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(leave_types, per_page)
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

        name = request.data.get("name")
        description = request.data.get("description")
        is_paid = request.data.get("is_paid")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        restriction = request.data.get("restriction")
        policy = request.data.get("policy")

        if start_date:
            start_date = create_data.convert_string_to_datetime(start_date)

        if end_date:
            end_date = create_data.convert_string_to_datetime(end_date)

        try:
            leave_type = LeaveType.objects.create(
                name=name,
                description=description,
                is_paid=is_paid,
                start_date=start_date,
                end_date=end_date,
                restriction=restriction,
                policy=policy,
            )
        except IntegrityError as e:
            logger.error(e)
            return read_data.get_409_response("Leave Type", "name")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllLeaveTypesAPI"
            )
            return Response(
                {"message": "Failed to create Leave Type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(leave_type)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LeaveTypeAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveTypeSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        serializer = self.serializer_class(leave_type)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        name = request.data.get("name", leave_type.name)
        description = request.data.get("description", leave_type.description)
        is_paid = request.data.get("is_paid", leave_type.is_paid)
        restriction = request.data.get("restriction", leave_type.restriction)
        policy = request.data.get("policy", leave_type.policy)
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")

        leave_type.name = name
        leave_type.description = description
        leave_type.is_paid = is_paid
        leave_type.restriction = restriction
        leave_type.policy = policy

        if start_date:
            leave_type.start_date = start_date
            leave_requests = leave_type.leave_requests.filter(
                Q(start_date__lt=start_date) & Q(status="pending")
            )
            denied_activity_kwargs = {
                "action": "updated",
                "object": "status",
                "value": "denied",
                "metadata": "Denied since Leave Type's start date was updated",
            }
            for leave_request in leave_requests:
                leave_request.status = "denied"
                leave_request.save(activity_kwargs=denied_activity_kwargs)

        if end_date:
            leave_type.end_date = end_date
            leave_requests = leave_type.leave_requests.filter(
                Q(end_date__gt=end_date) & Q(status="pending")
            )
            denied_activity_kwargs = {
                "action": "updated",
                "object": "status",
                "value": "denied",
                "metadata": "Denied since Leave Type's end date was updated",
            }
            for leave_request in leave_requests:
                leave_request.status = "denied"
                leave_request.save(activity_kwargs=denied_activity_kwargs)

        leave_type.save()
        serializer = self.serializer_class(leave_type)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        leave_type.delete()
        return read_data.get_200_delete_response("Leave Type")


class LeaveApplicabilityAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.ApplicabilitySerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_type_uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, leave_type_uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        serializer = self.serializer_class(leave_type)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_type_uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, leave_type_uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        applicability = leave_type.applicability

        location_uuids = request.data.getlist("location_uuids", [])
        exclude_location_uuids = request.data.getlist("exclude_location_uuids", [])

        department_uuids = request.data.getlist("department_uuids", [])
        exclude_department_uuids = request.data.getlist("exclude_department_uuids", [])

        designation_uuids = request.data.getlist("designation_uuids", [])
        exclude_designation_uuids = request.data.getlist(
            "exclude_designation_uuids", []
        )

        role_uuids = request.data.getlist("role_uuids", [])
        exclude_role_uuids = request.data.getlist("exclude_role_uuids", [])

        member_uuids = request.data.getlist("member_uuids", [])
        exclude_member_uuids = request.data.getlist("exclude_member_uuids", [])

        try:
            locations = Location.objects.filter(
                Q(organization=org) & Q(uuid__in=location_uuids)
            )
            exclude_locations = Location.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_location_uuids)
            )

            departments = Department.objects.filter(
                Q(organization=org) & Q(uuid__in=department_uuids)
            )
            exclude_departments = Department.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_department_uuids)
            )

            designations = Designation.objects.filter(
                Q(organization=org) & Q(uuid__in=designation_uuids)
            )
            exclude_designations = Designation.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_designation_uuids)
            )

            roles = Role.objects.filter(Q(organization=org) & Q(uuid__in=role_uuids))
            exclude_roles = Role.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_role_uuids)
            )

            members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=member_uuids)
            )
            exclude_members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_member_uuids)
            )

        except (ValidationError) as e:
            logger.error(e)
            return Response(
                {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
            )

        for location in locations:
            applicability.locations.add(location)
        for location in exclude_locations:
            applicability.exclude_locations.add(location)

        for object in departments:
            applicability.departments.add(object)
        for object in exclude_departments:
            applicability.exclude_departments.add(object)

        for object in designations:
            applicability.designations.add(object)
        for object in exclude_designations:
            applicability.exclude_designations.add(object)

        for object in roles:
            applicability.roles.add(object)
        for object in exclude_roles:
            applicability.exclude_roles.add(object)

        for object in members:
            applicability.members.add(object)
        for object in exclude_members:
            applicability.exclude_members.add(object)

        applicability.save()

        serializer = self.serializer_class(leave_type)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_type_uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, leave_type_uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        applicability = leave_type.applicability

        location_uuids = request.data.getlist("location_uuids", [])
        exclude_location_uuids = request.data.getlist("exclude_location_uuids", [])

        department_uuids = request.data.getlist("department_uuids", [])
        exclude_department_uuids = request.data.getlist("exclude_department_uuids", [])

        designation_uuids = request.data.getlist("designation_uuids", [])
        exclude_designation_uuids = request.data.getlist(
            "exclude_designation_uuids", []
        )

        role_uuids = request.data.getlist("role_uuids", [])
        exclude_role_uuids = request.data.getlist("exclude_role_uuids", [])

        member_uuids = request.data.getlist("member_uuids", [])
        exclude_member_uuids = request.data.getlist("exclude_member_uuids", [])

        try:
            locations = Location.objects.filter(
                Q(organization=org) & Q(uuid__in=location_uuids)
            )
            exclude_locations = Location.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_location_uuids)
            )

            departments = Department.objects.filter(
                Q(organization=org) & Q(uuid__in=department_uuids)
            )
            exclude_departments = Department.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_department_uuids)
            )

            designations = Designation.objects.filter(
                Q(organization=org) & Q(uuid__in=designation_uuids)
            )
            exclude_designations = Designation.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_designation_uuids)
            )

            roles = Role.objects.filter(Q(organization=org) & Q(uuid__in=role_uuids))
            exclude_roles = Role.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_role_uuids)
            )

            members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=member_uuids)
            )
            exclude_members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=exclude_member_uuids)
            )

        except (ValidationError) as e:
            logger.error(e)
            return Response(
                {"message": "Enter valid UUID(s)"}, status=status.HTTP_400_BAD_REQUEST
            )

        for location in locations:
            applicability.locations.remove(location)
        for location in exclude_locations:
            applicability.exclude_locations.remove(location)

        for object in departments:
            applicability.departments.remove(object)
        for object in exclude_departments:
            applicability.exclude_departments.remove(object)

        for object in designations:
            applicability.designations.remove(object)
        for object in exclude_designations:
            applicability.exclude_designations.remove(object)

        for object in roles:
            applicability.roles.remove(object)
        for object in exclude_roles:
            applicability.exclude_roles.remove(object)

        for object in members:
            applicability.members.remove(object)
        for object in exclude_members:
            applicability.exclude_members.remove(object)

        applicability.save()

        serializer = self.serializer_class(leave_type)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Get All LeaveBalances of all Members for a particular LeaveType
class AllLeaveBalancesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveBalanceSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        leave_type_uuid = self.kwargs.get("uuid")
        leave_type = get_leave_type(org.uuid, leave_type_uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        leave_balances = LeaveBalance.objects.filter(leave_type=leave_type)
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(leave_balances, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


# Get All LeaveBalances of a Member
class MembersAllLeaveBalancesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveBalanceSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        member_uuid = self.kwargs.get("member_uuid")
        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if (
            fetch_data.is_admin(requesting_member) is False
            and requesting_member != member
        ):
            return read_data.get_403_response()

        leave_balances = LeaveBalance.objects.filter(member=member)
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(leave_balances, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


# Get particular LeaveBalance of a Member
class MembersLeaveBalanceAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveBalanceSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        member_uuid = self.kwargs.get("member_uuid")
        leave_type_uuid = self.kwargs.get("leave_type_uuid")

        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if (
            fetch_data.is_admin(requesting_member) is False
            and requesting_member != member
        ):
            return read_data.get_403_response()

        leave_balance = get_leave_balance(member_uuid, leave_type_uuid)
        if leave_balance is None:
            return read_data.get_404_response("Leave Balance")

        serializer = self.serializer_class(leave_balance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        member_uuid = self.kwargs.get("member_uuid")
        leave_type_uuid = self.kwargs.get("leave_type_uuid")

        member = fetch_data.get_member_by_uuid(org.uuid, member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        leave_balance = get_leave_balance(member_uuid, leave_type_uuid)
        if leave_balance is None:
            return read_data.get_404_response("Leave Balance")

        available = request.data.get("available")
        reason = request.data.get("reason")

        leave_balance.available = available
        leave_balance.save(
            activity_kwargs={
                "action": "set",
                "days": available,
                "metadata": reason,
            }
        )

        serializer = self.serializer_class(leave_balance)
        return Response(serializer.data, status=status.HTTP_200_OK)
