import logging
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from attendance.exceptions import CaptureFRImagError
from member.filters import filter_member_images
from member.search import search_member_images
import organization

from rest_framework import status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from env import scan_fr_in_instance
from attendance.attendance_utils import (
    face_rec,
    face_rec_for_fr,
)
from member.search import search_members

from api import permissions
from member import serializers
from member.models import Member, MemberImage
from utils import fetch_data, read_data
# import face_recognition
from member.constants import MEMBER_MAX_IMAGE_COUNT
import base64
import datetime as dt
# from utils import face_rec
from utils.response import HTTP_200, HTTP_400

from utils.utils import base64_to_contentfile, is_fr_image_limit_reached, pagination
from utils.face_rec import convert_encoding_to_json, get_image_encoding
from export import utils as export_utils
from export.utils import create_export_request


logger = logging.getLogger(__name__)

logging.basicConfig(
    filename="logs/fr_images.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)

class MembersAllImagesAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberImageSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org.uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(requesting_member) is False:
            return read_data.get_403_response()

        member_images = requesting_member.member_images.all()
        # member_images = MemberImage.objects.filter(member__organization=org)
        member_images = search_member_images(member_images, request.GET.get("search", None))

        if bool(request.GET.get("export_csv")) is True:
            if not member_images.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            members_ids = export_utils.get_uuid_from_qs_for_fr_image(member_images)
            export_request = create_export_request(requesting_member, "fr_image", members_ids)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})

        page_obj, num_pages, page = pagination(member_images, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        """ MemberImage is used for face rec. If member try to upload image >= 2
            We will match the prev uploaded image with current image.
            If they capture multiple member images for a same member account it will cause
            issue in check and check out face rec.
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org.uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        if is_fr_image_limit_reached(member):
            return Response(
                {
                    "message": f"Maximum of {MEMBER_MAX_IMAGE_COUNT} images can be uploaded for Face Recognition. If required, please delete existing FR image and upload new images."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        image = request.data.get("image")
        if image is None:
            return Response(
                {"message": "Image required"}, status=status.HTTP_400_BAD_REQUEST
            )

        base_64_img = image
        image_or_res = base64_to_contentfile(image)
        print(image_or_res, "############################")

        if isinstance(image_or_res, Response):
            RESPONSE = image_or_res
            return RESPONSE

        image = image_or_res

        encoding = get_image_encoding(image)
        if len(encoding) == 0:
            return Response(
                {"message": "No face detected. Try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member_images = member.member_images.all()

        if member_images.exists():
            print("######## Image ########sss")
            try:
                user, image = face_rec(member, base_64_img, request.user)
            except ValidationError as err:
                return HTTP_400({}, {"message": err.message})
        
        logging.info(f"scan_fr_in_instance; {scan_fr_in_instance}")
        # Match all fr image from instance
        if scan_fr_in_instance is True:
            try:
                matched_member, all_matched_member_id = read_data.match_img_with_all_FR(base_64_img)
            except CaptureFRImagError as err:
                logging.info("Error occurred")
                logging.info(err.message)
                return HTTP_400({}, {"message": err.message})
            except Exception as err:
                logging.info(err)
                return HTTP_400({}, {"message": "Unknown error occurred. Error CFR2210."})

            logging.info("")
            logging.info(f"matched_member: {matched_member}")
            logging.info(f"all_matched_member_id: {all_matched_member_id}")

            if matched_member is None and len(all_matched_member_id) >= 1:
                return HTTP_400({}, {"message": "Unable to complete identification. Error CFR7412."})

            logging.info(f"matched_member: {matched_member}")
            logging.info(f"member: {member}")

            if matched_member and matched_member != member:
                return HTTP_400({}, {"message": "Unable to complete identification. Error CFR6485."})

        encoding = convert_encoding_to_json(encoding)
        member_image = MemberImage.objects.create(
            member=member, image=image, encoding=encoding, organization=org
        )

        serializer = self.serializer_class(member_image)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MemberImageAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberImageSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user,org_uuid)
        org = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        try:
            member_image = MemberImage.objects.get(uuid=uuid, member=member)
        except (MemberImage.DoesNotExist, ValidationError) as e:
            logger.error(e)
            return read_data.get_404_response("Member Image")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in MemberImageAPI"
            )
            return read_data.get_404_response("Member Image")

        serializer = self.serializer_class(member_image)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org.uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_hr_member(requesting_member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        try:
            member_image = MemberImage.objects.get(uuid=uuid)
        except (MemberImage.DoesNotExist, ValidationError) as e:
            logger.error(e)
            return read_data.get_404_response("Member Image")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in MemberImageAPI"
            )
            return read_data.get_404_response("Member Image")

        member_image.delete()
        return read_data.get_200_delete_response("Member Image")


    def post(self, request, *args, **kwargs):
        """ MemberImage is used for face rec. If member try to upload image >= 2
            We will match the prev uploaded image with current image.
            If they capture multiple member images for a same member account it will cause
            issue in check and check out face rec.

            Admin and hr can upload these images.
        """

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org.uuid = org.uuid
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        image = request.data.get("image")
        if image is None:
            return Response(
                {"message": "Image required"}, status=status.HTTP_400_BAD_REQUEST
            )

        selected_member = fetch_data.get_member_by_uuid(org.uuid, kwargs.get("uuid"))
        if not selected_member:
            return Response(
                {"message": "Member not found."}, status=status.HTTP_400_BAD_REQUEST
            )
        
        if is_fr_image_limit_reached(selected_member):
            return Response(
                {
                    "message": f"Maximum of {MEMBER_MAX_IMAGE_COUNT} images can be uploaded for Face Recognition. If required, please delete existing FR image and upload new images."
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        if member.role.name == "hr" and selected_member.role.name in ("admin", "hr"):
            return read_data.get_403_response()

        base_64_img = image
        image_or_res = base64_to_contentfile(image)
        print(image_or_res, "############################")

        if isinstance(image_or_res, Response):
            RESPONSE = image_or_res
            return RESPONSE

        image = image_or_res

        encoding = get_image_encoding(image)
        if len(encoding) == 0:
            return Response(
                {"message": "No face detected. Try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member_images = selected_member.member_images.all()

        if member_images.exists():
            print("######## Image ########sss")
            try:
                user, image = face_rec_for_fr(selected_member, base_64_img, request.user)
            except ValidationError as err:
                return HTTP_400({}, {"message": err.message})

        logging.info(f"scan_fr_in_instance; {scan_fr_in_instance}")

        # Match all fr image from instance
        if scan_fr_in_instance is True:
            try:
                matched_member, all_matched_member_id = read_data.match_img_with_all_FR(base_64_img)
            except CaptureFRImagError as err:
                logging.info("Error occurred")
                logging.info(err)
                return HTTP_400({}, {"message": err.message})
            except Exception as err:
                logging.info(err)
                return HTTP_400({}, {"message": "Unknown error occurred. Error CFR0230618."})

            logging.info("")
            logging.info(f"matched_member: {matched_member}")
            logging.info(f"all_matched_member_id: {all_matched_member_id}")

            if matched_member is None and len(all_matched_member_id) >= 1:
                return HTTP_400({}, {"message": "Unable to complete identification. Error CFR8160."})

            logging.info(f"matched_member: {matched_member}")
            logging.info(f"selected_member: {selected_member}")

            if matched_member and matched_member != selected_member:
                return HTTP_400({}, {"message": "Unable to complete identification. Error CFR3415"})

        encoding = convert_encoding_to_json(encoding)
        member_image = MemberImage.objects.create(
            member=selected_member, image=image, encoding=encoding, organization=org
        )

        serializer = self.serializer_class(member_image)
        return Response(serializer.data, status=status.HTTP_201_CREATED)



class GetMemberForFrAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberDataSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user,org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        org_members = org.members.all().select_related("user")

        if member.role.name == "hr":
            org_members = org_members.filter(role__name="member")

        search_query = request.GET.get("search")
        org_members = search_members(org_members, search_query)

        # serializer = self.serializer_class(org_members, many=True)
        # return Response(serializer.data, status=status.HTTP_200_OK)

        page_obj, num_pages, page = pagination(org_members, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )


class AllMemberImages(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = serializers.MemberImageSerializer

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org.uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        member_images = MemberImage.objects.filter(organization=org)

        members_status = request.GET.get("status", "active")
        if members_status in ("active", "inactive"):
            member_images = member_images.filter(member__status=members_status)

        member_images = search_member_images(member_images, request.GET.get("search", None))
        member_images = filter_member_images(member_images, request)


        if bool(request.GET.get("export_csv")) is True:
            if not member_images.exists():
                return HTTP_400({}, {"message": "No data found for export."})

            members_ids = export_utils.get_uuid_from_qs_for_fr_image(member_images)
            export_request = create_export_request(requesting_member, "fr_image", members_ids)
            if export_request is None:
                return HTTP_400({}, {"export_request_uuid": None})
            return HTTP_200({"export_request_uuid": export_request.uuid})


        page_obj, num_pages, page = pagination(member_images, request)
        serializer = self.serializer_class(page_obj.object_list, many=True)

        return Response(
            {
                "data": serializer.data,
                "pagination": {"total_pages": num_pages, "page": page},
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        org.uuid = org.uuid
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(requesting_member) is False:
            return read_data.get_403_response()

        uuid = self.kwargs.get("uuid")
        try:
            member_image = MemberImage.objects.get(uuid=uuid)
        except (MemberImage.DoesNotExist, ValidationError) as e:
            logger.error(e)
            return read_data.get_404_response("Member Image")
        except Exception as e:
            logger.error(e)
            logger.exception(
                f"Add exception for {e.__class__.__name__} in MemberImageAPI"
            )
            return read_data.get_404_response("Member Image")

        member_image.delete()
        return read_data.get_200_delete_response("Member Image")