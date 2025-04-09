from typing import Tuple, Union
from member.models import Member
from organization.models import Organization, Role
from utils import fetch_data
from visitor.models import Visitor
from rest_framework.request import Request



def authenticate_visitor_or_member(request:Request) -> Tuple[Organization, Union[Member, Visitor]]:
    """ get the visitor or member using request.user.
        If user is not member we will check the request.user exists in visitor or not
    """
    org_uuid = request.headers.get('organization-uuid')
    try:
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)
        # role = member.role.name
        requesting_user = member
    except Member.DoesNotExist:
        org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
        visitor = fetch_data.get_visitor(request.user, org.uuid)
        # role = visitor.role.name
        requesting_user = visitor

    return org, requesting_user
