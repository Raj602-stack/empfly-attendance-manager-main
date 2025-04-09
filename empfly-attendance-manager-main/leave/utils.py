from django.core.exceptions import ValidationError

from organization.models import Organization
from leave.models import (
    ApprovalWorkflow,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    RegularizationWorkflow,
)
from member.models import Member

import uuid as uuid4
import logging


logger = logging.getLogger(__name__)


# * Leave


def get_leave_type(organization_uuid: uuid4, uuid: uuid4) -> LeaveType:
    try:
        return LeaveType.objects.get(organization__uuid=organization_uuid, uuid=uuid)
    except (LeaveType.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in get_leave_type")
    return None


def get_leave_balance(member_uuid: uuid4, leave_type_uuid: uuid4) -> LeaveType:
    try:
        return LeaveBalance.objects.get(
            member__uuid=member_uuid, leave_type__uuid=leave_type_uuid
        )
    except (LeaveBalance.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_leave_balance"
        )
    return None


def get_leave_request(organization_uuid: uuid4, uuid: uuid4) -> LeaveType:
    try:
        return LeaveRequest.objects.get(
            member__organization__uuid=organization_uuid, uuid=uuid
        )
    except (LeaveRequest.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_leave_request"
        )
    return None


# * Approval Workflow


def get_approval_workflow(organization_uuid: uuid4, uuid: uuid4) -> ApprovalWorkflow:
    try:
        return ApprovalWorkflow.objects.get(
            organization__uuid=organization_uuid, uuid=uuid
        )
    except (ApprovalWorkflow.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_approval_workflow"
        )
    return None


def get_assocaited_approval_workflow(member: Member) -> ApprovalWorkflow:

    org = member.organization
    variable_priority = org.settings.get("variable_priority", [])

    for variable in variable_priority:

        if variable == "member" and member.approval_workflow is not None:
            return member.approval_workflow

        elif (
            variable == "designation"
            and member.designation is not None
            and member.designation.approval_workflow is not None
        ):
            return member.designation.approval_workflow

        elif (
            variable == "department"
            and member.department is not None
            and member.department.approval_workflow is not None
        ):
            return member.department.approval_workflow

        elif (
            variable == "location"
            and member.org_location is not None
            and member.org_location.approval_workflow is not None
        ):
            return member.org_location.approval_workflow

        elif (
            variable == "role"
            and member.role is not None
            and member.role.approval_workflow is not None
        ):
            return member.role.approval_workflow

        return None


# * Regularization Workflow


def get_regularization_workflow(
    organization_uuid: uuid4, uuid: uuid4
) -> RegularizationWorkflow:
    try:
        return RegularizationWorkflow.objects.get(
            organization__uuid=organization_uuid, uuid=uuid
        )
    except (RegularizationWorkflow.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_regularization_workflow"
        )
    return None


def check_condition(field_value: str, condition: str, value: str) -> bool:

    if condition == "is":
        return field_value in value
    elif condition == "is_not":
        return field_value not in value
    return True


def check_criteria(member: Member, criteria: dict) -> bool:

    object = criteria.get("object")
    condition = criteria.get("condition")
    value = criteria.get("value")

    if object is None or condition is None:
        logger.error(f"Invalid {criteria=}")
        return True

    try:
        value = value.lower()
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in check_criteria")
        return False

    if object == "designation":
        return check_condition(str(member.designation.uuid), condition, value)

    return True


def is_approval_workflow_allowed(
    member: Member, approval_workflow: ApprovalWorkflow
) -> bool:

    criterias = approval_workflow.criteria.get("criterias", [])
    match_any = approval_workflow.criteria.get("match_any", True)
    match_all = approval_workflow.criteria.get("match_all", False)

    # Sort criterias by order (desc)
    criterias = sorted(criterias, key=lambda x: x.get("order", 99), reverse=True)

    criteria_results = []
    for criteria in criterias:
        result = check_criteria(member, criteria)
        criteria_results.append(result)

    if match_any:
        return any(criteria_results)
    return all(criteria_results)


def get_default_approval_workflow(organization: Organization) -> ApprovalWorkflow:
    approval_workflow, created = ApprovalWorkflow.objects.get_or_create(
        organization=organization, name="Default Workflow"
    )
    if created:
        approval_workflow.criteria = {
            "auto_approval": False,
            "department_head": None,
            "members": [],
            "hr": True,
            "admin": True,
        }
        approval_workflow.approval_types = {
            "auto_approval": False,
            "department_head": None,
            "members": {},
            "hr": True,
            "admin": None,
        }
        approval_workflow.save()

    return approval_workflow
