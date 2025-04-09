from email.policy import default
from django.db import models
from organization.models import Organization
import uuid
import datetime as dt
from utils import read_data

# Create your models here.


def default_kiosk_settings():
    return {
        "product_serial_number": "",
        "max_temperature": "",
        "working_days": [1, 2, 3, 4, 5, 6],
        "enable_attendance": True,
        "enable_vms": False,
    }


class Kiosk(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="kiosks"
    )

    kiosk_name = models.CharField(max_length=200)
    status = models.BooleanField(default=True)

    start_time = models.TimeField(default=dt.datetime.strptime("00:00", "%H:%M").time())
    end_time = models.TimeField(default=dt.datetime.strptime("23:59", "%H:%M").time())

    settings = models.JSONField(default=default_kiosk_settings, null=True, blank=True)

    access_code = models.CharField(max_length=200)  # Encrypted pwd

    # For validating kiosk. Req user will provide the token
    # Device Identifier Token
    dit = models.CharField(max_length=200, null=True, blank=True)

    # Device Identifier Token expiry
    dit_expiry = models.DateTimeField(null=True, blank=True)

    org_location = models.ForeignKey(
        "organization.OrgLocation", on_delete=models.CASCADE, null=True
    )

    installed_latitude = models.DecimalField(max_digits=9, decimal_places=7)
    installed_longitude = models.DecimalField(max_digits=9, decimal_places=7)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "kiosk_name",
            "organization",
        )
        ordering = ['-updated_at']


    def __str__(self):
        return f"{self.kiosk_name}__{self.organization}"

    def save(self, *args, **kwargs):

        # Encrypt access code and dit
        if self.pk is None:
            self.access_code = read_data.encrypt_text(self.access_code)

            if self.dit:
                self.dit = read_data.encrypt_text(self.dit)
        else:
            kiosk_obj = Kiosk.objects.get(id=self.pk)

            # New access code is assigned
            if kiosk_obj.access_code != self.access_code:
                print("$$$$$$$$$$$$$$$$$ Access Code is changed $$$$$$$$$$$$$$$$$")
                self.access_code = read_data.encrypt_text(self.access_code)

        super(Kiosk, self).save(*args, **kwargs)
