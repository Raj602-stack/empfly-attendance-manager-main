from django.db.models import Q
from django.conf import settings
from celery import shared_task

from member.models import Member
from organization.models import Organization
# from roster.models import Roster
from leave.models import (
    LeaveBalanceActivity,
    LeaveRequest,
    LeaveType,
    LeaveBalance,
    Applicability,
)

from utils import create_data, read_data

import datetime as dt
import logging


logger = logging.getLogger(__name__)


def check_frequency(frequency: str, action_on: str, current_date: dt.datetime) -> bool:

    if frequency == "daily":
        return True

    elif frequency == "weekly" and action_on == current_date.weekday():
        return True

    elif frequency == "monthly" and action_on == current_date.day:
        return True

    elif frequency == "half_yearly":
        current_date_str = f"{current_date.day}-{current_date.month}"
        if current_date_str in action_on:
            return True

    elif frequency == "yearly":
        current_date_str = f"{current_date.day}-{current_date.month}"
        if action_on == current_date_str:
            return True

    elif frequency == "one_time":
        action_on_dt = create_data.convert_string_to_datetime(action_on)
        if action_on_dt == current_date:
            return True

    return False


# OPTIMIZE
def get_applicable_members(
    applicability: Applicability, check_effective_after: bool = True
) -> Member:

    leave_type = applicability.leave_type
    members = Member.objects.filter(organization=leave_type.organization)

    member_ids = []
    exclude_member_ids = []

    member_ids += list(applicability.designations.values_list("members__id", flat=True))
    member_ids += list(applicability.departments.values_list("members__id", flat=True))
    member_ids += list(applicability.roles.values_list("members__id", flat=True))
    member_ids += list(applicability.members.values_list("id", flat=True))
    member_ids += list(
        applicability.organization_locations.values_list("members__id", flat=True)
    )

    exclude_member_ids += list(
        applicability.exlude_designations.values_list("members__id", flat=True)
    )
    exclude_member_ids += list(
        applicability.exlude_departments.values_list("members__id", flat=True)
    )
    exclude_member_ids += list(
        applicability.exlude_roles.values_list("members__id", flat=True)
    )
    exclude_member_ids += list(
        applicability.exlude_members.values_list("id", flat=True)
    )
    exclude_member_ids += list(
        applicability.exlude_organization_locations.values_list(
            "members__id", flat=True
        )
    )

    member_ids = [x for x in set(member_ids) if x is not None]
    exclude_member_ids = [x for x in set(exclude_member_ids) if x is not None]

    members = Member.objects.filter(
        Q(id__in=member_ids) & ~Q(id__in=exclude_member_ids)
    )

    if check_effective_after:

        effective_after = leave_type.policy.get("effective_after", {})
        condition = effective_after.get("condition", "date_of_joining")
        days = effective_after.get("days", 0)

        current_date = read_data.get_current_datetime().date()
        effective_after_date = (current_date - dt.timedelta(days=days)).date()

        if condition == "date_of_joining":
            members = members.filter(
                Q(joining_date__isnull=False)
                & Q(joining_date__gte=effective_after_date)
            )
        elif condition == "date_of_joining":
            members = members.filter(
                Q(confirmation_date__isnull=False)
                & Q(confirmation_date__gte=effective_after_date)
            )

    return members


@shared_task(name="leave_balance_accrual")
def leave_balance_accrual():
    """
    Get LeaveTypes in an organization that has start_date lte today, and end_date gte today
    Get Accrual Policy
    Check if date falls on frequency
    Using the LeaveType's Applicability, get the members to whom it is applicable.
    Check effective_after date
    Get or create LeaveBalance for each member.
    Check if current accrual
    Add accrual to the LeaveBalance
    """

    current_date = read_data.get_current_datetime().date()
    current_date_str = current_date.__str__()

    for org in Organization.objects.all():
        print(f"{org=}")

        # Get valid LeaveTypes
        leave_types = LeaveType.objects.filter(
            Q(organization=org)
            & (Q(start_date__lte=current_date) | Q(start_date__isnull=True))
            & (Q(end_date__gte=current_date) | Q(end_date__isnull=True))
        )

        for leave_type in leave_types:
            print(f"{leave_type=}")

            applicability = leave_type.applicability
            accrual_policy = leave_type.policy.get("accrual", {})
            frequency = accrual_policy.get("frequency")
            credit_on = accrual_policy.get("credit_on")

            current_accrual = accrual_policy.get("current_accrual")
            number_of_days = accrual_policy.get("number_of_days")

            is_frequency_valid = check_frequency(frequency, credit_on, current_date)
            if is_frequency_valid is False:
                continue

            members = get_applicable_members(applicability)
            for member in members:
                print(f"{member=}")

                leave_balance, created = LeaveBalance.objects.get_or_create(
                    member=member, leave_type=leave_type
                )

                if created and current_accrual is False:
                    print(f"Skipping for {member=} since current accrual is False")
                    continue

                leave_balance.available += number_of_days
                leave_balance.save(
                    activity_kwargs={"action": "credit", "days": number_of_days}
                )


@shared_task(name="leave_balance_reset")
def leave_balance_reset():

    current_date = read_data.get_current_datetime().date()
    current_date_str = current_date.__str__()
    print(f"{current_date_str=}")

    for org in Organization.objects.all():
        print(f"{org=}")

        # Get valid LeaveTypes
        leave_types = LeaveType.objects.filter(
            Q(organization=org)
            & (Q(start_date__lte=current_date) | Q(start_date__isnull=True))
            & (Q(end_date__gte=current_date) | Q(end_date__isnull=True))
        )

        for leave_type in leave_types:
            print(f"----- {leave_type} -----")

            applicability = leave_type.applicability

            reset_policy = leave_type.policy.get("reset", {})
            frequency = reset_policy.get("frequency")
            reset_on = reset_policy.get("reset_on")
            carry_forward = reset_policy.get("carry_forward", {})
            carry_forward_unit = carry_forward.get("unit")
            carry_forward_value = carry_forward.get("value")
            carry_forward_max_limit = carry_forward.get("max_limit")

            is_frequency_valid = check_frequency(frequency, reset_on, current_date)
            if is_frequency_valid is False:
                continue

            members = get_applicable_members(applicability)
            for member in members:
                print(f"{member=}")

                leave_balance, created = LeaveBalance.objects.get_or_create(
                    member=member, leave_type=leave_type
                )

                if carry_forward_unit == "days":
                    number_of_days = min(
                        leave_balance.available, carry_forward_max_limit
                    )
                elif carry_forward_unit == "percentage":
                    number_of_days = leave_balance.available * carry_forward_value
                    number_of_days = min(number_of_days, carry_forward_max_limit)
                else:
                    number_of_days = 0

                leave_balance.lapsed = leave_balance.available - number_of_days
                leave_balance.available = number_of_days
                leave_balance.save(
                    activity_kwargs={"action": "reset", "days": number_of_days}
                )


@shared_task(name="deny_pending_leave_requests_older_than_today")
def deny_pending_leave_requests_older_than_today():

    activity_kwargs = {
        "action": "updated",
        "object": "status",
        "value": "denied",
        "metadata": "Denied by system",
    }

    current_date = read_data.get_current_datetime().date()
    leave_requests = LeaveRequest.objects.filter(
        Q(start_date__gt=current_date) & Q(status="pending")
    )

    for leave_request in leave_requests:
        leave_request.status = "denied"
        leave_request.save(activity_kwargs=activity_kwargs)
