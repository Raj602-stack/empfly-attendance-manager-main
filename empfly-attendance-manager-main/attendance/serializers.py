from datetime import timedelta
from attendance.models import MemberScan, Attendance, PresentByDefault
from member.serializers import MemberSerializer
from organization.serializers import SystemLocaitonSerializer
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from shift.serializers import LocationSettingsSerializer
from rest_framework import serializers
from kiosk.serializers import KioskSerializer
from shift.serializers import ShiftSerializer

class MemberScanSerializer(DynamicFieldsModelSerializer):

    member = MemberSerializer()
    system_location = SystemLocaitonSerializer()
    kiosk = KioskSerializer()

    class Meta:
        model = MemberScan
        exclude = ["id"]

class MemberScanSerializer2(DynamicFieldsModelSerializer):

    system_location = SystemLocaitonSerializer(
        fields=[
            "uuid",
            "name"
        ]
    )

    class Meta:
        model = MemberScan
        exclude = ["id"]

class AttendanceSerializer(DynamicFieldsModelSerializer):
    member = MemberSerializer()
    scans = MemberScanSerializer(many=True)
    shift = ShiftSerializer()

    class Meta:
        model = Attendance
        fields = "__all__"
        # exclude = ["id"]

class AttendanceSerializer2(DynamicFieldsModelSerializer):
    member = MemberSerializer(
        fields=[
            "employee_id",
            "uuid",
            "user",
            "photo"
        ]
    )
    scans = MemberScanSerializer2(
        fields=[
            "date_time",
            "scan_type",
            "system_location"
        ],
        many=True
    )
    shift = ShiftSerializer(fields=["name"])
    ot_verified_by = MemberSerializer(
        fields=[
            "uuid",
            "user",
            "photo"
        ]
    )

    class Meta:
        model = Attendance
        fields = "__all__"
        # exclude = ["id"]



class PresentByDefaultSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = PresentByDefault
        exclude = ["id"]