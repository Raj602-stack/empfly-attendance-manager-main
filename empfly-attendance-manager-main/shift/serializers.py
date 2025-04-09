from typing import Tuple
from member.models import Member
from organization.views import system_location
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from shift.models import LocationSettings, Shift, ShiftScheduleLog
from rest_framework import serializers
from account.serializers import UserSerializer

from organization.models import Department, SystemLocation

from organization import models as org_models


# TODO Due to cencular import
# from organization.serializers import OrganizationSerializer
class SystemLocaitonSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = SystemLocation
        exclude = ["id"]


class OrganizationSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = org_models.Organization
        exclude = ["id"]


class ShiftSerializer(DynamicFieldsModelSerializer):
    default_location = SystemLocaitonSerializer()
    organization = OrganizationSerializer()
    class Meta:
        model = Shift
        exclude = ["id"]


class LocationSettingsSerializer(DynamicFieldsModelSerializer):
    system_location = SystemLocaitonSerializer()

    class Meta:
        model = LocationSettings
        exclude = ["id"]


class AllShiftSerializer(DynamicFieldsModelSerializer):
    # location_settings = LocationSettingsSerializer(many=True)
    default_location = SystemLocaitonSerializer()

    class Meta:
        model = Shift
        exclude = ["id"]

class ShiftScheduleLogSerializer(DynamicFieldsModelSerializer):
    shift = AllShiftSerializer()
    location_settings = LocationSettingsSerializer(many=True)

    class Meta:
        model = ShiftScheduleLog
        exclude = ["id"]

class MinimalMemberSerializer(DynamicFieldsModelSerializer):
    user = UserSerializer()
    shift_schedule_logs = ShiftScheduleLogSerializer(many=True)

    class Meta:
        model = Member
        exclude = ["id"]


    # def get_location_settings(self, obj):

    #     shift = None
    #     loc_settings = []

    #     if obj.applicable_shift:
    #         shift, loc_settings = self.retrive_shift_loc_settings(
    #             shift=obj.applicable_shift
    #         )
    #     elif obj.organization.default_shift:
    #         shift, loc_settings = self.retrive_shift_loc_settings(
    #             shift=obj.organization.default_shift
    #         )

    #     return {"location_settings": loc_settings, "applicable_shift": shift}

    # def retrive_shift_loc_settings(
    #     self, shift: Shift
    # ) -> Tuple[ShiftSerializer, LocationSettingsSerializer]:
    #     shift_data = ShiftSerializer(shift).data

    #     loc_settings_data = LocationSettingsSerializer(
    #         shift.location_settings.all(), many=True
    #     ).data

    #     return shift_data, loc_settings_data
