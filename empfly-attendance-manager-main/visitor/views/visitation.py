from email import message
import email
from os import read
from account.models import SessionToken, User
from export.utils import create_export_request
from kiosk.models import Kiosk
from member.models import Member
import organization
from organization.models import Organization, OrgLocation, Role
from organization.serializers import OrganizationSerializer
from rest_framework import views, status
from api import permissions
from utils import create_data, fetch_data, read_data
from utils.email_funcs import send_visitation_request_mail, send_bulk_visitation_update_email
from utils.response import HTTP_200, HTTP_400
from utils.shift import notify_on_visitation_update, send_visitation_email_on_update
from utils.utils import base64_to_contentfile, convert_to_time, pagination
import datetime as dt
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from rest_framework.response import Response
# import asyncio
from account.serializers import UserSerializer
from utils import date_time


import logging
from visitor.filters import convert_query_params_to_dict, filter_visitations, filter_visitor_scan

from visitor.models import Visitation, Visitor, VisitorScan
from visitor.search import search_visitations, search_visitor_scan
from visitor.serializers import VisitationSerializer, VisitorScanSerializer, VisitorSerializer
# from visitor.utils import AllVistationCRUD, VisitationCRUD
from visitor.validations import validate_visitation
logger = logging.getLogger(__name__)



class AllVisitationRegisterAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitorScanSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        visitor_scan = VisitorScan.objects.filter(organization=org)

        # Other than user role is member he can see his date only
        if fetch_data.is_admin_hr_front_desk(member) is False:
            visitor_scan = visitor_scan.filter(visitation__host=member)

        visitor_status = request.GET.get("status", "active")
        if visitor_status in ("active", "inactive"):
            visitor_scan = visitor_scan.filter(visitor__status=visitor_status)

        visitor_scan = filter_visitor_scan(visitor_scan, request)
        visitor_scan = search_visitor_scan(visitor_scan, request.GET.get("search"))

        if bool(request.GET.get("export_csv")) is True:
            if not visitor_scan.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            departments_ids = visitor_scan.values_list("id", flat=True)
            export_request = create_export_request(member, "visitation_register", list(departments_ids))
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})


        page_obj, num_pages, page = pagination(visitor_scan, request)
        serializer = self.serializer_class( page_obj.object_list, many=True )
        return Response(
            {
                "data": serializer.data,
                "organization": OrganizationSerializer(org).data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )



class GetAllVisitationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_front_desk(member) is False:
            return read_data.get_403_response()

        visitations = Visitation.objects.filter(visitor__organization=org)

        visitations = search_visitations(visitations, request.GET.get("search"))
        visitations = filter_visitations(visitations, request)

        if bool(request.GET.get("export_csv")) is True:

            if not visitations.exists():
                return HTTP_400({}, {"message": "No data found for export csv."})

            visitations_ids = visitations.values_list("id", flat=True)
            export_request = create_export_request(member, "visitations", list(visitations_ids))
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(visitations, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class AllUsersCreatedVisitationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = UserSerializer

    def get(self, request, *args, **kwargs):
        """ created by field in visitation is connected to user model.
            Only users that created visitation will output here.
        """

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        # if fetch_data.is_admin(member) is False:
        #     return read_data.get_403_response()

        users_created_visitation = Visitation.objects.values_list("created_by__id")

        users = User.objects.filter(id__in=users_created_visitation, is_active=True)

        print(users)

        serializer = self.serializer_class( users, many=True )
        return HTTP_200(serializer.data)





class VisitationConfirmationAPI(views.APIView):
    """ Change visitation status.
        After user click the accept/decline button in the visitation email this req will happen.
    """

    permission_classes = []
    serializer_class = VisitationSerializer

    def post(self, request, *args, **kwargs):

        uuid = request.data.get("uuid")
        token = request.data.get("token")
        user_status = request.data.get("status")

        if user_status not in ("accepted", "declined"):
            return read_data.get_404_response("Status")
        
        # Check user req is valid or not.
        try:
            session_token = SessionToken.objects.get(token=token)
        except (SessionToken.DoesNotExist):
            return read_data.get_404_response("Token")

        # Get user from token provided.
        try:
            user = session_token.user
            visitation = Visitation.objects.get(uuid=uuid)
            if visitation.visitor.user == user:
                role = visitation.visitor.role.name
            elif visitation.host.user == user:
                role = visitation.host.role.name
            else:
                raise Visitation.DoesNotExist
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        host_status = visitation.host_status
        visitor_status = visitation.visitor_status
        visitation_status = visitation.visitation_status

        if visitation_status in ("cancelled", "scheduled", "completed"):
            return HTTP_400({}, {"message": f"Visitation {visitation_status}."})

        host_roles = ("admin", "hr", "member")

        # Email function can send_bulk_visitation_update_email or send_visitation_request_mail
        email_fun = send_bulk_visitation_update_email
        email_content = []

        # Inactive org location
        if visitation.org_location and visitation.org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org location is inactive."})

        org_location = visitation.org_location
        if org_location and org_location.enable_visitation is False:
            return HTTP_400({}, {"message": "Visitations are disabled for this Org Location."})

        # Inactive host or visitor doest have any permission
        if role in host_roles and visitation.host.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})
        elif role == "visitor" and visitation.visitor.status == "inactive":
            return HTTP_400({}, {"message": "Visitor is inactive."})

        # email_content -> Email content hold the data for send the email. This content is passed to send_visitation_email_on_update fun.

        if (role == "visitor") and (host_status == "accepted") and (visitor_status == "pending") and visitation.visitor.user == user:
            # Logged in User is visitation.
            # Visitation is scheduled.
            
            if user_status == "accepted":
                visitor_status = "accepted"
                visitation_status = "scheduled"

                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": "Visitation is scheduled"
                    },
                    {
                        "to": visitation.visitor.user,
                        "visitation": visitation,
                        "message": "Visitation is scheduled"
                    },
                ]
            elif user_status == "declined":
                visitor_status = "rejected"
                visitation_status = "cancelled"

                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": "Visitation is declined by visitor"
                    },
                ]

        elif (role in host_roles) and (visitor_status == "accepted") and (host_status == "pending") and visitation.host.user == user:
            # Logged in User is Host.

            if user_status == "accepted":
                # Visitation is scheduled.

                host_status = "accepted"
                visitation_status = "scheduled"

                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": "Visitation is scheduled"
                    },
                    {
                        "to": visitation.visitor.user,
                        "visitation": visitation,
                        "message": "Visitation is scheduled"
                    },
                ]

            elif user_status == "declined":
                host_status = "rejected"
                visitation_status = "cancelled"

                email_content = [
                    {
                        "to": visitation.visitor.user,
                        "visitation": visitation,
                        "message": "Your Visitation is declined by host"
                    },
                ]

        elif (role in host_roles) and (visitor_status == "pending") and (host_status == "pending") and visitation.host.user == user:
            # Logged in user is host.

            if user_status == "accepted":
                # Send request to visitor for veryfication.

                host_status = "accepted"

                user_name = create_data.get_user_name(visitation.host.user)
                # send email to visitor
                email_content = {
                    "to": visitation.visitor.user,
                    "visitation": visitation,
                    "message": f"{user_name} sent you a Visitation Request"
                }
                email_fun = send_visitation_request_mail

            elif user_status == "declined":
                host_status = "rejected"
                visitation_status = "cancelled"
        else:
            return read_data.get_404_response("Visitation")

        visitation.host_status = host_status
        visitation.visitor_status = visitor_status
        visitation.visitation_status = visitation_status

        visitation.save()
        session_token.delete()

        # send email
        # email_fun(email_content)
        send_visitation_email_on_update(visitation, request.user)

        serializer = self.serializer_class( visitation )
        return HTTP_200(serializer.data)


class VisitationScanAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitorScanSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
        requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)

        if fetch_data.is_visitor(requesting_visitor) is False:
            return read_data.get_403_response()

        visitor_scans = VisitorScan.objects.filter(
            visitor=requesting_visitor,
            visitor__organization=org
        )
        serializer = self.serializer_class(visitor_scans, many=True)
        return HTTP_200(serializer.data)

    def post(self, request, *args, **kwargs):
        """ Create scan for visitor. For creating scan user role must be visitor
        """
        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
        requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)

        if fetch_data.is_visitor(requesting_visitor) is False:
            return read_data.get_403_response()

        visitation_uuid = request.data.get("visitation")
        photo = request.data.get("photo")
        time = request.data.get("time")
        date = request.data.get("date")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        temperature = request.data.get("temperature")

        if not visitation_uuid:
            return HTTP_400({}, {"message": "Visitation not found"})

        if not date:
            return HTTP_400({}, {"message": "date not found"})

        if not time:
            return HTTP_400({}, {"message": "time not found"})

        if not latitude:
            return HTTP_400({}, {"message": "latitude not found"})

        if not longitude:
            return HTTP_400({}, {"message": "longitude not found"})

        if not photo:
            return HTTP_400({}, {"message": "photo not found"})

        if not temperature:
            return HTTP_400({}, {"message": "Temperature not found"})

        time = dt.datetime.strptime(time, "%H:%M:%S")

        content = base64_to_contentfile(photo)
        if isinstance(content, ContentFile):
            photo = content
        elif isinstance(content, Response):
            return content

        visitation = Visitation.objects.filter(
            uuid=visitation_uuid,
            visitor__user = request.user
        )
        if not visitation.exists():
            return HTTP_400({}, {"message": "Visitation not found."})
        visitation = visitation.first()


        if visitation.host.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if visitation.visitor.status == "inactive":
            return HTTP_400({}, {"message": "Visitor is inactive."})

        if visitation.org_location and visitation.org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org Location is inactive."})


        # TODO check
        # if visitation.visitation_date != dt.date.today():
        if visitation.visitation_date != date_time.today_date():
            return HTTP_400({}, {"message": "Visitation is not scheduled for today. Please check Visitation date."})

        if visitation.org_location.enable_visitation is False:
            return HTTP_400({},{"message": "Visitations are disabled for this Org Location."})

        visitor = request.user.visitor.get()

        kiosk = Kiosk.objects.get_or_create(kiosk_name="Web Kiosk", organization=org)[0]
        location = f"{latitude},{longitude}"

        visitor_scan = VisitorScan.objects.create(
            visitor=visitor,
            visitation=visitation,
            photo=photo,
            date=date,
            time=time.time(),
            kiosk=kiosk,
            location=location,
            temperature=temperature,
            organization=org
        )
        
        visitation = visitor_scan.visitation
        visitation.visitation_status = "completed"
        visitation.save()

        serializer = self.serializer_class( visitor_scan )
        return HTTP_200(serializer.data)




