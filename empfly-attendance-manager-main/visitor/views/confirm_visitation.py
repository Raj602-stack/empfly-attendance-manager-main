from member.models import Member
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import create_data, fetch_data, read_data
from utils.authenticate import authenticate_visitor_or_member
from utils.email_funcs import send_bulk_visitation_update_email, send_visitation_request_mail
from utils.response import HTTP_200, HTTP_400
from visitor.serializers import VisitationSerializer

import logging
from utils.shift import send_visitation_email_on_update

from visitor.models import Visitation
logger = logging.getLogger(__name__)

class AllVisitationConfirmAPI(views.APIView):

    # TODO Verify
    permission_classes = [permissions.IsTokenAuthenticated]
    serializer_class = VisitationSerializer

    def post(self, request, *args, **kwargs):
        """ Accept/Decline visitation for logged in user
        """

        org, requesting_user = authenticate_visitor_or_member(request)

        if fetch_data.is_admin_hr_member_visitor(requesting_user) is False:
            return read_data.get_403_response()

        status = request.data.get('status')

        if status not in ("accepted", "declined"):
            return HTTP_400({}, {"message": "Status must be in accepted/declined."})

        try:
            visitation = Visitation.objects.get(uuid=kwargs["uuid"])
        except Visitation.DoesNotExist:
            return read_data.get_404_response("Visitation")
        
        if visitation.org_location and visitation.org_location.enable_visitation is False:
            return HTTP_400({}, {"message": "Visitations are disabled for this Org Location."})

        role = requesting_user.role.name

        # Inactive users
        if role == "visitor":
            if visitation.visitor.status == "inactive":
                return HTTP_400({}, {"message": "Visitor is inactive."})
        elif role in ("admin", "hr", "member"):
            if visitation.host.status == "inactive":
                return HTTP_400({}, {"message": "Host is inactive."})

        if role == "visitor":

            if visitation.visitor != requesting_user:
                return read_data.get_403_response()

            if visitation.visitor_status != "pending":
                return HTTP_400({}, {"message": f"Visitor already {visitation.visitor_status}."})

        elif role in ("admin", "hr", "member"):

            if visitation.host != requesting_user:
                return read_data.get_403_response()

            if visitation.host_status != "pending":
                return HTTP_400({}, {"message": f"Host already {visitation.visitor_status}."})

        if visitation.visitation_status in ("scheduled", "completed", "cancelled"):
            return HTTP_400({}, {"message": f"Visitation already {visitation.visitation_status}."})

        email_fun = send_bulk_visitation_update_email
        email_content = []

        print(role)
        # TODO remove email_content from above conditions
        if role == "visitor":
            if status == "accepted":
                visitation.visitor_status = "accepted"
                if visitation.host_status == "accepted":
                    visitation.visitation_status = "scheduled"
                    email_content = [
                        {
                            "to": visitation.host.user,
                            "visitation": visitation,
                            "message": "Visitation is scheduled"
                        },
                        {
                            "to": visitation.visitor.user,
                            "visitation": visitation,
                            "message": "Visitation is scheduled"
                        },
                    ]

            elif status == "declined":
                visitation.visitor_status = "rejected"
                visitation.visitation_status = "cancelled"

                email_content = [
                    {
                        "to": visitation.host.user,
                        "visitation": visitation,
                        "message": "Visitation is declined by visitor"
                    },
                ]


        elif role in ("admin", "hr", "member"):
            if status == "accepted":
                visitation.host_status = "accepted"
                if visitation.visitor_status == "accepted":
                    visitation.visitation_status = "scheduled"
                    email_content = [
                        {
                            "to": visitation.host.user,
                            "visitation": visitation,
                            "message": "Visitation is scheduled"
                        },
                        {
                            "to": visitation.visitor.user,
                            "visitation": visitation,
                            "message": "Visitation is scheduled"
                        },
                    ]
                
                elif visitation.visitor_status == "pending":
                    # send email visitor
                    user_name = create_data.get_user_name(visitation.host.user)
                    email_content = {
                        "to": visitation.visitor.user,
                        "visitation": visitation,
                        "message": f"{user_name} sent you a Visitstion Request"
                    }
                    email_fun = send_visitation_request_mail


            elif status == "declined":
                visitation.host_status = "rejected"
                visitation.visitation_status = "cancelled"

                if visitation.visitor_status == "accepted":
                    email_content = [
                        {
                            "to": visitation.visitor.user,
                            "visitation": visitation,
                            "message": "Your Visitation is declined by host"
                        },
                    ]

        visitation.save()
        # email_fun(email_content)
        send_visitation_email_on_update(visitation, request.user)


        print(visitation.host_status,visitation.visitor_status, visitation.visitation_status)


        serializer = self.serializer_class( visitation )
        return HTTP_200(serializer.data)