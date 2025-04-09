from django.db.models import Q
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import login, logout, authenticate
from django.conf import settings
from utils.response import HTTP_400
from django.http import JsonResponse
from django.middleware.csrf import get_token
from rest_framework import generics, serializers, views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from visitor.serializers import VisitorSerializer
from django.db.models.functions import Lower
from api import permissions
from account.models import AuthToken, User, SessionToken
from member.models import Member
from organization.models import Organization
from django.http import HttpResponse

from django.contrib.auth.models import AnonymousUser

from account.serializers import UserSerializer
from member.serializers import MemberSerializer
from organization.serializers import OrganizationSerializer, RoleSerializer
from utils import create_data, fetch_data, email_funcs, read_data

import logging

from visitor.models import Visitor
from utils.utils import application_name_is_wrong

logger = logging.getLogger(__name__)


def get_csrf(request):

    return JsonResponse(
        {"detail": "CSRF cookie set", "X-CSRFToken": get_token(request)}
    )


class UserRegistrationAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):

        email = str(request.data.get("email", "")).strip()
        first_name = request.data.get("first_name")
        last_name = request.data.get("last_name")
        phone = request.data.get("phone")
        org_name = request.data.get("organization")
        city = request.data.get("city")

        if not email:
            return HTTP_400({}, {"message": "Email is required."})

        if not org_name:
            return HTTP_400({}, {"message": "organization is required."})

        if not first_name:
            return HTTP_400({}, {"message": "First Name is required."})

        if not city:
            return HTTP_400({}, {"message": "City Name is required."})

        user, user_created = create_data.create_user(email, first_name)

        # Create User
        # user, user_created = User.objects.get_or_create(email=email)

        # Create organization
        org = create_data.create_organization(org_name)

        default_shift = create_data.create_default_shift(org)
        org.default_shift = default_shift

        org_loc = create_data.create_org_loc(city, org)
        org.default_org_location = org_loc

        org.save()

        # Create member
        role = fetch_data.get_admin_role()
        create_data.create_member(org=org, user=user, role=role)

        if user_created:
            # user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            email_funcs.send_activation_mail(user)

        return Response(
            {
                "message": "Successfully created user/organization.",
            },
            status=status.HTTP_201_CREATED,
        )


