from enum import unique
from django.db import models
import uuid
import os
import datetime as dt
from django.core.validators import (
    MaxLengthValidator,
    MinValueValidator,
    MaxValueValidator,
)


def default_org_settings():
    return {
        "approval_workflow_priority": [
            "member",
            "designation",
            "location",
            "department",
            "role",
        ],
        "otp_expiry": 2,
        "host_confirmation": True,
        "temperature_integration": True,
        "visitor_management_settings": {"allow_non_invited_visitors": True},
        "applicability_settings_priority": [
            {
                "name": "department",
                "priority": 1,
            },
            {
                "name": "designation",
                "priority": 2,
            },
            {
                "name": "org_location",
                "priority": 3,
            },
            # {
            #     "name": "employee",
            #     "priority": 4,
            # },
        ],
    }


def default_shift_management_settings():
    return {
        "enable_geo_fencing": True,
        "enable_face_recognition": True,
        "location_settings": {"max_location_settings_count": 5},
        "ot_approval": False,
        "automated_ot_approval": True
    }

def default_kiosk_management_settings():
    return {
        "dit_expiry": 24,
    }


def rename_image(attribute: uuid.uuid4, filename: "file") -> str:
    # Gets the file extension
    ext = filename.split(".")[-1]
    # Extracts the seconds passed and the first 3 milliseconds since epoch
    # and concatenates them into a string
    seconds_since_epoch = str(dt.datetime.now().timestamp())[:-3].replace(".", "")
    # Creates unique name based on user ID and time since epoch
    unique_name = f"{attribute}__{seconds_since_epoch}"
    # Concatenates unique name and file extension
    filename = f"{unique_name}.{ext}"
    return filename


