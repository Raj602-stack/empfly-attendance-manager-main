from django.core.exceptions import ValidationError

from account.models import User
from member.models import Member
from organization.models import (
    # City,
    CostCenter,
    # Country,
    Department,
    Designation,
    Holiday,
    Organization,
    OrgLocation,
    Role,
    # State,
)

import uuid as uuid4
import logging


logger = logging.getLogger(__name__)


# * Role


def get_member_role() -> Role:
    role, created = Role.objects.get_or_create(name="member")
    return role


def get_finance_role() -> Role:
    role, created = Role.objects.get_or_create(name="finance")
    return role


def get_hr_role() -> Role:
    role, created = Role.objects.get_or_create(name="hr")
    return role


def get_admin_role() -> Role:
    role, created = Role.objects.get_or_create(name="admin")
    return role


def is_admin_or_hr(member: Member) -> Role:
    roles = Role.objects.filter(name__icontains=["admin", "hr"])
    if member.role in roles:
        return True
    return False


def is_admin(member: Member) -> bool:
    if member.role == get_admin_role():
        return True
    return False


# * Organization


def get_organization(user: User, organization_uuid: uuid4) -> Organization:

    if organization_uuid is None:
        member = Member.objects.get(user=user)
        return member.organization

    try:
        organization = Organization.objects.get(uuid=organization_uuid)
    except (Organization.DoesNotExist, ValidationError) as e:
        logging.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_organization")
        logger.error(e)
        return None

    if organization.members.filter(user=user).exists():
        return organization
    else:
        logging.exception(f"{user} provided another organization's uuid")
        return None


def get_department(org_uuid: uuid4, department_uuid: uuid4) -> Department:

    try:
        return Department.objects.get(uuid=department_uuid, organization__uuid=org_uuid)
    except (Department.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_department")
    return None


def get_cost_center(org_uuid: uuid4, cost_center_uuid: uuid4) -> Department:

    try:
        return CostCenter.objects.get(
            uuid=cost_center_uuid, organization__uuid=org_uuid
        )
    except (CostCenter.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_cost_center")
    return None


def get_holiday(org_uuid: uuid4, holiday_uuid: uuid4) -> Holiday:

    try:
        return Holiday.objects.get(uuid=holiday_uuid, organization__uuid=org_uuid)
    except (Holiday.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_holiday")
    return None


def get_designation(org_uuid: uuid4, designation_uuid: uuid4) -> Designation:

    try:
        return Designation.objects.get(
            uuid=designation_uuid, organization__uuid=org_uuid
        )
    except (Designation.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_designation")
    return None


def get_country(uuid: uuid4):

    try:
        return Country.objects.get(uuid=uuid)
    except (Country.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_country")
    return None


def get_state(uuid: uuid4):

    try:
        return State.objects.get(uuid=uuid)
    except (State.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_state")
    return None


def get_city(uuid: uuid4):

    try:
        return City.objects.get(uuid=uuid)
    except (City.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_city")
    return None


def get_org_location(uuid: uuid4) -> OrgLocation:

    try:
        return OrgLocation.objects.get(uuid=uuid)
    except (OrgLocation.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_org_location"
        )
    return None
