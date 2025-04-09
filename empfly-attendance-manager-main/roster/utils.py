from django.core.exceptions import ValidationError
from kiosk.models import Kiosk
from rest_framework import status
from roster.models import Location
# TODO shift
from rest_framework.response import Response

import uuid as uuid4
import logging


logger = logging.getLogger(__name__)


def get_location(organization_uuid: uuid4, uuid: uuid4) -> Location:
    try:
        return Location.objects.get(organization__uuid=organization_uuid, uuid=uuid)
    except (Location.DoesNotExist, ValidationError) as e:
        logger.error(e)
    except Exception as e:
        logger.error(e)
        logger.exception(f"Add exception for {e.__class__.__name__} in get_location")
    return None

def get_shift():
    pass
# def get_shift(organization_uuid: uuid4, uuid: uuid4) -> Shift:
#     try:
#         return Shift.objects.get(organization__uuid=organization_uuid, uuid=uuid)
#     except (Shift.DoesNotExist, ValidationError) as e:
#         logger.error(e)
#     except Exception as e:
#         logger.error(e)
#         logger.exception(f"Add exception for {e.__class__.__name__} in get_shift")
#     return None


def get_roster(organization_uuid: uuid4, uuid: uuid4):
    pass
    # try:
    #     return Roster.objects.get(organization__uuid=organization_uuid, uuid=uuid)
    # except (Roster.DoesNotExist, ValidationError) as e:
    #     logger.error(e)
    # except Exception as e:
    #     logger.error(e)
    #     logger.exception(f"Add exception for {e.__class__.__name__} in get_roster")
    # return None


# def get_cluster(organization_uuid: uuid4, uuid: uuid4) -> Cluster:
#     try:
#         return Cluster.objects.get(organization__uuid=organization_uuid, uuid=uuid)
#     except (Cluster.DoesNotExist, ValidationError) as e:
#         logger.error(e)
#     except Exception as e:
#         logger.error(e)
#         logger.exception(f"Add exception for {e.__class__.__name__} in get_cluster")
#     return None
