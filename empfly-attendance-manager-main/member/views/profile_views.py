from django.db.models import Q
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import login, logout, authenticate
from django.conf import settings
from django.core.files.base import ContentFile

from django.http import JsonResponse
from django.middleware.csrf import get_token

from rest_framework import generics, serializers, views, status
from rest_framework.response import Response

from utils.shift import curr_shift_schedule_log
from utils.date_time import curr_date_time_with_tz, curr_dt_with_org_tz


from api import permissions

from organization.utils import get_city

from account.models import User
from account import serializers
from member.models import Member, Profile
from member.serializers import ProfileSerializer
from organization.utils import get_member_role
from utils import fetch_data, read_data
from utils.utils import base64_to_contentfile





class MembersProfileAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = ProfileSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        # uuid = request.GET.get("uuid")
        # if uuid:
        #     member = fetch_data.get_member_by_uuid(org.uuid, uuid)
        #     if member is None:
        #         return read_data.get_404_response("Member")

        #     if requesting_member != member and fetch_data.is_admin(requesting_member) is False:
        #         return read_data.get_403_response()
        # else:
        member = requesting_member

        today_dt = curr_dt_with_org_tz()
        today_log = curr_shift_schedule_log(member, today_dt, org)[0]

        serializer = self.serializer_class(member.profile)

        data = serializer.data
        if today_log:
            data["today_shift"] = today_log.shift.name
        return Response(data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        # uuid = self.kwargs.get("uuid")
        # member = fetch_data.get_member_by_uuid(org.uuid, uuid)
        # if member is None:
        #     return read_data.get_404_response("Member")

        # if requesting_member != member and fetch_data.is_admin(requesting_member) is False:
        #     return read_data.get_403_response()

        member = requesting_member

        profile = member.profile
        first_name = request.data.get("first_name", member.user.first_name)
        last_name = request.data.get("last_name", member.user.last_name)
        photo = request.data.get("photo")

        gender = request.data.get("gender", profile.gender)
        address = request.data.get("address", profile.address)
        dob = request.data.get("dob", profile.dob)
        government_id = request.data.get("government_id", profile.government_id)
        marital_status = request.data.get("marital_status", profile.marital_status)
        theme = request.data.get("theme", profile.settings.get("theme"))
        vehicle_number = request.data.get("vehicle_number", member.vehicle_number)

        # pin_code = request.data.get("pincode", profile.pin_code)
        # government_id_type = request.data.get("government_id_type", profile.government_id_type)

        if not gender:
            gender = None
        elif gender not in [x[0] for x in Profile.GENDER_CHOICES]:
            return Response({"message": "Enter valid gender"}, status=status.HTTP_400_BAD_REQUEST)

        if theme and theme not in [x[0] for x in Profile.THEME_CHOICES]:
            return Response({"message": "Enter valid theme"}, status=status.HTTP_400_BAD_REQUEST)

        if not dob:
            dob = None

        if marital_status and marital_status not in [x[0] for x in Profile.MARITAL_STATUS_CHOICES]:
            return Response(
                {"message": "Enter valid marital status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.user.first_name = first_name
        member.user.last_name = last_name
        member.vehicle_number = vehicle_number
        profile.gender = gender
        profile.address = address
        profile.marital_status = marital_status
        profile.dob = dob
        profile.government_id = government_id

        if theme:
            profile.settings["theme"] = theme

        if photo:
            content = base64_to_contentfile(photo)
            if isinstance(content, ContentFile):
                member.photo = content
            else:
                return content  # response

        member.user.save()
        member.save()
        profile.save()

        serializer = self.serializer_class(member.profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
