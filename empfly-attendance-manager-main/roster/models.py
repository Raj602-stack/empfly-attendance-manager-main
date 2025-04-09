from django.db import models
from django.db.models import Q, CheckConstraint
from django.core.exceptions import ValidationError
import uuid
import logging


logger = logging.getLogger(__name__)


def default_shift_config() -> dict:
    return {
        "working_hours": {"full_day": 8, "half_day": 4, "quarter_day": 2},
        "days": [1, 2, 3, 4, 5],
        "skip_holidays": True,
        "notifications": {
            "absent": {
                "member": True,
                "manager": True,
                "admin": True,
            }
        },
    }


class Location(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    organization = models.ForeignKey(
        "organization.Organization", on_delete=models.CASCADE, related_name="locations"
    )

    name = models.CharField(max_length=200)
    description = models.CharField(max_length=200, null=True, blank=True)

    latitude = models.DecimalField(max_digits=18, decimal_places=14)
    longitude = models.DecimalField(max_digits=18, decimal_places=14)
    radius = models.FloatField(default=50.0)

    email = models.CharField(max_length=320, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="location_created_by",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "member.Member",
        on_delete=models.SET_NULL,
        related_name="location_updated_by",
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["organization", "name"]
        constraints = (
            # Radius should be between 0-5000 meters
            CheckConstraint(
                check=Q(radius__gte=0.0) & Q(radius__lte=5000.0),
                name="location_radius_range",
            ),
        )

    def __str__(self):
        return f"{self.name}__{self.organization}"


# class Shift(models.Model):

#     uuid = models.UUIDField(default=uuid.uuid4, unique=True)
#     organization = models.ForeignKey(
#         "organization.Organization", on_delete=models.CASCADE, related_name="shifts"
#     )

#     name = models.CharField(max_length=200)
#     description = models.CharField(max_length=200, null=True, blank=True)

#     start_time = models.TimeField()
#     end_time = models.TimeField()
#     duration = models.DurationField()
#     computation_time = models.TimeField()
#     """
#     Overtime is a duration field that defines the hours after
#     which the employee's duration is considered as overtime
#     Ex: The required duration is 8 hours abd overtime is set to 9 hours.
#     Generally people work a little over 8 hours say 8.5 hours.
#     This extra 0.5 hours will not be considered as overtime.
#     If anyone works beyond 9 hours, say 9:45, then the extra 45 minutes will be considered as overtime
#     # ! NOTE: Overtime duration should be greated than shift duration
#     """
#     overtime = models.DurationField(blank=True, null=True)

#     # TODO Cannot be deactivated if its assigned to a valid roster
#     is_active = models.BooleanField(default=True)
#     settings = models.JSONField(default=default_shift_config, null=True, blank=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     created_by = models.ForeignKey(
#         "member.Member",
#         on_delete=models.SET_NULL,
#         related_name="shift_created_by",
#         null=True,
#         blank=True,
#     )
#     updated_by = models.ForeignKey(
#         "member.Member",
#         on_delete=models.SET_NULL,
#         related_name="shift_updated_by",
#         null=True,
#         blank=True,
#     )

#     def convert_to_hours(self, attribute):
#         try:
#             return attribute.total_seconds() / 3600
#         except AttributeError as e:
#             logger.error(e)
#             return 0
#         except Exception as e:
#             logger.error(e)
#             logger.exception(
#                 f"Add exception for {e.__class__.__name__} in convert_to_hours"
#             )
#             return 0

#     @property
#     def duration_in_hours(self):
#         return self.convert_to_hours(self.duration)

#     @property
#     def overtime_in_hours(self):
#         return self.convert_to_hours(self.overtime)

#     def save(self, *args, **kwargs):

#         if hasattr(self.overtime, "total_seconds"):
#             if self.overtime.total_seconds() > 0:
#                 if self.overtime < self.duration:
#                     raise ValidationError(
#                         message="Overtime cannot be lesser than duration"
#                     )

#         duration_in_hours = self.duration_in_hours
#         self.settings["working_hours"] = {
#             "full_day": duration_in_hours,
#             "half_day": duration_in_hours / 2,
#             "quarter_day": duration_in_hours / 4,
#         }

#         super(Shift, self).save(*args, **kwargs)

#     class Meta:
#         unique_together = ["organization", "name"]

#     def __str__(self):
#         return f"{self.name}__{self.organization}"


# class Roster(models.Model):

#     uuid = models.UUIDField(default=uuid.uuid4, unique=True)
#     organization = models.ForeignKey(
#         "organization.Organization", on_delete=models.CASCADE, related_name="rosters"
#     )

#     name = models.CharField(max_length=200)
#     description = models.CharField(max_length=200, null=True, blank=True)

#     location = models.ForeignKey(
#         Location,
#         related_name="rosters",
#         on_delete=models.PROTECT,
#         null=True,
#         blank=True,
#     )
#     # shift = models.ForeignKey(Shift, related_name="rosters", on_delete=models.PROTECT)

#     start_date = models.DateField(null=True, blank=True)
#     end_date = models.DateField(null=True, blank=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
#     created_by = models.ForeignKey(
#         "member.Member",
#         on_delete=models.SET_NULL,
#         related_name="roster_created_by",
#         null=True,
#         blank=True,
#     )
#     updated_by = models.ForeignKey(
#         "member.Member",
#         on_delete=models.SET_NULL,
#         related_name="roster_updated_by",
#         null=True,
#         blank=True,
#     )

#     class Meta:
#         unique_together = ["organization", "name"]

#     def save(self, *args, **kwargs):

#         if self.start_date is None and self.end_date is not None:
#             raise ValidationError(
#                 message="start_date is required if end_date is provided"
#             )

#         # CONFIRM Manoj: Is start date and end date both required
#         # CONFIRM Manoj: Is end date if start date is provided
#         if self.end_date is None and self.start_date is not None:
#             raise ValidationError(
#                 message="end_date is required if start_date is provided"
#             )

#         if self.start_date is not None and self.end_date is not None:
#             if self.start_date > self.end_date:
#                 raise ValidationError(message="start_date cannot be past end_date")

#         super(Roster, self).save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.name}__{self.organization}"


# class Cluster(models.Model):
#     STATUS_CHOICES = (
#         ("active", "Active"),
#         ("inactive", "Inactive")
#     )

#     uuid = models.UUIDField(default=uuid.uuid4, unique=True)
#     organization = models.ForeignKey(
#         "organization.Organization", on_delete=models.CASCADE, related_name="clusters"
#     )

#     name = models.CharField(max_length=200)
#     description = models.CharField(max_length=200, null=True, blank=True)

#     locations = models.ManyToManyField("organization.SystemLocation", related_name="cluster", blank=True)
#     managers = models.ManyToManyField("member.Member", related_name="clusters")

#     status = models.CharField(max_length=50, default="active", choices=STATUS_CHOICES)

#     class Meta:
#         unique_together = ("organization", "name")

#     def __str__(self):
#         return f"{self.name}"
