from django.db import IntegrityError
from export.utils import create_export_request
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from django.db.models import Q
from api import permissions
from organization.models import Department, Designation, OrgLocation, Role
from organization.utils import get_cost_center, get_designation, get_member_role
from utils.shift import assign_applicable_shift
from utils.utils import base64_to_contentfile, is_allowed_to_add_members, send_limit_exceeded_notification
from account.models import User
from member.models import Member
from member import serializers, search
from roster.utils import get_roster
from utils.response import HTTP_200, HTTP_400
from utils import read_data, fetch_data, create_data, email_funcs
from django.db.models.functions import Lower
from kiosk.models import Kiosk

import logging

from visitor.models import Visitor


logger = logging.getLogger(__name__)


class MembersUploadCSVAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(member) is False:
            return read_data.get_403_response()

        schema = [
            {
                "email": "user1@gmail.com",
                "phone_number": "9876543210",
                "first_name": "user1",
                "last_name": "user",
                "designation": "designation1",
                "department": "department1",
                "org_location": "org_location_1",
                "employee_id": "01",
                "manager": "admin@gmail.com",
                "role": "admin",
                "status": "active",
            },
            {
                "email": "user2@gmail.com",
                "phone_number": "9876543211",
                "first_name": "user2",
                "last_name": "user",
                "designation": "designation2",
                "department": "department2",
                "org_location": "org_location_2",
                "employee_id": "02",
                "manager": "manager@gmail.com",
                "role": "member",
                "status": "inactive",
            },
        ]
        # return JsonResponse(schema,safe=False, status=status.HTTP_200_OK)
        return HTTP_200(schema)

    def post(self, request, *args, **kwargs):
        print("-----------"*10)
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        requesting_member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin(requesting_member) is False:
            return read_data.get_403_response()

        csv_file = request.data.get("csv_file")
        df = create_data.create_pandas_dataframe(csv_file)

        if df is None:
            return HTTP_400({}, {})

        failed_members = []

        # member_role = fetch_data.get_member_role()

        created_members_count = 0
        update_members_count = 0
        failed_rows = []
        row_count = 1

        all_users = User.objects.all()
        all_visitor = Visitor.objects.filter(organization=org)
        all_members = Member.objects.filter(organization=org)
        all_department = Department.objects.filter(organization=org)
        all_designation = Designation.objects.filter(organization=org)
        all_org_location = OrgLocation.objects.filter(organization=org)
        all_roles = Role.objects.filter(name__in=["admin", "hr", "member"])
        mobile_kiosk, _ = Kiosk.objects.get_or_create(
            kiosk_name="Mobile Kiosk", organization=org
        )

        for row in df.values:
            row_count += 1
            row_length = len(row)
            is_created = False
            print(row_length, "----------row_length-----------")

            is_update = 0
            if row_length == 12:
                is_update = 1

            email = str(row[0 + is_update]).lower()
            phone = (str(row[1 + is_update])).split(".", maxsplit=1)[0]
            first_name = row[2 + is_update]
            last_name = row[3 + is_update]
            designation = str(row[4 + is_update])
            department = str(row[5 + is_update])
            org_location = str(row[6 + is_update])
            employee_id = row[7 + is_update]
            manager_email = row[8 + is_update]
            role = row[9 + is_update]
            member_status = row[10 + is_update]

    # {
    #             "email": "user2@gmail.com",
    #             "phone_number": "9876543211",
    #             "first_name": "user2",
    #             "last_name": "user",
    #             "designation": "designation2",
    #             "department": "department2",
    #             "org_location": "org_location_2",
    #             "employee_id": "02",
    #             "manager": "manager@gmail.com",
    #             "role": "member",
    #             "status": "inactive",
    #         },

            try:
                if member_status not in ("active", "inactive"):
                    raise ValidationError("Status must be active/inactive.")

                if row_length not in (11 , 12):
                    raise ValidationError("Row length must be 11 or 12.")

                if row_length == 11:  # Import
                    if (not email and not phone) or (email == "NA" and phone == "NA"):
                        raise ValidationError("email or phone number is required")
                    if not first_name or first_name in ("NA",):
                        raise ValidationError("First Name is required")

                    # check user exist with email or phone number
                    users = all_users.filter(Q(email=email) | Q(phone=phone))

                    if users.exists():
                        user_with_email = users.filter(email=email)
                        user_with_phone = users.filter(phone=phone)

                        if user_with_email.exists() is True:
                            user = user_with_email.get()
                        elif user_with_phone.exists() is True:
                            user = user_with_phone.get()

                        if all_visitor.filter(user=user).exists() is True:
                            raise ValidationError("User is already a visitor.")

                    else:
                        # create user, set password and send activation email
                        create_user_data = {"first_name": first_name}

                        have_email = False
                        if email and email != "NA":
                            have_email = True
                            create_user_data["email"] = email
                        elif phone and phone != "NA":
                            create_user_data["phone"] = phone

                        user = User.objects.create(**create_user_data)
                        user.save()

                        if have_email is True:
                            email_funcs.send_activation_mail(user)

                    # ============= validate user =============

                    user = self.validate_user_data(
                        user=user,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone=phone,
                        all_users=all_users,
                    )

                    print("user === ",user)

                    # Get or create the Member
                    try:
                        member = all_members.get(user=user)
                    except Member.DoesNotExist:
                        if is_allowed_to_add_members(org) is False:
                            send_limit_exceeded_notification(org, request.user)
                            return Response(
                                {"message": "Organization member limit reached. Please contact Empfly support."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        member_role = all_roles.get(name=role)
                        member = Member.objects.create(
                            organization=org, user=user, role=member_role, status=member_status
                        )
                        # email_funcs.send_activation_mail(user)
                        member.authorized_kiosks.add(mobile_kiosk.id)
                        member.save()
                        created_members_count += 1
                        is_created = True

                if row_length == 12:  # Update
                    if not row[0]:
                        raise ValidationError("UUID is required")

                    member = all_members.get(uuid=row[0])
                    user = member.user

                    # ============= validate user =============
                    user = self.validate_user_data(
                        user=user,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone=phone,
                        all_users=all_users,
                    )

                    print(role, "role+++++++++++++++++")

                    if role and member != requesting_member:
                        if role not in ("admin", "hr", "member"):
                            raise ValidationError("Role must be in Admin/Hr/Member.")

                        try:
                            member_role = all_roles.get(name=role.lower())
                            if member_role != member.role:
                                member.role = member_role
                        except Role.DoesNotExist:
                            pass

                print(manager_email, "manager_email+++++++++++++++++")
                if department and department not in ("", "NA", None):
                    department_obj, created = all_department.get_or_create(
                        name=department, organization=org
                    )
                    if created:
                        member.department = department_obj
                    elif member.department != department_obj:
                        member.department = department_obj
                else:
                    member.department = None

                if designation and designation not in ("", "NA", None):
                    designation_obj, created = all_designation.get_or_create(
                        name=designation, organization=org
                    )
                    if created:
                        member.designation = designation_obj
                    elif member.designation != designation_obj:
                        member.designation = designation_obj
                else:
                    member.designation = None

                if org_location and org_location not in ("", "NA", None):
                    org_location_obj, created = all_org_location.get_or_create(
                        name=org_location, organization=org
                    )
                    if created:
                        member.org_location = org_location_obj
                    elif member.org_location != org_location_obj:
                        member.org_location = org_location_obj
                else:
                    member.org_location = None

                if employee_id in ("", "NA", None):
                    member.employee_id = None
                elif (
                    member.employee_id != employee_id
                    and all_members.filter(employee_id=employee_id).exists() is False
                ):
                    member.employee_id = employee_id

                if manager_email in ("", "NA", None):
                    member.manager = None
                elif manager_email:
                    try:
                        manager = all_members.exclude(uuid=member.uuid).get(
                            user__email=manager_email.lower()
                        )

                        if member not in (manager, manager.manager):
                            member.manager = manager
                    except Member.DoesNotExist:
                        pass

                if member.status == "inactive" and member_status == "active" and is_allowed_to_add_members(org) is False:
                    send_limit_exceeded_notification(org, request.user)
                    return Response(
                        {"message": "Organization member limit reached. Please contact Empfly support."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                member.status = member_status

                member.save()

                print("=================== is_created ===========", is_created)
                if not is_created:
                    update_members_count += 1

            except Exception as err:
                failed_rows.append(row_count)
                try:
                    failed_members.append(
                        {
                            "email": row[0],
                            "reason": str(err.__class__.__name__),
                            "detailed_reason": str(err),
                        }
                    )
                except Exception:
                    pass
                logger.error(err)
                logger.exception(
                    f"Add exception for {err.__class__.__name__} in MembersUploadCSVAPI"
                )

        return Response(
            {
                "failed_members": failed_members,
                "created_count": created_members_count,
                "failed_rows": failed_rows,
                "updated_count": update_members_count,
            },
            status=status.HTTP_201_CREATED,
        )

    def validate_user_data(
        self,
        user: User,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        all_users: User,
    ):

        user.first_name = first_name

        if last_name and last_name != "NA":
            user.last_name = last_name

        if email and email != "NA" and all_users.filter(email=email).exists() is False:
            user.email = email

        if phone and phone != "NA" and all_users.filter(phone=phone).exists() is False:
            user.phone = phone

        user.save()
        return user
