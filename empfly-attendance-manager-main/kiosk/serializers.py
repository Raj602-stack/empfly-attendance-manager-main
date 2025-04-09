from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from .models import Kiosk
from organization.serializers import OrgLocationSerializer

class KioskSerializer(DynamicFieldsModelSerializer):
    org_location = OrgLocationSerializer()
    class Meta:
        model = Kiosk
        # fields = "__all__"
        exclude = ["access_code"]