from attendance.filters import filter_report_for_attendance
from attendance.models import Attendance, MemberScan
from member.models import Member
from rest_framework import views, status
from api import permissions
from rest_framework.response import Response
from utils import fetch_data, read_data
from utils import date_time
from utils.response import HTTP_200
from django.db.models import Avg, Count, Max, F
from utils.date_time import curr_dt_with_org_tz
import logging
from visitor.filters import filter_visitations, filter_visitations_for_report
from visitor.models import Visitation, Visitor, VisitorScan

logger = logging.getLogger(__name__)


class VisitorScanReportAPI(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):

        org_uuid = request.headers.get("organization-uuid")
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        visitations = Visitation.objects.filter(organization=org)
        visitations = filter_visitations_for_report(visitations, request)

        visitations = list(
            visitations.values("visitation_status").annotate(status_count=Count("visitation_status"),)
        )
        print(visitations)

        avli_visitation_status = {"created", "scheduled", "cancelled", "completed"}

        for visitation in visitations:
            if visitation.get("visitation_status") not in avli_visitation_status:
                continue
            avli_visitation_status.remove(visitation.get("visitation_status"))


        for avliable_status in avli_visitation_status:
            visitations.append({
                "visitation_status": avliable_status,
                "status_count": 0
            })


        sum_of_total_count = sum(item["status_count"] for item in visitations)

        visitation_with_perc = map(
            lambda data: {
                "percentage": 0 if sum_of_total_count == 0 else (data["status_count"] / sum_of_total_count) * 100,
                "status": data["visitation_status"],
            },
            visitations,
        )

        print(visitation_with_perc)

        return HTTP_200(visitation_with_perc)


class VisitorCurrDayStatus(views.APIView):

    permission_classes = [permissions.IsTokenAuthenticated]

    def get(self, request, *args, **kwargs):
        """ For the current day how much visitor scheduled, completed visitation.
        """

        org_uuid = request.headers.get('organization-uuid')
        org = fetch_data.get_organization(request.user, org_uuid)
        member = fetch_data.get_member(request.user, org.uuid)

        if fetch_data.is_admin_or_hr(member) is False:
            return read_data.get_403_response()

        curr_dt = curr_dt_with_org_tz()
        print(curr_dt)

        visitations = Visitation.objects.filter(
            visitation_date=curr_dt.date(),
            visitor__status="active",
            organization=org,
            visitation_status__in=["scheduled", "completed"]
        )
        visitors = Visitor.objects.filter(organization=org, status="active")

        scheduled = 0
        completed = 0
        no_visitation = 0

        for visitor in visitors:
            visitor_visitation = visitations.filter(visitor=visitor)
            if not visitor_visitation.exists():
                no_visitation += 1
                continue

            scheduled += visitor_visitation.filter(visitation_status="scheduled").count()
            completed += visitor_visitation.filter(visitation_status="completed").count()


        return HTTP_200({
            "visitation_scheduled": scheduled,
            "visitation_completed": completed,
            "no_visitation": no_visitation,
        })
