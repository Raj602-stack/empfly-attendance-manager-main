from export.utils import get_export_request
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import fetch_data, read_data
from utils.response import HTTP_200

import logging
logger = logging.getLogger(__name__)



class PollExportRequestAPI(views.APIView):
    """ Whe user click export csv button they will get a uuid.
        This uuid represent the export request. After frontend create poll
        request every second if the export csv is done we will send the csv file link.
    """

    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = None

    def get(self, request, *args, **kwargs):
        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        uuid = self.kwargs.get("uuid")
        export_request = get_export_request(member, uuid)
        if export_request is None:
            return read_data.get_404_response("Export Request")

        # If csv is created successfully we will send the link(file path).
        return Response(
            {"status": export_request.status, "link": export_request.link, "uuid": export_request.uuid},
            status=status.HTTP_200_OK,
        )