class UserActivationAPI(views.APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):

        uuid = request.GET.get("uuid")
        token = request.GET.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        return Response({}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        # Validate UUID and Token
        uuid = request.data.get("uuid")
        token = request.data.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        # Set password
        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password is None or confirm_new_password is None:
            return Response(
                {"message": "Password needs to be provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_new_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.is_active = True
        user.save()

        # Deactivate the token
        session_token.delete()

        return Response(
            {"message": "Successfully activated your account"},
            status=status.HTTP_200_OK,
        )


class SetPasswordAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):
        user = request.user

        # user is not authenticated
        if isinstance(user, AnonymousUser):
            return Response(
                {"message": "User is not authenticated"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        current_password = request.data.get("current_password")
        if user.check_password(current_password) is False:
            return HTTP_400({}, {"message": "Invalid credentials"})

        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password != confirm_new_password:
            return HTTP_400({}, {"message": "Passwords do not match"})
        if new_password == "":
            return HTTP_400({}, {"message": "Enter a valid password"})

        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Successfully updated password"}, status=status.HTTP_200_OK
        )


class SetPasswordForMemberAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitorSerializer

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if not new_password:
            return HTTP_400({}, {"message": "New password is required."})

        if not confirm_new_password:
            return HTTP_400({}, {"message": "Confirm password is required."})

        if new_password != confirm_new_password:
            return Response(
                {"message": "Password does not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member_uuid = kwargs["uuid"]
        try:
            member = Member.objects.get(uuid=member_uuid, organization=org)
        except Member.DoesNotExist:
            return read_data.get_404_response("Member")

        if requesting_member.role.name == "hr" and member.role.name != "member":
            # HR can set pwd to member
            return read_data.get_403_response()

        # Set password
        user = member.user
        user.is_active=True
        user.set_password(new_password)
        user.save()

        return Response(
            {"message": "Password has been set"},
            status=status.HTTP_200_OK,
        )


class ValidatePasswordAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def post(self, request, *args, **kwargs):

        user = request.user
        current_password = request.data.get("current_password")
        is_valid = user.check_password(current_password)

        if is_valid:
            return Response({"message": "Valid credentials"}, status=status.HTTP_200_OK)

        return Response(
            {"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
        )


# class ForgotPasswordAPI(views.APIView):

#     permission_classes = []

#     def post(self, request, *args, **kwargs):

#         email = request.data.get("email")
#         email_funcs.password_reset_mail()

#         return Response(
#             {"message": "Password reset link has been sent to your email address"},
#             status=status.HTTP_201_CREATED,
#         )


class ForgotPasswordAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):

        email = request.data.get("email", "").lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist as e:
            return read_data.get_404_response("User")

        email_funcs.send_password_reset_mail(user)

        return Response(
            {"message": "Password reset link has been sent to your email address"},
            status=status.HTTP_201_CREATED,
        )


class PasswordResetAPI(views.APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):

        uuid = request.GET.get("uuid")
        token = request.GET.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        return Response({}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        # Validation uuid and Token
        uuid = request.data.get("uuid")
        token = request.data.get("token")

        try:
            user = User.objects.get(uuid=uuid)
        except (ValidationError, User.DoesNotExist) as e:
            logger.info(e)
            return read_data.get_404_response("User")

        try:
            session_token = SessionToken.objects.get(user=user, token=token)
        except (SessionToken.DoesNotExist) as e:
            return read_data.get_404_response("Token")

        # Set password
        new_password = request.data.get("new_password")
        confirm_new_password = request.data.get("confirm_new_password")

        if new_password != confirm_new_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()

        # Deactivate the token
        session_token.delete()

        return Response(
            {"message": "Password has been reset"},
            status=status.HTTP_200_OK,
        )


class TestAPI(views.APIView):

    permission_classes = []

    def get(self, request, *args, **kwargs):

        return Response({"message": "hello"}, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        return Response({"message": "Success"}, status=status.HTTP_201_CREATED)


class LoginAPI(views.APIView):

    permission_classes = []

    def post(self, request, *args, **kwargs):

        if application_name_is_wrong(request) is True:
            return Response(
                {"message": "Invalid domain name. Please enter the correct domain."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # User can provide either email or phone number
        username = request.data.get("username")
        password = request.data.get("password")

        if username is None:
            return Response(
                {"message": "Username is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if password is None:
            return Response(
                {"message": "Password is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        users = User.objects.filter(Q(email=username) | Q(phone=username))
        if not users.exists():
            return Response(
                {"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
            )
        temp_user = users.first()

        try:
            user = authenticate(request, username=temp_user.username, password=password)
            if user is not None:
                login(request, user)
        except (User.DoesNotExist) as e:
            logger.error(e)
            return Response(
                {"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f"Add exception for {e.__class__.__name__} in LoginAPI")
            logger.error(e)
            return Response(
                {"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
            )

        if user:
            org_uuid = request.headers.get("organization-uuid")
            org = fetch_data.get_organization(user, org_uuid)
            member = fetch_data.get_member(user, org.uuid)
            organization = member.organization
            if organization.status == "inactive":
                return Response(
                    {"message": "Organization inactive. Unable to login."}, status=status.HTTP_400_BAD_REQUEST
                )

        if user is not None:

            auth_tokens = user.auth_tokens.filter(active=True)
            if auth_tokens.count() == 0:
                auth_token = AuthToken.objects.create(
                    user=user,
                    name=create_data.generate_random_string(10),
                )
            else:
                auth_token = auth_tokens.order_by("-id").first()

            return Response({"token": auth_token.key}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
            )


class LogoutAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def post(self, request, *args, **kwargs):

        print(request.META.get("HTTP_AUTHORIZATION"))
        # logout(request)

        user = request.user

        # Delete token for mobile apps users
        token = request.META.get("HTTP_AUTHORIZATION")
        if token:
            token = token.split(" ")[1]
            user.auth_tokens.filter(key=token).delete()

        logout(request)

        return Response({}, status=status.HTTP_200_OK)


class UserDataAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        """ Return logged in user info
        """

        org_uuid = request.headers.get("organization-uuid")
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            visitor_or_member = fetch_data.get_member(request.user, org.uuid)
        except Member.DoesNotExist:
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            visitor_or_member = fetch_data.get_visitor(request.user, org.uuid)
        user = request.user

        role_serializer = RoleSerializer(visitor_or_member.role)

        addon_data = {}

        if visitor_or_member.role.name == "visitor":
            org_ids = list(
                Visitor.objects.filter(user=user).values_list(
                    "organization__id", flat=True
                )
            )

            serializer = VisitorSerializer(visitor_or_member)
        else:
            org_ids = list(
                Member.objects.filter(user=user).values_list(
                    "organization__id", flat=True
                )
            )

            # is_cluster_manager = False
            # if visitor_or_member.clusters.all().exists() is True:
            #     is_cluster_manager = True

            # addon_data["is_cluster_manager"] = is_cluster_manager

            org_location_obj = visitor_or_member.org_location_head.all()
            department_obj = visitor_or_member.department_head.all()

            addon_data["is_org_location_or_department_head"] = org_location_obj.exists() or department_obj.exists()

            serializer = MemberSerializer(visitor_or_member)

        organizations = Organization.objects.filter(id__in=org_ids)
        organization_serializer = OrganizationSerializer(organizations, many=True)

        user_serializer = UserSerializer(user)

        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": role_serializer.data,
            "organizations": organization_serializer.data,
            "user": user_serializer.data,
            "member": serializer.data,
        }

        return Response({**data, **addon_data}, status=status.HTTP_200_OK)


class SwitchOrganizationAPI(views.APIView):

    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get(self, request, *args, **kwargs):

        members = Member.objects.filter(user=request.user)
        org_ids = members.values_list("organization", flat=True)
        orgs = Organization.objects.filter(id__in=org_ids)

        serializer = OrganizationSerializer(orgs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):

        org.uuid = request.data.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        if org is None:
            return read_data.get_404_response("Organization")

        request.user.recent_organization_uuid = org.uuid
        request.user.save()

        return Response({}, status=status.HTTP_200_OK)





class FetchFileAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org_uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)


        path = self.kwargs.get("path")
        try:
            filename = path.split("/")[-1]
            file_instance_uuid = filename.split("__")[0]

            if "profile" in path:
                # logger.info(f"{path=}")
                file_member = fetch_data.get_member_by_uuid(org_uuid, file_instance_uuid)
                if file_member is None:
                    return read_data.get_404_response("Member")

                if member.organization != file_member.organization:
                    return read_data.get_403_response()

        except Exception as e:
            print(e)
            logger.error(e)
            logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")

        file_extension = filename.split(".")[-1]
        if file_extension in ["jpeg", "jpg", "png"]:
            response = HttpResponse(content_type=f"image/{file_extension}")
            try:
                with open(path, "rb") as img:
                    read_image = img.read()
                    response.write(read_image)
            except FileNotFoundError as e:
                print(e)

                logger.error(e)
                return read_data.get_404_response("File")
            except Exception as e:
                logger.error(e)
                print(e)

                logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")
                return Response(
                    {"message": "Unknown error occurred"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        elif file_extension in ["pdf"]:
            try:
                response = HttpResponse(content_type=f"application/{file_extension}")
                # response["Content-Disposition"] = f"attachment; filename={filename}"
                with open(path, "rb") as img:
                    read_image = img.read()
                    response.write(read_image)
            except Exception as e:
                logger.error(e)
                print(e)

                logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")
                return Response(
                    {"message": "Unknown error occurred"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif file_extension in ["csv"]:
            print("===================================================")
            print(path)
            print("===================================================")
            try:
                response = HttpResponse(content_type=f"text/{file_extension}")
                # response["Content-Disposition"] = f"attachment; filename={filename}"
                with open(path, "rb") as csv:
                    read_csv = csv.read()
                    response.write(read_csv)
            except Exception as e:
                logger.error(e)
                print(e)

                logger.exception(f"Add exception for {e.__class__.__name__} in FetchFileAPI")
                return Response(
                    {"message": "Unknown error occurred"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            return Response(
                {"message": "Unknown file extension"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return response
