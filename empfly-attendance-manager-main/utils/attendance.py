from django.db.models import Avg, Sum, Max, Min, Count
from django.db.models import Q

from attendance.models import Attendance, MemberScan
from member.models import Member
from organization.models import Organization
# TODO Shift
# from roster.models import Roster, Shift
from roster.models import Roster


from utils import create_data, read_data, fetch_data

import datetime as dt
import logging

logger = logging.getLogger(__name__)


def mark_absent(member, roster):
    pass


def calc_duration(member, scan_list, roster):
    pass


def compute_attendance(member, scans, roster):

    if scans.count() == 0:
        mark_absent(member, roster)

    scan_list = list(scans)

    if scans.count() % 2 == 0:
        calc_duration(member, scan_list, roster)
    else:
        calc_duration(member, scan_list[: -1], roster)


def get_rosters(org, time: dt.datetime.time) -> Roster:

    return org.rosters.filter(shift__computation__time=time)


def main():

    orgs = Organization.objects.all()
    current_datetime = read_data.get_current_datetime()

    current_time = current_datetime.time()
    current_time_str = f"{current_time.hour}:{current_time.minute}:00"
    current_time = create_data.convert_string_to_datetime(current_time_str, "%H:%M:%S")

    for org in orgs:

        rosters = get_rosters(org, current_time)
        for roster in rosters:

            members = rosters.members.all()
            for member in members:
                scans = member.scans.filter(is_computed=False)
                compute_attendance(member, scans, roster)