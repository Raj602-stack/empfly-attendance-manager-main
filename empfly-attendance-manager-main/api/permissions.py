from xml.sax.handler import feature_external_ges
from rest_framework.permissions import BasePermission

from member.models import Member
from utils import fetch_data


class IsTokenAuthenticated(BasePermission):
    """ Allows access only to Token Authenticated users
    """

    def has_permission(self, request, view):
        """ request.auth is used for mobile login. In mobile phones we use token phone auth
            request.user is for session auth means for web.
        """

        if bool(request.auth) or bool(request.user and request.user.is_authenticated):
            return True
        return False


class IsAdmin(BasePermission):
    """
    Allows access only to Token Authenticated users
    """

    def has_permission(self, request, view):

        if bool(request.auth) or bool(request.user and request.user.is_authenticated):
            member = Member.objects.get(user=request.user)
            return member.role == fetch_data.get_admin_role()
        return False
