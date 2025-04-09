from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from account.serializers import UserSerializer
# TODO shift
# from roster.models import Cluster, Location, Shift, Roster
from roster.models import Location
from member.models import Member
# BUG Fix this ImportError
# from member.serializers import MemberSerializer


class TempMemberSerializer(DynamicFieldsModelSerializer):

    user = UserSerializer()

    class Meta:
        model = Member
        exclude = ["id"]


class LocationSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Location
        exclude = ["id"]

# TODO shift
# class ShiftSerializer(DynamicFieldsModelSerializer):
#     class Meta:
#         model = Shift
#         exclude = ["id"]


# class RosterSerializer(DynamicFieldsModelSerializer):
#     # TODO shift
#     # shift = ShiftSerializer()
#     location = LocationSerializer()
#     members = TempMemberSerializer(many=True)

#     class Meta:
#         model = Roster
#         exclude = ["id"]


# class ClusterSerializer(DynamicFieldsModelSerializer):

#     locations = LocationSerializer(many=True)
#     managers = TempMemberSerializer(many=True)

#     class Meta:
#         model = Cluster
#         exclude = ["id"]
