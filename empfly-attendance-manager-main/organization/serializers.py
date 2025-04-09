from account.serializers import UserSerializer
from member.models import Member, Profile
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from organization.models import (
    Organization,
    Department,
    Designation,
    Holiday,
    # State,
    # City,
    # Country,
    CostCenter,
    Role,
    OrgLocation,
    SystemLocation,
)
# from shift import serializers as shift_serializer
# from shift.serializers import ShiftSerializer
from shift import serializers as shift_serializers

class SystemLocaitonSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = SystemLocation
        exclude = ["id"]


class OrganizationSerializer(DynamicFieldsModelSerializer):
    default_shift = shift_serializers.ShiftSerializer()
    class Meta:
        model = Organization
        exclude = ["id"]


class DesignationSerializer(DynamicFieldsModelSerializer):
    shift = shift_serializers.ShiftSerializer()
    class Meta:
        model = Designation
        exclude = ["id"]




class CostCenterSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = CostCenter
        exclude = ["id"]





# class CountrySerializer(DynamicFieldsModelSerializer):
#     class Meta:
#         model = Country
#         exclude = ["id"]


# class StateSerializer(DynamicFieldsModelSerializer):
#     class Meta:
#         model = State
#         exclude = ["id"]


# class CitySerializer(DynamicFieldsModelSerializer):

#     state = StateSerializer()
#     country = CountrySerializer()

#     class Meta:
#         model = City
#         exclude = ["id"]


class RoleSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Role
        exclude = ["id"]



#  ============= department serialzer ============
# TODO try to use the MinimalMemberSerializer, ProfileSerializer form the member module
class ProfileSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Profile
        # fields = ["photo"]
        exclude = ["id"]
        
class MinimalMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()
    profile = ProfileSerializer()

    class Meta:
        model = Member
        fields = ["uuid", "user", "profile", "photo"]

class OrgLocationSerializer(DynamicFieldsModelSerializer):
    shift = shift_serializers.ShiftSerializer()
    org_location_head = MinimalMemberSerializer(many=True)

    class Meta:
        model = OrgLocation
        exclude = ["id"]


class DepartmentSerializer(DynamicFieldsModelSerializer):
    department_head = MinimalMemberSerializer(many=True)
    shift = shift_serializers.ShiftSerializer()
    class Meta:
        model = Department
        exclude = ["id"]

class SystemLocaitonSerializer(DynamicFieldsModelSerializer):

    class Meta:
        model = SystemLocation
        exclude = ["id"]


class HolidaySerializer(DynamicFieldsModelSerializer):
    org_location = OrgLocationSerializer()
    class Meta:
        model = Holiday
        exclude = ["id"]