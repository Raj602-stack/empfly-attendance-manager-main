import uuid
from account.models import User
from export.utils import create_export_request
from member.models import Member
from organization.models import Organization, OrgLocation, Role
from utils.email_funcs import visitor_welcome_email
from utils.utils import base64_to_contentfile, pagination
from visitor.models import Visitation, Visitor
from kiosk.serializers import KioskSerializer
from kiosk.utils import get_kiosk_object
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from django.core.paginator import Paginator
from django.db.models import Q
from kiosk.models import Kiosk
import datetime as dt
from django.core.exceptions import ValidationError
from kiosk.search import search_kiosks
from django.core.files.base import ContentFile
from django.db.utils import IntegrityError
import logging
from django.contrib.auth import login

from utils import create_data, fetch_data, read_data
from utils.response import HTTP_200, HTTP_400
from visitor.serializers import VisitorSerializer
from visitor.search import search_visitor_images, search_visitors

logger = logging.getLogger(__name__)


class AllVisitorAPI(views.APIView):
    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitorSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        search_query = request.GET.get("search")

        visitors = member.organization.visitor.all()
        visitor_status = request.GET.get("status", "active")

        if visitor_status in ("active", "inactive"):
            visitors = visitors.filter(status=visitor_status)

        visitors = search_visitors(visitors, search_query)

        if bool(request.GET.get("export_csv")) is True:
            if not visitors.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            visitors_ids = visitors.values_list("id", flat=True)
            export_request = create_export_request(member, "visitor", list(visitors_ids))
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(visitors, request)
        serializer = VisitorSerializer(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_front_desk(member) is False:
            return read_data.get_403_response()

        first_name = request.data.get("first_name", "").strip()
        last_name = request.data.get("last_name", "").strip()
        email = request.data.get("email", "").strip().lower()
        phone = request.data.get("phone", "").strip()
        visitor_status = request.data.get("status")


        if not first_name:
            return HTTP_400({}, {"message": "first name is required"})

        if not last_name:
            return HTTP_400({}, {"message": "last name is required"})

        if not email:
            return HTTP_400({}, {"message": "Email is required"})


        if visitor_status not in ("active", "inactive"):
            return HTTP_400({}, {"message": "Status must be active/inactive"})

        visitor = Visitor.objects.filter(user__email=email, organization=org)
        if visitor.exists():
            return read_data.get_409_response("Visitor", "email")

        host = Member.objects.filter(user__email=email, organization=org)
        if host.exists():
           return read_data.get_409_response("Member", "email")

        if email:
            # user, created = User.objects.get_or_create(email=email)
            user, created = create_data.create_user(email=email, first_name=first_name)

            if created:
                # user.first_name = first_name
                user.last_name = last_name
                if not User.objects.filter(phone = phone).exists():
                    user.phone = phone
                user.save()
                # TODO send activation email
                # email_funcs.send_activation_mail(user)



        role, create = Role.objects.get_or_create(name="visitor")

        try:
            visitor = Visitor.objects.create(
                user=user,
                organization=org,
                status=visitor_status,
                role=role,
                # photo=photo,
            )
            # visitor.authorized_kiosks.add(*authorized_obj)
            visitor.save()

            visitor_welcome_email(visitor)

        except IntegrityError:
            return read_data.get_409_response("Visitor", "user")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllVisitorAPI"
            )
            return read_data.get_409_response("Visitor", "user")

        serializer = self.serializer_class(visitor)
        return HTTP_200(serializer.data)


class VisitorAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitorSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        visitor_uuid = self.kwargs.get("uuid")
        try:
            visitors = member.organization.visitor.get(uuid=visitor_uuid)
        except Visitor.DoesNotExist as e:
            logger.error(e)
            return HTTP_400({}, {"message": "Visitor not found"})

        serializer = self.serializer_class(visitors)
        return HTTP_200(serializer.data)


    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_front_desk(member) is False:
            return read_data.get_403_response()

        visitor_uuid = self.kwargs.get("uuid")
        try:
            visitor = member.organization.visitor.get(uuid=visitor_uuid)
            user = visitor.user
        except Visitor.DoesNotExist as e:
            logger.error(e)
            return HTTP_400({}, {"message": "Visitor not found"})
        
        first_name = request.data.get("first_name", user.first_name).strip()
        last_name = request.data.get("last_name", user.last_name).strip()
        email = request.data.get("email", user.email).strip()
        phone = request.data.get("phone", user.phone)
        phone = phone.strip() if isinstance(phone, str) else phone
        visitor_status = request.data.get("status")

        email = email.lower()

        email_is_differ = False
        if email != user.email:
            email_is_differ = True

        is_visitor = Visitor.objects.filter(user__email=email, organization=org).exclude(uuid=visitor_uuid)
        if is_visitor.exists():
            return read_data.get_409_response("Visitor", "email")

        host = Member.objects.filter(user__email=email, organization=org).exclude(uuid=visitor_uuid)
        if host.exists() and host.first().allowed_to_meet is False:
           return read_data.get_409_response("Member", "email")

        if first_name:
            visitor.user.first_name = first_name

        if last_name:
            visitor.user.last_name = last_name

        if not User.objects.filter(email=email).exists():
            visitor.user.email = email

        if phone:
            if User.objects.exclude(uuid=user.uuid).filter(phone=phone).exists() is False:
                visitor.user.phone = phone
        else:
            visitor.user.phone = None

        visitor.status = visitor_status

        try:
            visitor.save()
            visitor.user.save()

            # Visitor changed the email send welcome email to the new email.
            if email_is_differ is True:
                visitor_welcome_email(visitor)

        except IntegrityError:
            return read_data.get_409_response("Visitor", "user")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in AllVisitorAPI"
            )
            return read_data.get_409_response("Visitor", "user")

        serializer = self.serializer_class(visitor)
        return HTTP_200(serializer.data)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        visitor_uuid = self.kwargs.get("uuid")
        try:
            visitor = member.organization.visitor.get(uuid=visitor_uuid)
        except Visitor.DoesNotExist as e:
            logger.error(e)
            return HTTP_400({}, {"message": "Visitor not found"})

        visitor.delete()
        return HTTP_200({"message": "Successfully deleted visitor"})


class AllVisitorRegisterAPI(views.APIView):

    permission_classes = []
    serializer_class = VisitorSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
        requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)

        if fetch_data.is_visitor(requesting_visitor) is False:
            return read_data.get_403_response()

        serializer = self.serializer_class( requesting_visitor )
        return HTTP_200(serializer.data)

    def post(self, request, *args, **kwargs):

        first_name = request.data.get("first_name", "").strip()
        last_name = request.data.get("last_name", "").strip()
        email = request.data.get("email", "").strip().lower()
        phone = request.data.get("phone", "").strip()
        company_name = request.data.get("company_name", "").strip()

        org_location = request.data.get("org_uuid")

        if not first_name:
            return HTTP_400({}, {"message": "First name is required"})

        if not last_name:
            return HTTP_400({}, {"message": "Last name is required"})

        if not email:
            return HTTP_400({}, {"message": "Email is required"})

        if not phone:
            return HTTP_400({}, {"message": "Phone is required"})

        if not company_name:
            return HTTP_400({}, {"message": "Company Name is required"})

        org_location = OrgLocation.objects.filter(uuid=org_location)
        if not org_location.exists():
            return HTTP_400({}, {"message": "Organization Location is required"})
        org_location = org_location.first()

        organization = org_location.organization

        if Visitor.objects.filter(user__email=email, organization=organization).exists():
            return read_data.get_409_response("Visitor", "email")
        if Member.objects.filter(user__email=email,  organization=organization).exists():
            return Response(
                {"message": "Your account already exists. Please check with Empfly Admin.",},
                status=status.HTTP_409_CONFLICT
            )


        # user, create = User.objects.get_or_create(email=email)
        user, created = create_data.create_user(email=email, first_name=first_name)

        if created:
            user.first_name=first_name
            user.last_name=last_name
            user.is_active = True
            if not User.objects.filter(phone=phone).exists():
                user.phone=phone
            user.save()

        visitor = Visitor.objects.create(
            user=user,
            visitor_company=company_name,
            role=Role.objects.get_or_create(name="visitor")[0],
            organization=organization
        )

        login(request, user)

        serializer = self.serializer_class( visitor )
        return HTTP_200(serializer.data)
