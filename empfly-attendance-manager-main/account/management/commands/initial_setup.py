from django.core.management.base import BaseCommand

from account.models import User
from kiosk.models import Kiosk
from organization.models import OrgLocation, Organization, Role, SystemLocation
from shift.models import Shift, ShiftScheduleLog
from member.models import Member
from datetime import datetime as dt
import pytz

class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        parser.add_argument("organization_name", type=str)
        parser.add_argument("first_name", type=str)
        parser.add_argument("last_name", type=str)
        parser.add_argument("email", type=str)
        parser.add_argument("org_location", type=str)

    def handle(self, *args, **kwargs):

        # take values from arguments
        organization_name = kwargs.get("organization_name", None)
        first_name = kwargs.get("first_name", None)
        last_name = kwargs.get("last_name", None)
        email = kwargs.get("email", None)
        org_location = kwargs.get("org_location", None)

        try:
            # create organization
            organization, _ = Organization.objects.get_or_create(name=organization_name)

            # create roles
            roles = ["admin", "hr", "member", "visitor"]
            for role in roles:
                object, _ = Role.objects.get_or_create(name=role)

            # create user
            user = User.objects.create(email=email, first_name=first_name, last_name=last_name)
            user.is_active = True
            user.is_superuser = True
            user.is_staff = True
            user.set_password("password")
            user.save()

            # create kiosk
            kiosk, _ = Kiosk.objects.get_or_create(kiosk_name="Mobile Kiosk", organization=organization)

            # create org loation
            org_location, _ = OrgLocation.objects.get_or_create(name=org_location, organization=organization)

            # create shift
            shift, _ = Shift.objects.get_or_create(
                name="General",
                start_time="09:00:00",
                end_time="17:00:00",
                organization=organization,
                computation_time="23:00:00",
                enable_geo_fencing=False
            )

            organization.default_shift = shift
            organization.default_org_location = org_location
            organization.save()

            admin_role, _ = Role.objects.get_or_create(name="admin")

            # create member
            member, _ = Member.objects.get_or_create(user=user, organization=organization, role=admin_role)
            member.authorized_kiosks.add(kiosk)
            member.save()

            # ShiftScheduleLog.objects.create(
            #     employee=member,
            #     shift=shift,
            #     start_date=dt.today(),
            #     organization=organization
            # )


        except Exception as error:
            print(error.__class__.__name__, error)
