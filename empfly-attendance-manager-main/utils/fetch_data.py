from django.core.exceptions import ValidationError

from account.models import User
from member.models import Member
from organization.models import Organization, Role

from uuid import uuid4

import logging
import json

from visitor.models import Visitor


logger = logging.getLogger(__name__)

# TODO deprecated
def get_user_data(user: User) -> dict:

    data = {
        "uuid": user.uuid,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "timezone": user.profile.timezone,
        "avatar_url": None,
        "organizations": [],
        "last_accessed_organization": None,
    }

    organization_ids = Member.objects.filter(user=user).values_list(
        "organization__id", flat=True
    )
    organizations = Organization.objects.filter(id__in=organization_ids)

    organization_list = []
    for organization in organizations:

        organization_dict = {
            "uuid": organization.uuid,
            "name": organization.name,
        }
        organization_list.append(organization_dict)

    data["organizations"] = organization_list

    return data


# * Account

# TODO deprecated
def get_user(user_uuid: uuid4) -> User:

    try:
        return User.objects.get(uuid=user_uuid)
    except (User.DoesNotExist, ValidationError) as e:
        logging.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_user")
        logger.error(e)
        return None


# * Member


def get_member(user: User, organization_uuid: uuid4) -> Member:
    """ Get member obj using user and org uuid.
    """

    try:
        return Member.objects.get(user=user, organization__uuid=organization_uuid)
    except Member.DoesNotExist as e:
        logging.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_member")
        logger.error(e)
        return None


def get_member_by_uuid(org_uuid: uuid4, uuid: uuid4) -> Member:
    """ Get member obj using uuid of member and org uuid.
    """

    if org_uuid is None:
        return Member.objects.get(uuid=uuid)

    try:
        return Member.objects.get(uuid=uuid, organization__uuid=org_uuid)
    except (Member.DoesNotExist, ValidationError, ValueError) as e:
        logger.error(e)
    except Exception as e:
        logger.exception(
            f"Add exception for {e.__class__.__name__} in get_member_by_uuid"
        )
    return None

# TODO deprecated
def has_access(
    organization_uuid: uuid4, requesting_user: User, resouce_type: str, resource
) -> bool:

    requesting_member = get_member(requesting_user, organization_uuid)
    if requesting_member is None:
        return False

    if resouce_type == "member":
        try:
            if (
                requesting_member.id != resource.id
                and requesting_member.role != get_admin_role()
            ):
                return False
            return True
        except Exception as e:
            logger.exception(f"Add exception for {e.__class__.__name__} in has_access")
            logger.error(e)
            return False

    return False


# * Roles


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

def get_visitor_role() -> Role:
    role, created = Role.objects.get_or_create(name="visitor")
    return role

def is_admin_or_hr(member: Member) -> Role:
    roles = Role.objects.filter(name__in=["admin", "hr"])
    if member.role in roles:
        return True
    return False

def is_admin_hr_front_desk(member: Member) -> Role:
    roles = Role.objects.filter(name__in=["admin", "hr"])
    if member.role in roles:
        return True

    return member.is_front_desk


def is_admin(member: Member) -> bool:
    if member.role == get_admin_role():
        return True
    return False

def is_admin_or_front_desk(member: Member) -> bool:
    if member.role == get_admin_role():
        return True
    
    return member.is_front_desk


def is_admin_hr_member(member: Member) -> bool:
    roles = Role.objects.filter(name__in=["admin", "hr", "member"])
    if member.role in roles:
        return True
    return False

def is_front_desk(member: Member) -> bool:
    return member.is_front_desk
# * Organization

# def is_admin_hr_member_visitor(member: Member) -> bool:
#     roles = Role.objects.filter(name__in=["admin", "hr", "member"])
#     if member.role in roles:
#         return True
#     return False

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



def get_organization_as_visitor(user: User, organization_uuid: uuid4) -> Organization:
    """ Get visitor organization using user and org uuid.
    """

    if organization_uuid is None:
        visitor = Visitor.objects.get(user=user)
        return visitor.organization

    try:
        organization = Organization.objects.get(uuid=organization_uuid)
    except (Organization.DoesNotExist, ValidationError) as e:
        logging.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_organization")
        logger.error(e)
        return None

    if organization.visitor.filter(user=user).exists():
        return organization
    else:
        logging.exception(f"{user} provided another organization's uuid")
        return None


def get_visitor(user: User, organization_uuid: uuid4) -> Member:

    try:
        return Visitor.objects.get(user=user, organization__uuid=organization_uuid)
    except Visitor.DoesNotExist as e:
        logging.error(e)
        return None
    except Exception as e:
        logger.exception(f"Add exception for {e.__class__.__name__} in get_visitor")
        logger.error(e)
        return None

def is_visitor(visitor:Visitor) -> bool:
    if get_visitor_role() == visitor.role:
        return True
    return False

def is_admin_hr_member_visitor(user):
    roles = Role.objects.filter(name__in=["admin", "hr", "member", "visitor"])
    if user.role in roles:
        return True
    return False