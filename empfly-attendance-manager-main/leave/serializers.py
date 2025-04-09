from unittest import mock
from organization.serializers import OrganizationSerializer
from serializers.dynamic_serializers import DynamicFieldsModelSerializer
from leave.models import (
    LeaveBalanceActivity,
    LeaveType,
    LeaveBalance,
    LeaveRequest,
    Applicability,
    ApprovalWorkflow,
    LeaveRequestActivity,
    RegularizationRequest,
    RegularizationWorkflow,
)
from member.serializers import MemberSerializer


class ApplicabilitySerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = Applicability
        exclude = ["id"]


class LeaveTypeSerializer(DynamicFieldsModelSerializer):

    organization = OrganizationSerializer(fields=["uuid", "name"])
    applicability = ApplicabilitySerializer()

    class Meta:
        model = LeaveType
        exclude = ["id"]


class LeaveBalanceSerializer(DynamicFieldsModelSerializer):

    member = MemberSerializer()
    leave_type = LeaveTypeSerializer()

    class Meta:
        model = LeaveBalance
        exclude = ["id"]


class LeaveBalanceActivitySerializer(DynamicFieldsModelSerializer):

    leave_balance = LeaveBalanceSerializer()

    class Meta:
        model = LeaveBalanceActivity
        exclue = ["id"]


# * Leave Request


class ApprovalWorkflowSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = ApprovalWorkflow
        exclude = ["id"]


class LeaveRequestSerializer(DynamicFieldsModelSerializer):

    member = MemberSerializer()
    leave_type = LeaveTypeSerializer()
    approval_workflow = ApprovalWorkflowSerializer()

    class Meta:
        model = LeaveRequest
        exclude = ["id"]


class LeaveRequestActivitySerializer(DynamicFieldsModelSerializer):

    leave_request = LeaveRequestSerializer()

    class Meta:
        model = LeaveRequestActivity
        exclude = ["id"]


# * Regularization


class RegularizationWorkflowSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = RegularizationWorkflow
        exclude = ["id"]


class RegularizationRequestSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = RegularizationRequest
        exclude = ["id"]