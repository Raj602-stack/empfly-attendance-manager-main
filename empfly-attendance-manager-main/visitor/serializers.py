from rest_framework import serializers
from dataclasses import field
from account.models import User
from member.models import Member
from organization.serializers import OrgLocationSerializer, OrganizationSerializer, RoleSerializer
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from visitor.models import Visitation, Visitor, VisitorScan
from account.serializers import UserSerializer
from kiosk.serializers import KioskSerializer
from member.serializers import MemberSerializer


class VisitorSerializer(DynamicFieldsModelSerializer):
    user = UserSerializer()
    # authorized_kiosks = KioskSerializer(many=True)
    role = RoleSerializer()
    organization = OrganizationSerializer()

    class Meta:
        model = Visitor
        # fields = "__all__"
        exclude = ["id"]

# class VisitorImageSerializer(DynamicFieldsModelSerializer):
#     visitor = VisitorSerializer()

#     class Meta:
#         model = VisitorImage
#         fields = "__all__"

# -------------------------------------------------------------
class TempVisitationSerializer(DynamicFieldsModelSerializer):
    created_by = UserSerializer()
    visitor = VisitorSerializer()
    host = MemberSerializer()
    org_location = OrgLocationSerializer()

    class Meta:
        model = Visitation
        # fields = "__all__"
        exclude = ["id"]

class VisitorScanSerializer(DynamicFieldsModelSerializer):
    visitor = VisitorSerializer()
    kiosk = KioskSerializer()
    visitation = TempVisitationSerializer()

    class Meta:
        model = VisitorScan
        # fields = "__all__"
        exclude = ["id"]
# -------------------------------------------------------------

class CreatedByUserSerializer(DynamicFieldsModelSerializer):
    """Get visitor or member profile image
    """
    photo = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = ["uuid", "first_name", "last_name", "email", "phone", "photo"]
        # exclude = ["id"]

    def get_photo(self, obj):
        member = Member.objects.filter(user=obj)
        if member.exists():
            return MemberSerializer(member.get(), fields=["photo"]).data

        # visitor = Visitor.objects.filter(user=obj)
        # if visitor.exists():
        #     return VisitationSerializer(visitor.get(), fields=["photo"]).data



class VisitationSerializer(DynamicFieldsModelSerializer):
    visitor_scan = VisitorScanSerializer(many=True)
    created_by = CreatedByUserSerializer()
    visitor = VisitorSerializer()
    host = MemberSerializer()
    org_location = OrgLocationSerializer()

    class Meta:
        model = Visitation
        # fields = "__all__"
        exclude = ["id"]