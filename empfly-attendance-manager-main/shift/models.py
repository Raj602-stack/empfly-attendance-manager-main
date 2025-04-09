from email.policy import default
from django.db import models
import uuid
from organization.models import Organization
from django.core.exceptions import ValidationError
from shift.utils import allow_geo_fencing_if_location_exists

# Create your models here.


class Shift(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("inactive", "Inactive"))

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    start_time = models.TimeField()
    end_time = models.TimeField()

    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE, related_name="shifts")

    default_location = models.ForeignKey(
        "organization.SystemLocation", on_delete=models.PROTECT, related_name="shift_default_locations",  null=True,
    )

    computation_time = models.TimeField()

    present_working_hours = models.FloatField(default=8.0)
    partial_working_hours = models.FloatField(default=4.0)

    skip_days = models.JSONField(default=list, null=True, blank=True)

    enable_face_recognition = models.BooleanField(default=True)
    enable_geo_fencing = models.BooleanField(default=True)

    status = models.CharField(max_length=50, default="active", choices=STATUS_CHOICES)

    shift_start_time_restriction = models.BooleanField(default=True)
    loc_settings_start_time_restriction = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="shift_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="shift_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["name", "organization"]
        ordering = ["-updated_at"]


    def __str__(self) -> str:
        return f"{self.name}__{self.uuid}"


class LocationSettings(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    system_location = models.ForeignKey("organization.SystemLocation", on_delete=models.CASCADE)

    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE)

    start_time = models.TimeField()
    end_time = models.TimeField()

    applicable_start_date = models.DateField()
    applicable_end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="location_settings_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="location_settings_updated_by",
        null=True,
        blank=True,
    )
    class Meta:
        ordering = ["-applicable_start_date"]

    def __str__(self) -> str:
        return f"{self.system_location.name}__{self.uuid}"

    def save(self, *args, **kwargs):
        super(LocationSettings, self).save(*args, **kwargs)

        # allow_geo_fencing_if_location_exists(self.shift)
        # if location settings is config for shift org and shift geo fencing become true
        # shift = self.shift
        # location_settings = LocationSettings.objects.filter(shift=shift)

        # if location_settings.count() > 0:
        #     shift.enable_geo_fencing = True
        #     shift.save()

        #     org = self.system_location.organization
        #     settings = org.shift_management_settings
        #     settings["enable_geo_fencing"] = True
        #     org.shift_management_settings = settings
        #     org.save()


class ShiftScheduleLog(models.Model):
    STATUS_CHOICES = (("active", "Active"), ("inactive", "Inactive"))

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    employee = models.ForeignKey("member.Member", on_delete=models.CASCADE, related_name="shift_schedule_logs")

    shift = models.ForeignKey(Shift, on_delete=models.CASCADE, related_name="shift_schedule_logs")

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # Employee shift mapping
    is_esm = models.BooleanField(default=False)

    status = models.CharField(max_length=50, default="active", choices=STATUS_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
    )

    location_settings = models.ManyToManyField(LocationSettings, related_name="shift_schedule_log", blank=True)

    def __str__(self) -> str:
        return f"date: ( {self.start_date} ---- {self.end_date} ) __________ shift: {self.shift.name} _________ status : {self.status} ________ employee: {self.employee.user.first_name} ______ id: {self.employee.id}"
        # return f"from: {self.start_date}-------to: {self.end_date}-------shift: {self.shift} ------- status:{self.status} ------- is_mapping:{self.is_esm}"

    class Meta:
        ordering = ["-start_date"]