def rename_company_logo(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("company/logo/", filename)


def default_limit_settings() -> dict:
    return {"member": 5}

class Organization(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    logo = models.ImageField(upload_to=rename_company_logo, null=True, blank=True)

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(null=True, blank=True)

    location = models.TextField(null=True, blank=True)

    shift_management_settings = models.JSONField(default=default_shift_management_settings, blank=True)
    kiosk_management_settings = models.JSONField(default=default_kiosk_management_settings, blank=True)

    default_shift = models.ForeignKey(
        "shift.Shift", on_delete=models.PROTECT, null=True, blank=True, related_name="organizations"
    )

    default_org_location = models.ForeignKey(
        "organization.OrgLocation", on_delete=models.PROTECT, null=True, blank=True, related_name="organizations"
    )

    organization_email = models.EmailField(null=True, blank=True)
    timezone = models.CharField(max_length=200, default="Asia/Kolkata")

    settings = models.JSONField(default=default_org_settings, null=True, blank=True)
    limit = models.JSONField(default=default_limit_settings, null=True, blank=True)

    STATUS_CHOICES = (("active", "Active"), ("inactive", "Inactive"))
    status = models.CharField(max_length=50, default="active", choices=STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="organization_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="organization_updated_by",
        null=True,
        blank=True,
    )

    last_attendance_computed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.uuid}__{self.name}"


class Designation(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, related_name="designations", on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    approval_workflow = models.ForeignKey(
        "leave.ApprovalWorkflow",
        on_delete=models.SET_NULL,
        related_name="designations",
        null=True,
        blank=True,
    )
    regularization_workflow = models.ForeignKey(
        "leave.RegularizationWorkflow",
        on_delete=models.SET_NULL,
        related_name="designations",
        null=True,
        blank=True,
    )

    shift = models.ForeignKey(
        "shift.Shift",
        on_delete=models.CASCADE,
        related_name="designations",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="designation_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="designation_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("organization", "name")
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.uuid}__{self.name}"


class Department(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, related_name="departments", on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    # department_head = models.OneToOneField(
    #     "member.Member",
    #     on_delete=models.RESTRICT,
    #     related_name="department_head",
    #     # null=True,
    #     # blank=True,
    # )

    department_head = models.ManyToManyField(
        "member.Member",
        blank=True,
        related_name="department_head",
    )


    is_active = models.BooleanField(default=True)


    approval_workflow = models.ForeignKey(
        "leave.ApprovalWorkflow",
        on_delete=models.SET_NULL,
        related_name="departments",
        null=True,
        blank=True,
    )
    regularization_workflow = models.ForeignKey(
        "leave.RegularizationWorkflow",
        on_delete=models.SET_NULL,
        related_name="departments",
        null=True,
        blank=True,
    )

    shift = models.ForeignKey(
        "shift.Shift",
        on_delete=models.CASCADE,
        related_name="departments",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="department_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="department_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("organization", "name")
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.uuid}__{self.name}"


class CostCenter(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    department = models.ForeignKey(Department, related_name="cost_centers", on_delete=models.CASCADE)

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="cost_center_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="cost_center_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ("department", "name")

    def __str__(self):
        return f"{self.organization}__{self.name}"


class Holiday(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)
    date = models.DateField()

    org_location = models.ForeignKey(
        "organization.OrgLocation", related_name="holidays", on_delete=models.CASCADE, null=True, blank=True
    )
    organization = models.ForeignKey(Organization, related_name="holidays", on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="holiday_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="holiday_updated_by",
        null=True,
        blank=True,
    )

    # is_recurring = models.BooleanField(default=False)
    class Meta:
        unique_together = ("organization", "name")

    def __str__(self):
        return f"{self.uuid}__{self.name}"


class Role(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    name = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=200, null=True, blank=True)

    approval_workflow = models.ForeignKey(
        "leave.ApprovalWorkflow",
        on_delete=models.SET_NULL,
        related_name="roles",
        null=True,
        blank=True,
    )
    regularization_workflow = models.ForeignKey(
        "leave.RegularizationWorkflow",
        on_delete=models.SET_NULL,
        related_name="roles",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.name}"


class OrgLocation(models.Model):
    ORG_LOCATION_STATUS_CHOICES = (("active", "Active"), ("inactive", "Inactive"))

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="org_locations",
    )

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=50, default="active", choices=ORG_LOCATION_STATUS_CHOICES)

    org_location_head = models.ManyToManyField(
        "member.Member",
        blank=True,
        related_name="org_location_head",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    shift = models.ForeignKey(
        "shift.Shift",
        on_delete=models.CASCADE,
        related_name="org_locations",
        null=True,
        blank=True,
    )

    enable_visitation = models.BooleanField(default=True)

    # latitude = models.DecimalField(max_digits=18, decimal_places=14)
    # longitude = models.DecimalField(max_digits=18, decimal_places=14)
    # email = models.CharField(max_length=320, null=True, blank=True)
    # phone = models.CharField(max_length=20, null=True, blank=True)
    # is_active = models.BooleanField(default=True)
    # approval_workflow = models.ForeignKey(
    #     "leave.ApprovalWorkflow",
    #     on_delete=models.SET_NULL,
    #     related_name="organization_locations",
    #     null=True,
    #     blank=True,
    # )
    # regularization_workflow = models.ForeignKey(
    #     "leave.RegularizationWorkflow",
    #     on_delete=models.SET_NULL,
    #     related_name="organization_locations",
    #     null=True,
    #     blank=True,
    # )

    # created_by = models.ForeignKey(
    #     "member.Member",
    #     on_delete=models.SET_NULL,
    #     related_name="organization_location_created_by",
    #     null=True,
    #     blank=True,
    # )
    # updated_by = models.ForeignKey(
    #     "member.Member",
    #     on_delete=models.SET_NULL,
    #     related_name="organization_location_updated_by",
    #     null=True,
    #     blank=True,
    # )

    class Meta:
        unique_together = ["organization", "name"]
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.uuid}__{self.name}"


class SystemLocation(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive")
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="system_locations")

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    latitude = models.DecimalField(max_digits=9, decimal_places=7)
    longitude = models.DecimalField(max_digits=9, decimal_places=7)

    radius = models.FloatField(default=50.0)
    # , validators=[MinValueValidator(0.0), MaxValueValidator(5000.0)]

    status = models.CharField(max_length=50, default="active", choices=STATUS_CHOICES)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["organization", "name"]
        ordering = ['-updated_at']


    def __str__(self):
        return f"{self.name}__{self.name}"
