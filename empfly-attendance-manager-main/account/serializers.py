from account.models import User, UserActivity, AuthToken, SessionToken
from serializers.dynamic_serializers import DynamicFieldsModelSerializer


class UserSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = User
        fields = ["uuid", "first_name", "last_name", "email", "phone", "username"]


class UserActivitySerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = UserActivity
        exclude = ["id"]


class SessionTokenSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = SessionToken
        exclude = ["id"]


class UserDataSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "username"]
