from django.db import IntegrityError
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q

from api import permissions

from organization.utils import get_hr_role, get_admin_role

from leave.models import RegularizationRequest
from leave import serializers, search
from leave.utils import get_leave_type
from member.models import Member
from utils import read_data, fetch_data, create_data, email_funcs

import logging


logger = logging.getLogger(__name__)


class AllRegularizationRequestsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RegularizationRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        regularization_requests = RegularizationRequest.objects.filter(
            member__organization=org
        )
        search_query = request.GET.get("search_query")
        regularization_requests = search.search_regularization_requests(
            regularization_requests, search_query
        )

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(regularization_requests, per_page)
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
            return read_data.get_404_response("Regularization Type")

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
            regularization_request = RegularizationRequest.objects.create(
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
                f"Add exception for {e.__class__.__name__} in MyRegularizationRequestsAPI"
            )
            return Response(
                {"message": "Failed to create Regularization Request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        leave_balance.available -= days
        leave_balance.booked += days
        leave_balance.save()

        serializer = self.serializer_class(regularization_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyRegularizationRequestsAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RegularizationRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        regularization_requests = RegularizationRequest.objects.filter(member=member)
        search_query = request.GET.get("search_query")
        regularization_requests = search.search_regularization_requests(
            regularization_requests, search_query
        )

        per_page = request.GET.get("per_page", 10)
        page = request.GET.get("page", 1)
        paginator = Paginator(regularization_requests, per_page)
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

        date = request.data.get("date")
        check_in = request.data.get("check_in")
        check_out = request.data.get("check_out")
        reason = request.data.get("reason")

        date = create_data.convert_string_to_datetime(date)
        if date is None:
            return Response(
                {"message": "Date is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reason is None:
            return Response(
                {"message": "Reason is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        regularization_workflow = fetch_data.get_assocaited_regularization_workflow(
            member
        )
        is_allowed = fetch_data.is_regularization_workflow_allowed(
            member, regularization_workflow
        )
        if is_allowed is False:
            regularization_workflow = fetch_data.get_default_regularization_workflow(
                org
            )

        try:
            regularization_request = RegularizationRequest.objects.create(
                member=member,
                date=date,
                check_in=check_in,
                check_out=check_out,
                reason=reason,
                regularization_workflow=regularization_workflow,
            )
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in MyRegularizationRequestsAPI"
            )
            return Response(
                {"message": "Failed to create Regularization Request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.serializer_class(regularization_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RegularizationRequestAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RegularizationRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        regularization_request_uuid = self.kwargs.get("uuid")
        regularization_request = fetch_data.get_regularization_request(
            org.uuid, regularization_request_uuid
        )
        if regularization_request is None:
            return read_data.get_404_response("Regularization Request")

        serializer = self.serializer_class(regularization_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        regularization_request_uuid = self.kwargs.get("uuid")
        regularization_request = fetch_data.get_regularization_request(
            org.uuid, regularization_request_uuid
        )
        if regularization_request is None:
            return read_data.get_404_response("Regularization Request")

        regularization_request.delete()
        return read_data.get_200_delete_response("Regularization Request")


class ApproveRegularizationRequestAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.RegularizationRequestSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        regularization_request = fetch_data.get_regularization_request(org.uuid, uuid)
        if regularization_request is None:
            return read_data.get_404_response("Regularization Request")

        serializer = self.serializer_class(regularization_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        regularization_request = fetch_data.get_regularization_request(org.uuid, uuid)
        if regularization_request is None:
            return read_data.get_404_response("Regularization Request")

        regularization_workflow = regularization_request.regularization_workflow
        status_details = regularization_request.status_details
        member = regularization_request.member
        approval_status = request.data.get("approve")
        if approval_status not in ("approved", "denied"):
            return Response(
                {"message": "Enter valid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        # * Members can create LRs for past days therefore
        # * HR/Admin should be allowed to update LRs past the start date
        # if regularization_request.start_date >= read_data.get_current_datetime().date():
        #     if regularization_request.status == "pending":
        #         regularization_request.status = "denied"
        #         regularization_request.save()
        #     return Response(
        #         {"message": "Cannot updated past leave requests"},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # * Regularization Request has been approved/denied previously
        if regularization_request.status != "pending":
            if (
                member.role == get_hr_role()
                or member.role == get_admin_role()
            ):
                regularization_request.status = approval_status
                regularization_request.save(
                    activity_kwargs={
                        "created_by": member,
                        "action": approval_status,
                        "object": "regularization_request",
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
            regularization_request.status = "denied"

        if all(status_details.values()):
            regularization_request.status = "approved"

        regularization_request.save(activity_kwargs=activity_kwargs)

        serializer = self.serializer_class(regularization_request)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RegularizationRequestActivityAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = serializers.RegularizationRequestActivitySerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = request.data.get("uuid")
        regularization_request = fetch_data.get_regularization_request(org.uuid, uuid)
        if regularization_request is None:
            return read_data.get_404_response("Regularization Request")

        if (
            regularization_request.member != member
            and member.role != fetch_data.get_admin_role()
        ):
            return read_data.get_403_response()

        activities = regularization_request.regularization_request_activities.all()
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
