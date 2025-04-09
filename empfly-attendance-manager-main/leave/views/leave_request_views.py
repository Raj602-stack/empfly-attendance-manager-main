from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions
from organization.utils import get_hr_role, get_admin_role

from leave.models import LeaveType, LeaveBalance, LeaveRequest, Applicability
from leave import serializers, search
from leave.utils import (
    get_leave_type,
    get_leave_request,
    get_assocaited_approval_workflow,
    is_approval_workflow_allowed,
    get_default_approval_workflow,
)
from member.models import Member
from utils import read_data, fetch_data, create_data, email_funcs

import logging


logger = logging.getLogger(__name__)


class AllLeaveRequestsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_requests = LeaveRequest.objects.filter(member__organization=org)
        search_query = request.GET.get("search_query")
        leave_requests = search.search_leave_requests(leave_requests, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(leave_requests, per_page)
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

        leave_type_uuid = request.data.get("leave_type_uuid")
        leave_type = get_leave_type(org.uuid, leave_type_uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        member_uuid = request.data.get("member_uuid")
        member = fetch_data.get_member_by_uuid(member_uuid)
        if member is None:
            return read_data.get_404_response("Member")

        unit = request.data.get("unit", "days")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        config = request.data.get("config")
        reason = request.data.get("reason")
        """
        config = {
            "27-04-2022": {
                "duration": "full_day",
                "cost": 1
                "total": 1
            },
            "28-04-2022": {
                "duration": "half_day",
                "cost": 0.5,
                "half": 1
                "total": 2
            },
            "29-04-2022": {
                "duration": "quarter_day",
                "cost": 0.25,
                "quarter": 3,
                "total": 4
            }
        }
        """

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        start_date = create_data.convert_string_to_datetime(start_date)
        if start_date is None:
            return Response(
                {"message": "Start date is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        end_date = create_data.convert_string_to_datetime(end_date)
        if end_date is None:
            return Response(
                {"message": "End date is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if reason is None:
            return Response(
                {"message": "Reason is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        total_cost = 0
        for date, date_config in config.items():
            total_cost += date_config.get("cost", 1)

        if unit == "days":
            days = total_cost

        leave_balance = LeaveBalance.objects.get(member=member, leave_type=leave_type)
        if (
            leave_balance.available - days < 0
            and leave_type.restriction.get("exceed_leave_balance") is False
        ):
            return Response(
                {"message": "Cannot exceed leave balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            leave_request = LeaveRequest.objects.create(
                member=member,
                leave_type=leave_type,
                unit=unit,
                start_date=start_date,
                end_date=end_date,
                days=days,
                config=config,
                reason=reason,
            )
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in MyLeaveRequestsAPI"
            )
            return Response(
                {"message": "Failed to create Leave Request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        leave_balance.available -= days
        leave_balance.booked += days
        leave_balance.save()

        serializer = self.serializer_class(leave_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyLeaveRequestsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_requests = LeaveRequest.objects.filter(member=member)
        search_query = request.GET.get("search_query")
        leave_requests = search.search_leave_requests(leave_requests, search_query)

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(leave_requests, per_page)
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

        leave_type_uuid = request.data.get("leave_type_uuid")
        leave_type = get_leave_type(org.uuid, leave_type_uuid)
        if leave_type is None:
            return read_data.get_404_response("Leave Type")

        unit = request.data.get("unit", "days")
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        config = request.data.get("breakup")
        reason = request.data.get("reason")
        """
        breakup = {
            "27-04-2022": {
                "duration": "full_day",
                "days": 1
                "total_days": 1
            },
            "28-04-2022": {
                "duration": "half_day",
                "days": 0.5,
                "which_half": 1
                "total_halves": 2
            },
            "29-04-2022": {
                "duration": "quarter_day",
                "days": 0.25,
                "which_quarter": 3,
                "total_quarters": 4
            }
        }
        """

        start_date = create_data.convert_string_to_datetime(start_date)
        end_date = create_data.convert_string_to_datetime(end_date)

        if start_date is None or end_date is None:
            return Response(
                {"message": "State date and end date are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reason is None:
            return Response(
                {"message": "Reason is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        total_cost = 0
        for date, date_config in config.items():
            total_cost += date_config.get("cost", 1)

        if unit == "days":
            days = total_cost

        leave_balance = LeaveBalance.objects.get(member=member, leave_type=leave_type)
        if (
            leave_balance.available - days < 0
            and leave_type.restriction.get("exceed_leave_balance") is False
        ):
            return Response(
                {"message": "Cannot exceed leave balance"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        approval_workflow = get_assocaited_approval_workflow(member)
        is_allowed = is_approval_workflow_allowed(member, approval_workflow)
        if is_allowed is False:
            approval_workflow = get_default_approval_workflow(org)

        try:
            leave_request = LeaveRequest.objects.create(
                member=member,
                leave_type=leave_type,
                unit=unit,
                start_date=start_date,
                end_date=end_date,
                days=days,
                config=config,
                reason=reason,
                approval_workflow=approval_workflow,
            )
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in MyLeaveRequestsAPI"
            )
            return Response(
                {"message": "Failed to create Leave Request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(leave_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LeaveRequestAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_request_uuid = self.kwargs.get("uuid")
        leave_request = get_leave_request(org.uuid, leave_request_uuid)
        if leave_request is None:
            return read_data.get_404_response("Leave Request")

        serializer = self.serializer_class(leave_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        leave_request_uuid = self.kwargs.get("uuid")
        leave_request = get_leave_request(org.uuid, leave_request_uuid)
        if leave_request is None:
            return read_data.get_404_response("Leave Request")

        leave_type = leave_request.leave_type
        days = leave_request.days
        leave_request.delete()

        leave_balance = LeaveBalance.objects.get(member=member, leave_type=leave_type)
        leave_balance.available += days
        leave_balance.booked -= days
        leave_balance.save()

        return read_data.get_200_delete_response("Leave Request")


class ApproveLeaveRequestAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.LeaveRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        leave_request = get_leave_request(org.uuid, uuid)
        if leave_request is None:
            return read_data.get_404_response("Leave Request")

        serializer = self.serializer_class(leave_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        leave_request = get_leave_request(org.uuid, uuid)
        if leave_request is None:
            return read_data.get_404_response("Leave Request")

        approval_workflow = leave_request.approval_workflow
        status_details = leave_request.status_details
        member = leave_request.member
        approval_status = request.data.get("approve")
        if approval_status not in ("approved", "denied"):
            return Response(
                {"message": "Enter valid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        # * Members can create LRs for past days therefore
        # * HR/Admin should be allowed to update LRs past the start date
        # if leave_request.start_date >= read_data.get_current_datetime().date():
        #     if leave_request.status == "pending":
        #         leave_request.status = "denied"
        #         leave_request.save()
        #     return Response(
        #         {"message": "Cannot updated past leave requests"},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # * Leave Request has been approved/denied previously
        if leave_request.status != "pending":
            if (
                member.role == get_hr_role()
                or member.role == get_admin_role()
            ):
                leave_request.status = approval_status
                leave_request.save(
                    activity_kwargs={
                        "created_by": member,
                        "action": approval_status,
                        "object": "leave_request",
                        "value": approval_status,
                    }
                )
            else:
                return read_data.get_403_response()

        member_uuid_list = list(status_details.get("members", {}).keys())
        member_approval_values = set(status_details.get("members", {}).values())

        activity_kwargs = {
            "action": approval_status,
            "value": approval_status,
            "created_by": member,
        }

        # * Department
        if status_details.get("department_head") == "pending":

            activity_kwargs["object"] = "department_head"
            # If Member does not belong to a department
            if member.department is None:
                status_details["department_head"] = "approved"
                activity_kwargs["created_by"] = None

            # If approver is not the member's department head
            elif member.department.department_head != requesting_member:
                return Response(
                    {"message": "Only department head can approve at this stage"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            status_details["department_head"] = approval_status

        # * Members
        elif len(member_uuid_list) > 0 and (
            "approved" not in member_approval_values
            and "denied" not in member_approval_values
        ):

            activity_kwargs["object"] = "members"
            members = Member.objects.filter(
                Q(organization=org) & Q(uuid__in=member_uuid_list)
            )

            # UUIDs mentioned in the list are not valid
            if members.count() == 0:
                status_details["members"] = {}
            else:
                # Remove invalid UUIDs
                member_uuids = list(members.values_list("uuid", flat=True))
                invalid_member_uuids = list(set(member_uuid_list) ^ set(member_uuids))
                for value in invalid_member_uuids:
                    del status_details["members"][value]

                if str(requesting_member.uuid) not in member_uuids:
                    return read_data.get_403_response()

                status_details["member"][str(requesting_member.uuid)] = approval_status

        # * HR
        elif status_details.get("hr") == "pending":

            activity_kwargs["object"] = "members"
            hr_count = Member.objects.filter(
                Q(organization=org) & Q(role__name="hr")
            ).count()

            # If no HR members exist
            if hr_count == 0:
                status_details["hr"] = "approved"
                activity_kwargs["created_by"] = None

            # If approver is not HR
            elif member.role != get_hr_role():
                return Response(
                    {"message": "Only HR can approve at this stage"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            status_details["hr"] = approval_status

        # * Admin
        elif status_details.get("admin") == "pending":

            activity_kwargs["object"] = "members"
            admin_count = Member.objects.filter(
                Q(organization=org) & Q(role__name="admin")
            ).count()

            # If no Admin members exist
            if admin_count == 0:
                status_details["admin"] = "approved"
                activity_kwargs["created_by"] = None

            # If approver is not Admin
            elif member.role != fetch_data.get_admin_role():
                return Response(
                    {"message": "Only admins can approve at this stage"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            status_details["admin"] = approval_status

        if approval_status == "denied":
            leave_request.status = "denied"

        if all(status_details.values()):
            leave_request.status = "approved"

        leave_request.save(activity_kwargs=activity_kwargs)

        serializer = self.serializer_class(leave_request)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LeaveRequestActivityAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.LeaveRequestActivitySerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = request.data.get("uuid")
        leave_request = get_leave_request(org.uuid, uuid)
        if leave_request is None:
            return read_data.get_404_response("Leave Request")

        if (
            leave_request.member != member
            and member.role != fetch_data.get_admin_role()
        ):
            return read_data.get_403_response()

        activities = leave_request.leave_request_activities.all()
        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(activities, per_page)
        page_obj = paginator.get_page(page)

        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": paginator.num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )
