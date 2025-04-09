from django.db import models
from organization.models import Organization
import uuid


def get_default_approval_workflow(organization: Organization):
    approval_workflow, created = ApprovalWorkflow.objects.get_or_create(
        organization=organization, name="Default Workflow"
    )
    if created:
        approval_workflow.criteria = {
            "auto_approval": False,
            "department_head": None,
            "members": [],
            "hr": True,
            "admin": True,
        }
        approval_workflow.approval_types = {
            "auto_approval": False,
            "department_head": None,
            "members": {},
            "hr": True,
            "admin": None,
        }
        approval_workflow.save()

    return approval_workflow


def default_restriction() -> dict:
    return {
        "exceed_leave_balance": False,
        "duration": {"full_day": True, "half_day": True, "quarter_day": True},
        "past_days": True,
        "future_days": True,
        "min_days": True,
        "max_days": True,
    }


def default_policy() -> dict:
    """
    Accrual frequency and credit_on values
    ---
    "frequency": "yearly"
    "credit_on": "31-12" (Dec 31st of every year)
    ---
    "frequency": "half-yearly"
    "credit_on": ["31-06", "31-12"] (June 31st and Dec 31st)
    ---
    "frequency": "monthly"
    "credit_on": 1 (first day of every month)
    ---
    "frequency": "weekly"
    "credit_on": 5 (every Friday) (Sunday=0)
    ---
    "frequency": "daily"
    "credit_on": None (no value required)
    ---
    """

    return {
        "effective_after": {
            "condition": "date_of_joining",
            "days": 0,
        },
        "accrual": {
            "frequency": "monthly",
            "credit_on": 1,  # date of month
            "number_of_days": 0.25,
            "current_accrual": True,
        },
        "reset": {
            "frequency": "yearly",
            "reset_on": "31-12",
            "carry_forward": {
                "unit": "days",  # Percentage
                "value": 0.25,  # Only for percentage
                "max_limit": 10,
            },
        },
        "prorate_accrual": {},
        "variable_priority": [],
    }


class LeaveType(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization",
        related_name="leave_types",
        on_delete=models.CASCADE,
    )

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    is_paid = models.BooleanField(default=True)
    unit = models.CharField(max_length=200, default="days")

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    restriction = models.JSONField(default=default_restriction, null=True, blank=True)
    policy = models.JSONField(default=default_policy, null=True, blank=True)

    class Meta:
        unique_together = ("organization", "name")

    def save(self, *args, **kwargs):

        if self.pk is None:
            created = True
        else:
            created = False

        super(LeaveType, self).save(*args, **kwargs)
        if created:
            Applicability.objects.create(leave_type=self)

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    member = models.ForeignKey(
        "member.Member", related_name="leave_balances", on_delete=models.CASCADE
    )
    leave_type = models.ForeignKey(
        LeaveType, related_name="leave_balances", on_delete=models.CASCADE
    )

    available = models.FloatField(default=0)
    booked = models.FloatField(default=0)
    lapsed = models.FloatField(default=0)

    class Meta:
        unique_together = ("member", "leave_type")

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        super(LeaveBalance, self).save(force_insert, force_update)

        if kwargs:
            kwargs = kwargs.get("activity_kwargs", {})
            if kwargs:
                LeaveBalanceActivity.objects.create(
                    leave_balance=self,
                    action=kwargs.get("action"),
                    days=kwargs.get("days"),
                    metadata=kwargs.get("metadata"),
                )

    def __str__(self):
        return f"{self.member}__{self.leave_type}"


