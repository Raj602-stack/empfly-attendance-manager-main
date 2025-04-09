from django.db import models
import uuid
import os
import datetime as dt
from account.models import User
import member.models as member # due to cercular import error

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


def rename_visitor_image(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join(f"visitor/profile/{instance.uuid}/", filename)

def rename_visitor_face_rec_image(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join(f"visitor/face_recognition/{instance.uuid}/", filename)

def rename_visitor_scan_image(instance: models.Model, filename: "file") -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join(f"visitor/scan/{instance.uuid}/", filename)

class Visitor(models.Model):

    VISITOR_STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive")
    )

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    user = models.ForeignKey(
        "account.User", on_delete=models.CASCADE, related_name="visitor"
    )

    inactive_days = models.IntegerField(default=0)
    visitor_company = models.CharField(null=True, blank=True, max_length=200)

    role = models.ForeignKey(
        "organization.Role",
        on_delete=models.CASCADE,
        related_name="visitor",
    )

    status = models.CharField(
        max_length=50,
        choices=VISITOR_STATUS_CHOICES,
        default="active"
    )

    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="visitor",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["organization", "user"]
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):

        # TODO handle this error when creating visitor
        if member.Member.objects.filter(user=self.user, organization=self.organization).exists():
            raise ValueError("User is already a member")

        if self.role.name != "visitor":
            raise ValueError("Visitor role must be visitor.")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email}__{self.uuid}"


class VisitorScan(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    visitor = models.ForeignKey(
        Visitor,
        on_delete=models.CASCADE,
        related_name="visitor_scan"
    )

    visitation = models.ForeignKey(
        "visitor.Visitation",
        on_delete=models.CASCADE,
        related_name="visitor_scan"
    )

    photo = models.ImageField(upload_to=rename_visitor_scan_image)

    date = models.DateField()
    time = models.TimeField()

    kiosk = models.ForeignKey(
        "kiosk.Kiosk",
        on_delete=models.CASCADE,
        related_name="visitor_scan"
    )

    location = models.CharField(null=True, blank=True, max_length=200)

    temperature = models.FloatField(null=True, blank=True)

    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="visitor_scan"
    )
    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.visitor.user.email}__{self.uuid}"



class Visitation(models.Model):

    HOST_AND_VISITOR_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
    )

    VISITATION_STATUS  = (
        ("created", "Created"),
        ("scheduled", "Scheduled"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    )

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)

    name = models.CharField(max_length=200)
    description = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    visitor = models.ForeignKey(
        Visitor,
        on_delete=models.CASCADE,
        related_name="visitation"
    )

    host = models.ForeignKey(
        "member.Member",
        on_delete=models.CASCADE,
        related_name="visitation_host"
    )

    visitation_date = models.DateField()

    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)

    allowed_kiosks = models.ManyToManyField(
        "kiosk.Kiosk",
        related_name="kiosks"
    )

    host_status = models.CharField(
        choices=HOST_AND_VISITOR_STATUS_CHOICES,
        max_length=50,
    )

    visitor_status = models.CharField(
        choices=HOST_AND_VISITOR_STATUS_CHOICES,
        max_length=50,
    )

    visitation_status = models.CharField(
        choices=VISITATION_STATUS,
        max_length=50,
    )

    created_by = models.ForeignKey(
        "account.User",
        on_delete=models.CASCADE,
        related_name="visitation"
    )

    org_location = models.ForeignKey(
        "organization.OrgLocation",
        on_delete=models.CASCADE,
        related_name="visitation",
        null=True
    )

    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="visitation"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name}-{self.uuid}"
