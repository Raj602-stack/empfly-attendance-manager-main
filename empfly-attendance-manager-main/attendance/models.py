import datetime as dt
import os
import uuid

from django.db import models
from utils import read_data
from django.contrib.postgres.fields import ArrayField



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


def rename_member_scan_images(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("member/trip_scans/", filename)


class MemberScan(models.Model):

    SCAN_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("computed", "Computed"),
        ("expired", "Expired"),
    )
    SCAN_TYPE_CHOICES = (
        ("check_in", "Check In"),
        ("check_out", "Check Out"),
    )

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    member = models.ForeignKey(
        "member.Member",
        related_name="scans",
        on_delete=models.CASCADE,
    )

    system_location = models.ForeignKey(
        "organization.SystemLocation", on_delete=models.SET_NULL, related_name="scans", null=True, blank=True
    )

    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE)

    image = models.ImageField(upload_to=rename_member_scan_images, null=True, blank=True)

    kiosk = models.ForeignKey("kiosk.Kiosk", on_delete=models.SET_NULL, null=True)

    # date = models.DateField()
    # time = models.TimeField()
    date_time = models.DateTimeField()

    latitude = models.CharField(max_length=200, null=True, blank=True)
    longitude = models.CharField(max_length=200, null=True, blank=True)

    is_computed = models.BooleanField(default=False)
    status = models.CharField(max_length=200, choices=SCAN_STATUS_CHOICES, default="pending")
    scan_type = models.CharField(max_length=200, choices=SCAN_TYPE_CHOICES)

    metadata = models.JSONField(default=dict, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.uuid}__{self.member}"

    class Meta:
        ordering = ["-created_at"]


class Attendance(models.Model):

    OT_STATUS_CHOICES = (
        ("ot_available", "OT Available"),
        ("ot_requested", "OT requested"),
        ("ot_approved", "OT Approved"),
        ("ot_rejected", "OT rejected")
    )

    member = models.ForeignKey(
        "member.Member",
        related_name="attendance",
        on_delete=models.CASCADE,
    )

    organization = models.ForeignKey("organization.Organization", on_delete=models.CASCADE, related_name="attendances")

    date = models.DateField()

    scans = models.ManyToManyField(MemberScan, related_name="attendance", blank=True)

    # present, partial, absent, weekend, holiday
    status = models.CharField(max_length=200, null=True, blank=True)
    status_details = models.JSONField(default=dict, null=True, blank=True)

    difference = models.DurationField(null=True, blank=True)

    # save duration as minutes
    duration = models.FloatField(default=0.0, null=True, blank=True)

    # save as minutes
    late_check_in = models.FloatField(default=0.0, null=True, blank=True)
    # save as minutes
    early_check_out = models.FloatField(default=0.0, null=True, blank=True)
    # save as minutes
    late_check_out = models.FloatField(default=0.0, null=True, blank=True)

    # save as minutes
    overtime = models.FloatField(default=0.0, null=True, blank=True)

    # # Overtime Status
    ot_status = models.CharField(
        max_length=50,
        choices=OT_STATUS_CHOICES,
        null=True,
        blank=True
    )

    visited_system_locations = ArrayField(models.CharField(max_length=100), blank=True, null=True)

    ot_verified_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="attendances",
        null=True,
        blank=True
    )

    shift = models.ForeignKey(
        "shift.Shift",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    remarks = models.TextField(null=True, blank=True)

    @property
    def first_scan(self):
        if self.scans:
            return self.scans.order_by("datetime").first()
        return None

    @property
    def last_scan(self):
        if self.scans:
            return self.scans.order_by("-datetime").first()
        return None

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.member}_{self.date}__{self.status}"


class AttendanceComputationHistory(models.Model):
    STATUS_CHOICES = (("started", "Started"), ("completed", "Completed"), ("failed", "Failed"))

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    organization = models.ForeignKey(
        "organization.Organization",
        related_name="attendance_computation_histories",
        on_delete=models.CASCADE,
    )

    employee_count = models.PositiveIntegerField(default=0)

    shift = models.ForeignKey("shift.Shift", on_delete=models.CASCADE, related_name="attendance_history")

    # Actual attendance date
    attendance_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=50, choices=STATUS_CHOICES)

    computation_started_at = models.DateTimeField()
    computation_ended_at = models.DateTimeField(null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.uuid}__{self.shift.name}"

    class Meta:
        ordering = ["-updated_at"]

class PresentByDefault(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="present_by_default",
    )

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    members = models.ManyToManyField("member.Member", related_name="present_by_default", blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=200, null=True, blank=True)

    def save(self, *args, **kwargs):

        if self.start_date > self.end_date:
            raise ValueError
        if self.start_date > read_data.get_current_datetime():
            raise ValueError

        super(PresentByDefault, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}__{self.organization}"
