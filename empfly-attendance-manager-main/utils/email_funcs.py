from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.response import Response
from django.utils.encoding import force_bytes
from account.models import User, SessionToken
from core.settings import UI_DOMAIN_URL

from pathlib import Path
import environ
import os

from visitor.models import Visitor

env = environ.Env(DEBUG=(bool, False))
BASE_DIR = Path(__file__).resolve().parent.parent
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

import uuid
import secrets
import logging


def create_email_content(user: User, set_token: bool = True, set_uuid: bool = True) -> dict:
    """Creates dictionary to be used in email template

    Args:
        user (Model): User object
        token (bool, optional): Determines if token should be created.
                                Defaults to True.
        uuid (bool, optional): Determines if uuid should be created.
                              Defaults to True.

    Returns:
        dict: Dictionary containing data for email templates
    """

    token, uuid = None, None

    if set_token:
        token = secrets.token_urlsafe()
        SessionToken.objects.create(user=user, token=token)

    if set_uuid:
        uuid = user.uuid

    return {
        "email": user.email,
        "domain": settings.UI_DOMAIN_URL,
        "user": user,
        "token": token,
        "uuid": uuid,
    }


def send_activation_mail(user: User) -> bool:
    """ When user is created we will send activation email.
        From this page they can set pwd for their account.
    """

    subject = "Activate Your Account"
    content = create_email_content(user)
    email_template_name = "account/email/user/user-activation.html"
    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logging.info("Successfully sent email")
        return True
    except Exception as e:
        logging.exception(f"Add exception for {e.__class__.__name__} " f"in send_activation_mail")
        logging.error(f"Error while sending activation mail: {e}")
        return False


# TODO deprecated
def send_verification_mail(user: User, email: str, token: bool = None) -> bool:

    subject = "Verify Your Email"

    if token:
        content = create_email_content(user, set_token=False, set_uid=True)
        SessionToken.objects.create(user=user, token=token)
        content["token"] = token
    else:
        content = create_email_content()

    email_template_name = "account/email/user/email-verification.html"
    email_content = render_to_string(email_template_name, content)

    try:
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [email],
            fail_silently=False,
            html_message=email_content,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(f"Add exception for {e.__class__.__name__} " f"in send_activation_mail")
        logging.error(f"Error while sending activation mail: {e}")
        return False

# TODO deprecated
def send_invitation_mail(user: User, org_uid: uuid.uuid4, org_name: str) -> bool:

    subject = f"Invitation from {org_name}"
    content = create_email_content(user, set_uid=True, set_token=False)

    content["org_uid"] = org_uid
    content["org_name"] = org_name

    email_template_name = "account/email/user/user-activation.html"

    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(f"Add exception for {e.__class__.__name__} " "in send_activation_mail")
        logging.error(f"Error while sending activation mail: {e}")
        return False


def send_visitation_request_mail(email_content: dict) -> bool:
    """
    Send email with accept/decline button.

    email_content = {
        "to": user,
        "from": created_by,
        "visitation": visitation,
        "message": message
    }
    """

    subject = "Confirm Visitation"
    email_template_name = "visitation_confirm_email.html"

    user = email_content["to"]

    # create Token use for validate user.
    token = secrets.token_urlsafe()

    # Save in SessionToken model when visitor/host requesting we can validate.
    SessionToken.objects.create(user=user, token=token)

    # The variables to be used in the email HTML template
    content = {
        "domain": settings.UI_DOMAIN_URL,
        "token": token,
        # "user": user,
        # "email": user.email,
        # "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        # "uuid":uuid
    }
    
    print()

    content = {**content, **email_content}
    # print("###########"*10)
    # copy = f"http://127.0.0.1:3000/visitation-confirm/{content.get('token')}/{content.get('visitation').uuid}/accepted"
    # copy2 = f"http://127.0.0.1:3000/visitation-confirm/{content.get('token')}/{content.get('visitation').uuid}/declined"
    # print(copy)
    # print()
    # print(copy2)
    # print(content)
    # print("###########"*10)

    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [(content["to"]).email],
            fail_silently=False,
            html_message=email,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(f"Add exception for {e.__class__.__name__} " "in send_visitation_mail")
        logging.error(f"Error while sending visitation email: {e}")
        return False


def send_visitation_update_mail(email_content: dict) -> bool:
    """ Send email on if host or admin or visitor updated visitation
    """

    subject = "Update to Your Visitation"
    email_template_name = "visitation_updates.html"

    user = email_content["to"]

    content = {
        "domain": settings.UI_DOMAIN_URL,
    }

    print(content)

    content = {**content, **email_content}
    email = render_to_string(email_template_name, content)

    print((content["to"]).email)

    try:
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [(content["to"]).email],
            fail_silently=False,
            html_message=email,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(f"Add exception for {e.__class__.__name__} " "in send_visitation_mail")
        logging.error(f"Error while sending visitation email: {e}")
        return False




def send_bulk_visitation_update_email(email_content):
    """ Send multiple emails.
    """

    for content in email_content:
        send_visitation_update_mail(content)


def send_otp_to_email(otp:str, email:str):
    """ Send otp to visitor email for visitation page login.
    """
    subject = f"{otp} - OTP from Empfly"
    email_template_name = "account/email/visitor/visitor_otp.html"
    email_content = render_to_string(email_template_name, {"otp":otp})


    try:
        send_mail(
            f"{subject}",
            "",
            settings.EMAIL_SENDER,
            [email],
            fail_silently=False,
            html_message=email_content,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(
            f"Add exception for {e.__class__.__name__} " f"in send_activation_mail"
        )
        logging.error(f"Error while sending activation mail: {e}")
        return False


def visitor_welcome_email(visitor:Visitor) -> bool:
    """ When visitor is creating visitor get welcome email
    """

    subject = "Welcome Email"
    email_template_name = "visitor_welcome_email.html"

    content = {
        "domain": settings.UI_DOMAIN_URL,
        "visitor": visitor
    }

    email = render_to_string(email_template_name, content)

    try:
        send_mail(
            f"{subject} | Empfly",
            "",
            settings.EMAIL_SENDER,
            [visitor.user.email],
            fail_silently=False,
            html_message=email,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(f"Add exception for {e.__class__.__name__} " "in welcome_email_to_visitor")
        logging.error(f"Error while sending visitor_welcome_email: {e}")
        return False



def send_password_reset_mail(user):

    subject = "Reset Your Password | Empfly"
    content = create_email_content(user=user, set_uuid=True, set_token=True)
    email_template_name = "account/email/user/password-reset.html"
    # Create email template
    email = render_to_string(email_template_name, content)

    try:
        # Send mail to user
        send_mail(
            subject,
            "",
            settings.EMAIL_SENDER,
            [user.email],
            fail_silently=False,
            html_message=email,
        )
        logging.info("Succesfully sent email")
        return True
    except Exception as e:
        logging.exception(e)
        logging.error(
            f"Add exception for {e.__class__.__name__} in send_password_reset_mail"
        )
        return False