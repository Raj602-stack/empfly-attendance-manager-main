from email.policy import default
from django.core.exceptions import ValidationError
from django.db import models
import uuid
import os
import datetime as dt
from visitor.models import Visitor
from organization.models import Role


def rename_image(attribute: uuid.uuid4, filename: str) -> str:
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


def rename_member_fr_images(instance: models.Model, filename: str) -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join("member/face_recognition/", filename)


def rename_profile_image(instance: models.Model, filename: str) -> str:
    filename = rename_image(instance.uuid, filename)
    return os.path.join(f"profile/{instance.uuid}/", filename)


class Member(models.Model):
    MEMBER_STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive")
    )

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    user = models.ForeignKey(
        "account.User", on_delete=models.CASCADE, related_name="members"
    )
    photo = models.ImageField(upload_to=rename_profile_image, null=True, blank=True)

    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="members",
    )
    role = models.ForeignKey(
        "organization.Role",
        on_delete=models.CASCADE,
        related_name="members",
    )

    designation = models.ForeignKey(
        "organization.Designation",
        related_name="members",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    department = models.ForeignKey(
        "organization.Department",
        related_name="members",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    org_location = models.ForeignKey(
        "organization.OrgLocation",
        related_name="members",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    cost_center = models.ForeignKey(
        "organization.CostCenter",
        related_name="members",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    joining_date = models.DateTimeField(null=True, blank=True)
    confirmation_date = models.DateTimeField(null=True, blank=True)

    manager = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="members",
        null=True,
        blank=True,
    )
    approval_workflow = models.ForeignKey(
        "leave.ApprovalWorkflow",
        on_delete=models.SET_NULL,
        related_name="members",
        null=True,
        blank=True,
    )
    regularization_workflow = models.ForeignKey(
        "leave.RegularizationWorkflow",
        on_delete=models.SET_NULL,
        related_name="members",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    authorized_kiosks = models.ManyToManyField(
        "kiosk.Kiosk",
        related_name="members",
        blank=True
    )

    is_front_desk = models.BooleanField(default=False)

    allowed_to_meet = models.BooleanField(blank=True, default=False)
    vehicle_number = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=50, default="active", choices=MEMBER_STATUS_CHOICES)
    employee_id = models.CharField(max_length=200, null=True, blank=True)

    @property
    def is_admin(self) -> bool:
        if self.role.name == "admin":
            return True
        return False

        
    class Meta:
        # unique_together = ["organization", "user"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "user"], name='org_and_user'),
            models.UniqueConstraint(fields=["organization", "employee_id"], name='org_and_employee_id')
        ]
        ordering = ['-created_at']



    # TODO while editing email is changing not user name change that to
    def save(self, *args, **kwargs):

        if self.joining_date is not None and self.confirmation_date is not None:
            if self.confirmation_date < self.joining_date:
                raise ValidationError

        if self.role.name not in ("admin", "hr", "member"):
            raise ValidationError("Role must be in admin/hr/member.")

        # TODO handle this error when member creating
        if Visitor.objects.filter(user=self.user, organization=self.organization).exists():
            raise ValueError("User is already a visitor")

        created = False
        if self.pk is None:
            created = True

        super(Member, self).save(*args, **kwargs)

        if created:
            # Due to circular import
            from utils.create_data import initial_employee_log

            Profile.objects.get_or_create(member=self)
            initial_employee_log(member=self)

    def __str__(self):
        return f"{self.user.email}__{self.uuid}__{self.organization}"


class MemberImage(models.Model):

    uuid = models.UUIDField(unique=True, default=uuid.uuid4)
    member = models.ForeignKey(
        "member.Member", on_delete=models.CASCADE, related_name="member_images"
    )

    image = models.ImageField(upload_to=rename_member_fr_images, null=True, blank=True)
    encoding = models.JSONField(default=dict, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="member_images"
    )

    def __str__(self):
        return f"{self.member}"

    class Meta:
        ordering = ["-updated_at"]

class Profile(models.Model):

    TITLE_CHOICES = (
        ("mr", "Mr"),
        ("ms", "Ms"),
        ("mrs", "Mrs"),
    )
    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female"),
        ("prefer_not_to_say", "Prefer not to say"),
    )
    GOVERNMENT_ID_TYPES = (
        ("passport", "Passport"),
        ("aadhar", "Aadhar"),
        ("driving_license", "Driving License"),
    )
    THEME_CHOICES = (
        ("system", "System"),
        ("light", "Light"),
        ("dark", "Dark"),
    )
    MARITAL_STATUS_CHOICES = (
        ("single", "Single"),
        ("married", "Married"),
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    member = models.OneToOneField("member.Member", related_name="profile", on_delete=models.CASCADE)

    gender = models.CharField(
        max_length=200, choices=GENDER_CHOICES, null=True, blank=True
    )

    address = models.TextField(null=True, blank=True)
    # city = models.ForeignKey(
    #     "organization.City",
    #     related_name="profiles",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    # )

    dob = models.DateField(null=True, blank=True)
    settings = models.JSONField(default=dict, null=True, blank=True)
    government_id = models.CharField(max_length=200, null=True, blank=True)

    # theme = models.CharField(max_length=200, choices=THEME_CHOICES, default="light")
    marital_status = models.CharField(
        max_length=200,
        choices=MARITAL_STATUS_CHOICES,
        # default="single",
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # pin_code = models.CharField(max_length=20, null=True, blank=True)
    # government_id_type = models.CharField(
    #     max_length=200, choices=GOVERNMENT_ID_TYPES, null=True, blank=True
    # )

    def __str__(self):
        return f"{self.member}"
