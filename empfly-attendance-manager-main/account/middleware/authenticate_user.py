from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework import status
from visitor.models import Visitor
from member.models import Member
from utils import fetch_data
from django.http import JsonResponse
from account.authentication import TokenAuthentication

class AuthenticateUser:
    """ Check member or visitor is inactive.
        If user is inactive they cannot access any page.
    """
    def __init__(self, get_response):
        self.get_response = get_response


    def get_request_user(self, request):
        """
        Function used to get user from request
        if request has token in request header using that we can take user
        else we can take session authentication request.user as user
        """
        try:
            return TokenAuthentication().authenticate(request)[0]
        except Exception as error:
            print(error)
            print("!!!!!!!!!!!! authentication for web !!!!!!!!!!!!")
            return request.user

    def __call__(self, request):
        print("")
        print("")
        print("************************* AuthenticateUser function started *************************")

        if "logout" in request.build_absolute_uri() or "login" in request.build_absolute_uri():
            print("========= Logout in url =========")
            response = self.get_response(request)
            return response


        user = self.get_request_user(request)
        if user.is_anonymous is True:
            print("======= User not found ==========")
            response = self.get_response(request)
            return response

        req_member, req_visitor = None, None

        print(f"user : {user}")

        # Check user is member or not
        try:
            org_uuid = request.headers.get("organization-uuid")
            org = fetch_data.get_organization(user, org_uuid)
            req_member = fetch_data.get_member(user, org.uuid)
        except Member.DoesNotExist:
            pass

        print(f"Member : {req_member}")

        if req_member is not None:
            if req_member.status == "inactive":
                return JsonResponse({'message': 'Member is inactive.'}, status=403)

            response = self.get_response(request)
            return response


        #  Check user is visitor or not
        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            req_visitor = fetch_data.get_visitor(request.user, org.uuid)
        except Visitor.DoesNotExist:
            pass

        print(f"Visitor: {req_visitor}")
        
        if req_visitor is not None:
            if req_visitor.status == "inactive":
                return JsonResponse({'message': 'Member is inactive.'}, status=403)

            response = self.get_response(request)
            return response

        response = self.get_response(request)
        return response