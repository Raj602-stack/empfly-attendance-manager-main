from account.serializers import UserSerializer, UserDataSerializer

# import kiosk
from kiosk.serializers import KioskSerializer
from member.models import Member, MemberImage, Profile
from organization.serializers import (
    DesignationSerializer,
    DepartmentSerializer,
    CostCenterSerializer,
    OrgLocationSerializer,
    OrganizationSerializer,
    RoleSerializer,
)

# TODO add shift
# from roster.serializers import RosterSerializer, ShiftSerializer
# from roster.serializers import RosterSerializer
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from shift.serializers import ShiftScheduleLogSerializer, ShiftSerializer


class ManagerSerializer(DynamicFieldsModelSerializer):
    role = RoleSerializer()
    user = UserSerializer()

    class Meta:
        model = Member
        fields = "__all__"


class MemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()
    designation = DesignationSerializer()
    department = DepartmentSerializer()
    cost_center = CostCenterSerializer()
    # rosters = RosterSerializer(many=True)
    org_location = OrgLocationSerializer()
    role = RoleSerializer()
    authorized_kiosks = KioskSerializer(many=True)
    organization = OrganizationSerializer()
    shift_schedule_logs = ShiftScheduleLogSerializer(many=True)
    manager = ManagerSerializer(
        exclude=["authorized_kiosks", "cost_center", "org_location"]
    )

    class Meta:
        model = Member
        exclude = ["id"]


class MinimalMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()

    class Meta:
        model = Member
        fields = ["uuid", "user"]


class ProfileSerializer(DynamicFieldsModelSerializer):
    member = MemberSerializer()

    class Meta:
        model = Profile
        exclude = ["id"]


class MemberImageSerializer(DynamicFieldsModelSerializer):
    member = MinimalMemberSerializer()

    class Meta:
        model = MemberImage
        exclude = ["id"]



class MemberDataSerializer(DynamicFieldsModelSerializer):

    user = UserDataSerializer()

    class Meta:
        model = Member
        fields = ["uuid", "user"]