# ============ for member ============
class AllVisitationAPI(views.APIView):
    """ Get own visitations, create visitation
        Create visitation for member, admin, hr.
    """

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitationSerializer

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get('organization-uuid')
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            requesting_member = fetch_data.get_member(request.user, org.uuid)
            user_role = requesting_member.role.name
            requesting_user = requesting_member
        except Member.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_admin_hr_member(requesting_user) is False:
            return read_data.get_403_response()

        visitations = Visitation.objects.filter(visitor__organization__id=org.id)
        if user_role in ("admin", "hr", "member"):
            visitations = visitations.filter(host=requesting_member)

        visitations = search_visitations(visitations, request.GET.get("search"))
        visitations = filter_visitations(visitations, request)

        if bool(request.GET.get("export_csv")) is True:

            if not visitations.exists():
                return HTTP_400({}, {"message": "No data found for export csv."})

            visitations_ids = visitations.values_list("id", flat=True)
            export_request = create_export_request(requesting_member, "visitations", list(visitations_ids))
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(visitations, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        """ Visitation Flow
        =======================
        - create visitation for my-self (minimum role = member)
        - create visitation by admin or hr
        - create visitation as visitor

        Ref : https://www.notion.so/peerxp/Visitations-Visitations-bfec996c955a4a1eb1ce9aab980dd041
        """

        org_uuid = request.headers.get('organization-uuid')

        # User is must be a member or a visitor
        org_uuid = request.headers.get('organization-uuid')
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            requesting_member = fetch_data.get_member(request.user, org.uuid)
            user_role = requesting_member.role.name
            requesting_user = requesting_member
        except Member.DoesNotExist:
            return read_data.get_403_response()
        # if user_role not in ("admin", "hr", "member", "visitor"):
        #     return read_data.get_403_response()

        if fetch_data.is_admin_hr_member(requesting_user) is False:
            return read_data.get_403_response()
        print("###########################")
        res_or_data = validate_visitation(request, user_role, requesting_member)
        if isinstance(res_or_data, Response):
            return res_or_data

        name = res_or_data.get("name", "")
        description = res_or_data.get("description", "")
        visitor = res_or_data.get("visitor")
        host = res_or_data.get("host")
        visitation_date = res_or_data.get("visitation_date")
        start_time = res_or_data.get("start_time")
        end_time = res_or_data.get("end_time")
        org_location = res_or_data.get("org_location")


        if host.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if visitor.status == "inactive":
            return HTTP_400({}, {"message": "Visitor is inactive."})

        if org_location and org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org Location is inactive."})

        if org_location and org_location.enable_visitation is False:
            return HTTP_400({}, {"message": "Visitations are disabled for this Org Location."})

        created_by = request.user # logged in user

        # visitor create visitation and host conf in org settings is False
        visitation_completed = False

        if user_role == "visitor":
            # If visitor is creating visitation host conf is required.
            # if host_confirmation in the org settings is true right away scheduled visitation.

            visitor_org = request.user.visitor.get().organization
            host_confirmation = visitor_org.settings.get("host_confirmation")

            print(host_confirmation, "host_confirmation")

            if host_confirmation is True:
                host_status = "pending"
                visitor_status = "accepted"
                visitation_status = "created"

                # email to host
                user = host.user
                user_name = create_data.get_user_name(visitor.user)
                message = f"{user_name} sent you a Visitation Request"

            elif host_confirmation is False:
                host_status = "accepted"
                visitor_status = "accepted"
                visitation_status = "scheduled"

                visitation_completed = True
                message = "Visitation is scheduled"

        elif created_by == host.user:
            # create visitation for my self
            # Host is creating visitation. Visitor confirmation is required.
            host_status = "accepted"
            visitor_status = "pending"
            visitation_status = "created"

            # email to visitor
            user = visitor.user
            user_name = create_data.get_user_name(host.user)
            message = f"{user_name} sent you a Visitation Request"

        elif user_role in ("admin", "hr"): # create visitation  for other member
            # Host and visitor confirmation required.

            host_status = "pending"
            visitor_status = "pending"
            visitation_status = "created"

            # email to host
            user = host.user
            user_name = create_data.get_user_name(request.user)
            message = f"{user_name} sent you a Visitation Request"

        visitation = Visitation.objects.create(
            name=name,
            description=description,
            visitor=visitor,
            host=host,
            visitation_date=visitation_date,
            start_time=start_time,
            end_time=end_time,
            org_location=org_location,
            host_status=host_status,
            visitor_status=visitor_status,
            visitation_status=visitation_status,
            created_by=created_by,
            organization=org
        )
        send_visitation_email_on_update(visitation, request.user)

        serializer = self.serializer_class( visitation )
        return HTTP_200(serializer.data)


class VisitationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitationSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            requesting_member = fetch_data.get_member(request.user, org.uuid)
            user_role = requesting_member.role.name
            requesting_user = requesting_member
        except Member.DoesNotExist:
            return read_data.get_403_response()

        # if user_role not in ("admin", "hr", "member", "visitor"):
        #     return read_data.get_403_response()
        if fetch_data.is_admin_hr_member(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        serializer = self.serializer_class(visitation)
        return HTTP_200(serializer.data)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            requesting_member = fetch_data.get_member(request.user, org.uuid)
            user_role = requesting_member.role.name
            requesting_user = requesting_member
        except Member.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_admin_hr_member(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        if visitation.created_by.id == request.user.id or user_role == "admin" or requesting_member.is_front_desk is True:
            # Have permission to update visitation.
            pass
        else:
            return read_data.get_403_response()

        # completed or cancelled cannot editable.
        if visitation.visitation_status in ("completed", "cancelled"):
            return read_data.get_403_response(f"Can't edit {visitation.visitation_status} visitation")

        res_or_data = validate_visitation(request, user_role, requesting_member)
        if isinstance(res_or_data, Response):
            return res_or_data

        name = res_or_data.get("name", "")
        description = res_or_data.get("description", "")
        visitor = res_or_data.get("visitor")
        host = res_or_data.get("host")
        visitation_date = res_or_data.get("visitation_date")
        start_time = res_or_data.get("start_time")
        end_time = res_or_data.get("end_time")
        org_location = res_or_data.get("org_location")

        if host != visitation.host and host.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if visitor != visitation.visitor and visitor.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if org_location and org_location != visitation.org_location and org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org Location is inactive."})

        if org_location and org_location.enable_visitation is False:
            return HTTP_400({}, {"message": "Visitations are disabled for this Org Location."})

        is_send_email = False
        visitation_completed = False

        host_status = visitation.host_status
        visitor_status = visitation.visitor_status
        visitation_status = visitation.visitation_status

        if user_role == "visitor" and visitation.visitor.user == request.user and visitation.host != host:

            visitor_org = request.user.visitor.get().organization

            # If host_confirmation is required Host must accept. else right away shcedule.
            host_confirmation = visitor_org.settings.get("host_confirmation")

            if host_confirmation is True:
                host_status = "pending"
                visitor_status = "accepted"
                visitation_status = "created"

                # email to host
                user = host.user
                message = f"{visitation.visitor.user.email} send you a Visitation Request"
                is_send_email = True

            elif host_confirmation is False:
                host_status = "accepted"
                visitor_status = "accepted"
                visitation_status = "scheduled"

                visitation_completed = True
                is_send_email = True
                message = "Visitation is schedule"

        elif request.user == host.user and visitation.host != host: # create visitation for my self
            host_status = "accepted"
            visitor_status = "pending"
            visitation_status = "created"

            # email to visitor
            user = visitor.user
            message = f"{visitation.host.user.email} send you a Visitation Request"
            is_send_email = True

        elif user_role in ("admin", "hr") and visitation.host != host or visitation.visitor != visitor: # create visitation  for other member
            host_status = "pending"
            visitor_status = "pending"
            visitation_status = "created"

            # email to host
            user = host.user
            message = f"{request.user.email} send you a Visitation Request"
            is_send_email = True

        visitation.name = name
        visitation.description = description
        visitation.visitation_date = visitation_date
        visitation.start_time = start_time
        visitation.end_time = end_time
        visitation.org_location = org_location
        visitation.host_status = host_status
        visitation.visitor_status = visitor_status
        visitation.visitation_status = visitation_status

        is_changed = False

        if visitor != visitation.visitor:
            is_changed = True
            visitation.visitor = visitor

        if visitation.host != host:
            is_changed = True
            visitation.host = host

        visitation.save()

        if is_changed is True:
            # If visitor or host changed visitation restart.
            send_visitation_email_on_update(visitation, request.user)
        elif is_changed is False:
            # Just notify what is the change.
            notify_on_visitation_update(visitation, request.user)

        serializer = self.serializer_class( visitation )
        return HTTP_200(serializer.data)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get('organization-uuid')
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            requesting_member = fetch_data.get_member(request.user, org.uuid)
            user_role = requesting_member.role.name
            requesting_user = requesting_member
        except Member.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_admin_hr_member(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        if visitation.created_by.id == request.user.id or user_role == "admin":
            pass
        else:
            return read_data.get_403_response()

        if visitation.visitation_status in ("cancelled", "completed"):
            return read_data.get_403_response("visitation is already "+visitation.visitation_status)

        visitation.delete()
        return HTTP_200({"message": "Successfully deleted visitation"})

    def patch(self, request, *args, **kwargs):
        """ Cancell visitation
        """


        org_uuid = request.headers.get('organization-uuid')
        try:
            org = fetch_data.get_organization(request.user, org_uuid)
            requesting_member = fetch_data.get_member(request.user, org.uuid)
            user_role = requesting_member.role.name
            requesting_user = requesting_member
        except Member.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_admin_hr_member(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        if visitation.created_by.id == request.user.id or user_role == "admin":
            pass
        else:
            return read_data.get_403_response()

        if visitation.visitation_status in ("cancelled", "completed"):
            return read_data.get_403_response("visitation is already "+visitation.visitation_status)

        visitation.visitation_status = "cancelled"

        visitation.save()

        if user_role == "visitor" and request.user == visitation.visitor.user:
            # send email to host
            email_content = [
                {
                    "to": visitation.host.user,
                    "visitation": visitation,
                    "message": "Your Visitation is cancelled by visitor"
                },
            ]
        elif request.user == visitation.host.user:
            # send email to visitor
            email_content = [
                {
                    "to": visitation.visitor.user,
                    "visitation": visitation,
                    "message": "Your Visitation is cancelled by host"
                },
            ]
        elif visitation.created_by.id == request.user.id or user_role == "admin":
            # admin cancelling

            username = create_data.get_user_name(request.user)
            if visitation.host_status == "pending" and visitation.visitor_status == "pending":
                # Visitation in the member stage
                # So member only get cancel email

                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": f"Your Visitation is cancelled by {username}."
                    },
                ]
            else:
                # Visitation request in visitation stage. host and visitor will get the email
                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": f"Your Visitation is cancelled by {username}."
                    },
                    {
                        "to": visitation.visitor.user,
                        "visitation": visitation,
                        "message": f"Your Visitation is cancelled by {username}."
                    },
                ]
        else:
            logger.error("No condition are met for send email edit visitation")
            email_content = []

        send_bulk_visitation_update_email(email_content)

        serializer = self.serializer_class(visitation)
        return HTTP_200(serializer.data)




# =============== for visitor ===============
class VisitorVisitationAPI(views.APIView):
    """Get own visitations, create visitation
    """

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitationSerializer

    def get(self, request, *args, **kwargs):
        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)
            user_role = requesting_visitor.role.name
            requesting_user = requesting_visitor
        except Visitor.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_visitor(requesting_user) is False:
            return read_data.get_403_response()

        visitations = Visitation.objects.filter(visitor__organization__id=org.id)
        if user_role == "visitor":
            visitations = visitations.filter(visitor=requesting_visitor)
        # elif user_role in ("admin", "hr", "member"):
        #     visitations = visitations.filter(host=requesting_member)

        visitations = search_visitations(visitations, request.GET.get("search"))
        visitations = filter_visitations(visitations, request)

        page_obj, num_pages, page = pagination(visitations, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)
        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        """ Visitation Flow
        =======================
        - create visitation for my-self (minimum role = member)
        - create visitation by admin or hr
        - create visitation as visitor
        """
        # User is must be a member or a visitor
        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)
            user_role = requesting_visitor.role.name
            requesting_user = requesting_visitor
        except Visitor.DoesNotExist:
            return read_data.get_403_response()

        # if user_role not in ("admin", "hr", "member", "visitor"):
        #     return read_data.get_403_response()

        if fetch_data.is_visitor(requesting_user) is False:
            return read_data.get_403_response()
        print("###########################")
        res_or_data = validate_visitation(request, user_role, requesting_visitor)
        if isinstance(res_or_data, Response):
            return res_or_data

        name = res_or_data.get("name", "")
        description = res_or_data.get("description", "")
        visitor = res_or_data.get("visitor")
        host = res_or_data.get("host")
        visitation_date = res_or_data.get("visitation_date")
        start_time = res_or_data.get("start_time")
        end_time = res_or_data.get("end_time")
        org_location = res_or_data.get("org_location")

        created_by = request.user # logged in user

        if host.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if visitor.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if org_location and org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org Location is inactive."})
        
        if org_location and org_location.enable_visitation is False:
            return HTTP_400({}, {"message": "Visitations are disabled for this Org Location."})


        # visitor create visitation and host conf in org settings is False
        visitation_complted = False

        if user_role == "visitor":
            visitor_org = request.user.visitor.get().organization
            host_confirmation = visitor_org.settings.get("host_confirmation")

            print(host_confirmation, "host_confirmation")

            if host_confirmation is True:
                host_status = "pending"
                visitor_status = "accepted"
                visitation_status = "created"

                # email to host
                user = host.user
                user_name = create_data.get_user_name(visitor.user)
                message = f"{user_name} sent you a Visitation Request"

            elif host_confirmation is False:
                host_status = "accepted"
                visitor_status = "accepted"
                visitation_status = "scheduled"

                visitation_complted = True
                message = "Visitation is scheduled"

        elif created_by == host.user: # create visitation for my self
            host_status = "accepted"
            visitor_status = "pending"
            visitation_status = "created"

            # email to visitor
            user = visitor.user
            user_name = create_data.get_user_name(host.user)
            message = f"{user_name} sent you a Visitation Request"

        elif user_role in ("admin", "hr"): # create visitation  for other member

            host_status = "pending"
            visitor_status = "pending"
            visitation_status = "created"

            # email to host
            user = host.user
            user_name = create_data.get_user_name(request.user)
            message = f"{user_name} sent you a Visitation Request"

        visitation = Visitation.objects.create(
            name=name,
            description=description,
            visitor=visitor,
            host=host,
            visitation_date=visitation_date,
            start_time=start_time,
            end_time=end_time,
            org_location=org_location,
            host_status=host_status,
            visitor_status=visitor_status,
            visitation_status=visitation_status,
            created_by=created_by,
            organization=org
        )
        send_visitation_email_on_update(visitation, request.user)

        # if visitation_complted is True:
        #     email_content = [
        #         {
        #             "to": visitation.host.user,
        #             "visitation": visitation,
        #             "message": message
        #         },
        #         {
        #             "to": visitation.visitor.user,
        #             "visitation": visitation,
        #             "message": message
        #         },
        #     ]
        #     send_bulk_visitation_update_email(email_content)
        # else:
        #     email_content = {
        #         "to": user,
        #         "visitation": visitation,
        #         "message": message
        #     }
        #     send_visitation_request_mail(email_content)
        serializer = self.serializer_class( visitation )
        return HTTP_200(serializer.data)


class AllVisitorVisitationAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitationSerializer

    def get(self, request, *args, **kwargs):
        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)
            user_role = requesting_visitor.role.name
            requesting_user = requesting_visitor
        except Visitor.DoesNotExist:
            return read_data.get_403_response()

        # if user_role not in ("admin", "hr", "member", "visitor"):
        #     return read_data.get_403_response()
        if fetch_data.is_visitor(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        serializer = self.serializer_class(visitation)
        return HTTP_200(serializer.data)

    def put(self, request, *args, **kwargs):

        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)
            user_role = requesting_visitor.role.name
            requesting_user = requesting_visitor
        except Visitor.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_visitor(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        if visitation.created_by.id == request.user.id or user_role == "admin":
            pass
        else:
            return read_data.get_403_response()

        if visitation.visitation_status in ("completed", "cancelled"):
            return read_data.get_403_response(f"Can't edit {visitation.visitation_status} visitation")

        res_or_data = validate_visitation(request, user_role, requesting_visitor)
        if isinstance(res_or_data, Response):
            return res_or_data

        name = res_or_data.get("name", "")
        description = res_or_data.get("description", "")
        visitor = res_or_data.get("visitor")
        host = res_or_data.get("host")
        visitation_date = res_or_data.get("visitation_date")
        start_time = res_or_data.get("start_time")
        end_time = res_or_data.get("end_time")
        org_location = res_or_data.get("org_location")

        if host != visitation.host and host.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if visitor != visitation.visitor and visitor.status == "inactive":
            return HTTP_400({}, {"message": "Host is inactive."})

        if org_location and org_location != visitation.org_location and org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org Location is inactive."})

        if org_location and org_location.enable_visitation is False:
            return HTTP_400({}, {"message": "Visitations are disabled for this Org Location."})

        is_send_email = False
        visitation_complted = False

        host_status = visitation.host_status
        visitor_status = visitation.visitor_status
        visitation_status = visitation.visitation_status

        if user_role == "visitor" and visitation.visitor.user == request.user and visitation.host != host:

            visitor_org = request.user.visitor.get().organization
            host_confirmation = visitor_org.settings.get("host_confirmation")

            if host_confirmation is True:
                host_status = "pending"
                visitor_status = "accepted"
                visitation_status = "created"

                # email to host
                user = host.user
                message = f"{visitation.visitor.user.email} send you a Visitation Request"
                is_send_email = True

            elif host_confirmation is False:
                host_status = "accepted"
                visitor_status = "accepted"
                visitation_status = "scheduled"

                visitation_complted = True
                is_send_email = True
                message = "Visitation is schedule"

        elif request.user == host.user and visitation.host != host: # create visitation for my self
            host_status = "accepted"
            visitor_status = "pending"
            visitation_status = "created"

            # email to visitor
            user = visitor.user
            message = f"{visitation.host.user.email} send you a Visitation Request"
            is_send_email = True

        elif user_role in ("admin", "hr") and visitation.host != host or visitation.visitor != visitor: # create visitation  for other member
            host_status = "pending"
            visitor_status = "pending"
            visitation_status = "created"

            # email to host
            user = host.user
            message = f"{request.user.email} send you a Visitation Request"
            is_send_email = True

        visitation.name = name
        visitation.description = description
        visitation.visitation_date = visitation_date
        visitation.start_time = start_time
        visitation.end_time = end_time
        visitation.org_location = org_location
        visitation.host_status = host_status
        visitation.visitor_status = visitor_status
        visitation.visitation_status = visitation_status

        is_changed = False

        if visitor != visitation.visitor:
            is_changed = True
            visitation.visitor = visitor

        if visitation.host != host:
            is_changed = True
            visitation.host = host

        visitation.save()

        if is_changed is True:
            send_visitation_email_on_update(visitation, request.user)
        elif is_changed is False:
            notify_on_visitation_update(visitation, request.user)


        # if visitation_complted is True and is_send_email:
        #     email_content = [
        #         {
        #             "to": visitation.host.user,
        #             "visitation": visitation,
        #             "message": message
        #         },
        #         {
        #             "to": visitation.visitor.user,
        #             "visitation": visitation,
        #             "message": message
        #         },
        #     ]
        #     send_bulk_visitation_update_email(email_content)

        # elif is_send_email:
        #     # send email according to host or visitor change
        #     email_content = {
        #         "to": user,
        #         "visitation": visitation,
        #         "message": message
        #     }
        #     send_visitation_request_mail(email_content)
        # elif is_send_email is False:
        #     send_visitation_email_on_update(visitation, request.user)

        serializer = self.serializer_class( visitation )
        return HTTP_200(serializer.data)

    def delete(self, request, *args, **kwargs):
        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)
            user_role = requesting_visitor.role.name
            requesting_user = requesting_visitor
        except Visitor.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_visitor(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        if visitation.created_by.id == request.user.id or user_role == "admin":
            pass
        else:
            return read_data.get_403_response()

        if visitation.visitation_status in ("cancelled", "completed"):
            return read_data.get_403_response("visitation is already "+visitation.visitation_status)

        visitation.delete()
        return HTTP_200({"message": "Successfully deleted visitation"})

    def patch(self, request, *args, **kwargs):

        try:
            org_uuid = request.headers.get('organization-uuid')
            org = fetch_data.get_organization_as_visitor(request.user, org_uuid)
            requesting_visitor = fetch_data.get_visitor(request.user, org.uuid)
            user_role = requesting_visitor.role.name
            requesting_user = requesting_visitor
        except Visitor.DoesNotExist:
            return read_data.get_403_response()

        if fetch_data.is_visitor(requesting_user) is False:
            return read_data.get_403_response()

        uuid = kwargs.get("uuid")
        try:
            visitation = Visitation.objects.get(uuid=uuid)
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")

        if visitation.created_by.id == request.user.id or user_role == "admin":
            pass
        else:
            return read_data.get_403_response()

        if visitation.visitation_status in ("cancelled", "completed"):
            return read_data.get_403_response("visitaiton is alredy "+visitation.visitation_status)

        visitation.visitation_status = "cancelled"

        visitation.save()

        print("++++++++++++++++++++"*10)
        if user_role == "visitor" and request.user == visitation.visitor.user:
            print("visitor######")
            """to host"""
            email_content = [
                {
                    "to": visitation.host.user,
                    "visitation": visitation,
                    "message": "Your Visitation is cancelled by visitor"
                },
            ]
        elif request.user == visitation.host.user:
            print("host######")
            """to visitor"""
            email_content = [
                {
                    "to": visitation.visitor.user,
                    "visitation": visitation,
                    "message": "Your Visitation is cancelled by host"
                },
            ]
        elif visitation.created_by.id == request.user.id or user_role == "admin":
            print("admin######")

            username = create_data.get_user_name(request.user)
            if visitation.host_status == "pending" and visitation.visitor_status == "pending":
                """host"""
                
                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": f"Your Visitation is cancelled by {username}."
                    },
                ]
            else:
                """both"""
                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": f"Your Visitation is cancelled by {username}."
                    },
                    {
                        "to": visitation.visitor.user,
                        "visitation": visitation,
                        "message": f"Your Visitation is cancelled by {username}."
                    },
                ]
        else:
            logger.error("No condition are met for send email edit visitation")
            email_content = []

        print(email_content)
        print("++++++++++++++++++++"*10)

        send_bulk_visitation_update_email(email_content)

        serializer = self.serializer_class(visitation)
        return HTTP_200(serializer.data)