class LeaveBalanceActivity(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    leave_balance = models.ForeignKey(
        LeaveBalance, related_name="leave_balance_activities", on_delete=models.CASCADE
    )

    action = models.CharField(max_length=20, default="credit")
    days = models.FloatField(default=0)
    metadata = models.JSONField(default=dict, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "member.Member",
        related_name="leave_balance_activities",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name_plural = "Leave balance activities"

    def __str__(self):
        return f"{self.leave_balance}__{self.created_at}"


class LeaveRequest(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    member = models.ForeignKey(
        "member.Member", related_name="leave_requests", on_delete=models.CASCADE
    )
    leave_type = models.ForeignKey(
        LeaveType, related_name="leave_requests", on_delete=models.CASCADE
    )
    approval_workflow = models.ForeignKey(
        "leave.ApprovalWorkflow",
        on_delete=models.SET_NULL,
        related_name="leave_requests",
        null=True,
        blank=True,
    )

    unit = models.CharField(max_length=200, default="days")
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.FloatField()
    config = models.JSONField(default=dict, null=True, blank=True)

    settings = models.JSONField(default=dict, null=True, blank=True)
    reason = models.CharField(max_length=200)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    status_details = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self):
        return f"{self.member}__{self.leave_type}"

    def get_associated_leave_balance(self):
        return LeaveBalance.objects.get(member=self.member, leave_type=self.leave_type)

    def create_status_details(self, approval_types):
        temp = {}
        for key, value in approval_types.items():
            if (key == "auto_approval") or (key == "members" and len(value) == 0):
                continue
            if value is not None:
                temp[key] = "pending"
        return temp

    def update_leave_balance(self):
        leave_balance = self.get_associated_leave_balance()

        if self.unit == "days":
            days = self.days

        leave_balance.available -= days
        leave_balance.booked += days
        leave_balance.save()

    def reset_leave_balance(self):
        leave_balance = self.get_associated_leave_balance()

        if self.unit == "days":
            days = self.days

        leave_balance.available += days
        leave_balance.booked -= days
        leave_balance.save()

    def save(self, force_insert=False, force_update=False, *args, **kwargs):

        created = False
        if self.pk is None:
            created = True

        if created:
            if self.approval_workflow is None:
                self.approval_workflow = get_default_approval_workflow(
                    self.member.organization
                )
            self.status_details = self.create_status_details(
                self.approval_workflow.approval_types
            )

        super(LeaveRequest, self).save(force_insert, force_update)

        if created:
            self.update_leave_balance()

        if self.status == "denied":
            self.reset_leave_balance()

        if kwargs:
            kwargs = kwargs.get("activity_kwargs", {})
            if kwargs:
                LeaveRequestActivity.objects.create(
                    leave_request=self,
                    action=kwargs.get("action"),
                    object=kwargs.get("object"),
                    value=kwargs.get("value"),
                    created_by=kwargs.get("created_by"),
                )


class Applicability(models.Model):

    GENDER_CHOICES = (
        ("all", "All"),
        ("male", "Male"),
        ("female", "Female"),
    )

    MARITAL_STATUS_CHOICES = (
        ("all", "All"),
        ("single", "Single"),
        ("married", "Married"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    leave_type = models.OneToOneField(
        LeaveType, related_name="applicability", on_delete=models.CASCADE
    )

    gender = models.CharField(max_length=200, choices=GENDER_CHOICES)
    marital_status = models.CharField(max_length=200, choices=MARITAL_STATUS_CHOICES)

    locations = models.ManyToManyField(
        "roster.Location", related_name="applicabilities", blank=True
    )
    exclude_locations = models.ManyToManyField(
        "roster.Location", related_name="applicabilities_exclusion", blank=True
    )

    departments = models.ManyToManyField(
        "organization.Department", related_name="applicabilities", blank=True
    )
    exclude_departments = models.ManyToManyField(
        "organization.Department", related_name="applicabilities_exclusion", blank=True
    )

    designations = models.ManyToManyField(
        "organization.Designation", related_name="applicabilities", blank=True
    )
    exclude_designations = models.ManyToManyField(
        "organization.Designation", related_name="applicabilities_exclusion", blank=True
    )

    roles = models.ManyToManyField(
        "organization.Role", related_name="applicabilities", blank=True
    )
    exclude_roles = models.ManyToManyField(
        "organization.Role", related_name="applicabilities_exclusion", blank=True
    )

    members = models.ManyToManyField(
        "member.Member", related_name="applicabilities", blank=True
    )
    exclude_members = models.ManyToManyField(
        "member.Member", related_name="applicabilities_exclusion", blank=True
    )

    class Meta:
        verbose_name_plural = "Applicabilities"

    def __str__(self):
        return f"{self.leave_type.organization}__{self.leave_type.name}"


def default_criteria() -> dict:
    """
    {
        "object": "dept",
        "condition": "is",
        "value": [123, 345]
    }
    """

    return {
        "criterion": [
            {
                "object": "Department",
                "condition": "equals",
                "value": 1,
            },
            {
                "object": "Designation",
                "condition": "equals",
                "value": 1,
            },
        ],
        "match_any": True,
        "match_all": False,
    }


def default_approval_types() -> dict:
    return {
        "auto_approval": False,  # Automatically approve leave requests if True
        "department_head": None,  # The department head of the requester will have to approve
        "members": {},  # List of employees who can approve,
        "hr": None,  # Send approval request to HR Role users
        "admin": None,  # Send approval request to Admin Role users
    }


class ApprovalWorkflow(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        Organization, related_name="approval_workflows", on_delete=models.CASCADE
    )

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    criteria = models.JSONField(default=default_criteria, null=True, blank=True)
    approval_types = models.JSONField(
        default=default_approval_types, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="approval_workflow_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="approval_workflow_updated_by",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name}"


class LeaveRequestActivity(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    leave_request = models.ForeignKey(
        LeaveRequest, related_name="leave_request_activities", on_delete=models.CASCADE
    )

    action = models.CharField(max_length=200, null=True, blank=True)
    object = models.CharField(max_length=200, null=True, blank=True)
    value = models.CharField(max_length=200, null=True, blank=True)
    metadata = models.JSONField(default=dict, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="leave_request_activities_created_by",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name_plural = "Leave request activities"

    def __str__(self):
        return f"{self.leave_request}__{self.created_at}"


class RegularizationWorkflow(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        Organization, related_name="regularization_workflows", on_delete=models.CASCADE
    )

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    criteria = models.JSONField(default=default_criteria, null=True, blank=True)
    approval_types = models.JSONField(
        default=default_approval_types, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="regularization_workflow_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="regularization_workflow_updated_by",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name}"


class RegularizationRequest(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    member = models.ForeignKey(
        "member.Member",
        related_name="regularization_requests",
        on_delete=models.CASCADE,
    )

    date = models.DateField()
    reason = models.CharField(max_length=200)
    check_in = models.DateTimeField()
    check_out = models.DateTimeField()

    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="pending")
    status_details = models.JSONField(default=dict, null=True, blank=True)

    regularization_workflow = models.ForeignKey(
        "leave.RegularizationWorkflow",
        on_delete=models.SET_NULL,
        related_name="leave_requests",
        null=True,
        blank=True,
    )


class RegularizationRequestActivity(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    regularization_request = models.ForeignKey(
        RegularizationRequest,
        related_name="regularization_request_activities",
        on_delete=models.CASCADE,
    )

    action = models.CharField(max_length=200, null=True, blank=True)
    object = models.CharField(max_length=200, null=True, blank=True)
    value = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="regularization_request_activities_created_by",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name_plural = "Regularization request activities"

    def __str__(self):
        return f"{self.leave_request}__{self.created_at}"
