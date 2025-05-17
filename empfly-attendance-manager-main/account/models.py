from django.db import IntegrityError, models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.utils import crypto
# from env import SUPER_USERS

import environ
env = environ.Env()
environ.Env.read_env()

SUPER_USERS = env("SUPER_USERS", default="").split(",")


from rest_framework.authtoken.models import Token

import datetime as dt
import os
import uuid


def rename_image(attribute: uuid.uuid4, filename: str) -> str:
    # Get the file extension
    ext = filename.split(".")[-1]
    # Extract the seconds passed and the first 3 milliseconds since epoch
    # and concatenate them into a string
    seconds_since_epoch = str(dt.datetime.now().timestamp())[:-3].replace(".", "")
    # Create unique name based on user ID and time since epoch
    unique_name = f"{attribute}__{seconds_since_epoch}"
    # Concatenate unique name and file extension
    filename = f"{unique_name}.{ext}"
    return filename


class UserManager(BaseUserManager):
    """Django Custom User Manager

    Used for creating and customizing User objects
    """

    def create_user(self, username, email, password, first_name=None, last_name=None):

        if not email:
            raise ValueError("User must have an email")

        if not password:
            raise ValueError("User must have a password")

        # Normalize the email address by lowercasing the domain part of it
        user = self.model(email=self.normalize_email(email))

        user.set_password(password)
        user.first_name = first_name
        user.last_name = last_name

        user.is_active = False
        user.save(using=self._db)
        return user

    def create_superuser(
        self, username, email, password, first_name=None, last_name=None
    ):

        if not email:
            raise ValueError("User must have an email")

        if not password:
            raise ValueError("User must have a password")

        # Normalize the email address by lowercasing the domain part of it
        user = self.model(email=self.normalize_email(email))
        # Calls the create_user method mentioned above
        user = self.create_user(username, email, password, first_name, last_name)

        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save(using=self._db)

        return user


class User(AbstractUser):
    """
    Model to authorize and allow access to the web app and browse-able API
    """

    username = models.CharField(max_length=200, unique=True)

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    email = models.EmailField(null=True, blank=True)
    # TODO Confirm is unique or not
    phone = models.CharField(max_length=15, null=True, blank=True)

    first_name = models.CharField(max_length=200)
    last_name = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    recent_organization_uuid = models.UUIDField(null=True, blank=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []

    # objects = UserManager()

    def save(self, *args, **kwargs):

        # self.first_name = self.first_name if self.first_name else None

        users = User.objects.all()

        self.email = self.email if self.email else None
        self.phone = self.phone if self.phone else None

        if not self.first_name:
            raise ValueError("First Name is required.")

        # if self.pk is None:
        #     if self.email:
        #         self.email = self.email.lower()
        #         self.username = self.email
        #     elif self.phone:
        #         self.username = self.phone.lower()
        #     elif self.username:
        #         self.username = self.username.lower()
        #     else:
        #         raise ValueError
        #     self.is_active = False
        # else:
        #     if self.email:
        #         self.email = self.email.lower()
        #         self.username = self.email
        #         users = users.exclude(id=self.pk)
        #     elif self.phone:
        #         self.username = self.phone
        #         users = users.exclude(id=self.pk)

        # If user is being created
        if self.pk is None:
            # If email exists, set username to email
            # Else set username to phone number
            if self.email:
                self.email = self.email.lower()
                self.username = self.email.lower()
            elif self.phone:
                self.username = self.phone.lower()
            elif self.username:
                self.username = self.username.lower()
            else:
                raise ValueError

            self.is_active = False

        else:
            if self.email:
                self.email = self.email.lower()
                self.username = self.email.lower()
                users = users.exclude(id=self.pk)
            elif self.phone:
                self.username = self.phone
                users = users.exclude(id=self.pk)

        if self.username:
            if users.filter(username=self.username).exists():
                raise IntegrityError

        if self.email:
            if users.filter(email=self.email).exists():
                raise IntegrityError

        if self.phone:
            if users.filter(phone=self.phone).exists():
                raise IntegrityError

        self.has_superuser_permission()

        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.username}__{self.uuid}"

    def has_superuser_permission(self):
        if not self.email:
            return

        email = self.email.lower()
        if email in SUPER_USERS:
            self.is_superuser = True
            self.is_staff = True
        else:
            self.is_superuser = False
            self.is_staff = False

class UserActivity(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    user = models.ForeignKey(
        User, related_name="user_activities", on_delete=models.CASCADE
    )

    actor = models.ForeignKey(
        User,
        related_name="user_activities_actor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=200, null=True, blank=True)
    object = models.CharField(max_length=200, null=True, blank=True)
    old_value = models.CharField(max_length=200, null=True, blank=True)
    new_value = models.CharField(max_length=200, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "User activities"

    def __str__(self):
        return f"{self.actor}__{self.action}__{self.object}"


class AuthToken(Token):

    key = models.CharField(_("Key"), max_length=40, db_index=True, unique=True)
    user = models.ForeignKey(
        User,
        related_name="auth_tokens",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
    )

    active = models.BooleanField(default=True)
    name = models.CharField(_("Name"), max_length=64)

    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        related_name="auth_tokens_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = (("user", "name"),)

    def __str__(self):
        return f"{self.user}_{self.name}"


class SessionToken(models.Model):

    user = models.ForeignKey(
        User, related_name="session_tokens", on_delete=models.CASCADE
    )
    token = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.email}__{self.token}"


class OTP(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4, unique=True, primary_key=True, editable=False
    )
    otp = models.CharField(max_length=4)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.uuid}__{self.email}"
