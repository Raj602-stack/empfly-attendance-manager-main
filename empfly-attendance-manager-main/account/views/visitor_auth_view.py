from venv import create
from account.models import OTP
from utils.email_funcs import send_otp_to_email
from utils.response import HTTP_400, HTTP_200
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import fetch_data, read_data
from visitor.models import Visitation, Visitor
from visitor.serializers import VisitorSerializer
from utils.utils import generateOTP, is_user_email_exists
from organization.models import Organization, OrgLocation
from datetime import datetime
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth import login, logout
import datetime as dt
from django.core.exceptions import ValidationError
import logging
logger = logging.getLogger(__name__)



class VisitorOtpAPI(views.APIView):

    serializer_class = VisitorSerializer
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """ Send email to email provided by visitor for visitor login page.
        """

        email = request.data.get("email", "").strip()
        email = email.lower()

        if not email:
            return HTTP_400({}, {"message": "Email is required"})

        generated_otp = generateOTP()
        otp = OTP.objects.create(
            email=email,
            otp=generated_otp,
        )

        is_sended = send_otp_to_email(generated_otp, email)

        return HTTP_200({
            "uuid": otp.uuid,
            "is_otp_sended": is_sended
        })

class VisitorVerifyOtpAPI(views.APIView):

    serializer_class = VisitorSerializer
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """ Verify the entered otp.
        """

        uuid = request.data.get("uuid")
        user_otp = str(request.data.get("otp"))
        # TODO change org_uuid to organization_location
        org_location = request.data.get("org_uuid")

        if not uuid:
            return HTTP_400({}, {"message": "uuid is required"})

        if not user_otp:
            return HTTP_400({}, {"message": "OTP is required"})

        if not org_location:
            return HTTP_400({}, {"message": "Organization Location is required"})

        if len(user_otp) != 4:
            return HTTP_400({}, {"message": "Enter a valid OTP"})

        try:
            otp = OTP.objects.get(uuid=uuid)
        except OTP.DoesNotExist:
            return HTTP_400({}, {"message": "Please generate OTP"})

        try:
            org_location = OrgLocation.objects.get(uuid=org_location)
            org = org_location.organization
        except (OrgLocation.DoesNotExist, ValidationError):
            return HTTP_400({}, {"message": "Organization Location does not exist."})

        if org_location.status == "inactive":
            return HTTP_400({}, {"message": "Org location is inactive."})

        created_at = otp.created_at
        otp_expiry = org.settings.get("otp_expiry")

        if not otp_expiry:
            return HTTP_400({}, {"message": "No expiry date"})
        otp_expiry = int(otp_expiry)

        current_time = timezone.now()
        exp_time = created_at + timedelta(minutes=otp_expiry)

        if current_time > exp_time:
            otp.delete()
            return HTTP_400({"message": "OTP is expired. Please try again."})

        if otp.otp != user_otp:
            return HTTP_400({}, {"message": "Incorrect OTP. Please try again"})

        email = otp.email
        print(email, "############## Email ###############")
        user = is_user_email_exists(email)

        print(user, "++++++++++++++++ user +++++++++++++++++++")

        if user is not None:
            visitor = Visitor.objects.filter(
                user=user,
                organization=org
            )

        if user is None or visitor.exists() is False:
            otp.delete()
            return HTTP_200({
                "email": email,
                "account_exists" : False,
            })

        user = visitor.first().user
        user.is_active = True
        user.save()

        # visitations = Visitation.objects.filter(visitation_date=str(dt.date.today()), visitor=visitor.first())

        # if not visitations.exists():
        #     otp.delete()
        #     return HTTP_400({}, {"message": "Visitation is not scheduled for today. Please check Visitation date."})

        login(request, user)
        otp.delete()

        return HTTP_200({
            "email": email,
            "account_exists" : True,
        })



class VisitorLogoutAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def post(self, request, *args, **kwargs):

        logout(request)

        return HTTP_200({})
