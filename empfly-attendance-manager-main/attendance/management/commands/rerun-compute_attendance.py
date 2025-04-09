import logging
import zoneinfo

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone as tz
from django.db import connection

from attendance.models import Attendance, AttendanceComputationHistory, MemberScan
from organization.models import Holiday, Organization
from shift.models import Shift, ShiftScheduleLog
from django.db.models import F
# from django.db.models.functions import TimeZone
from attendance.constants import MAX_MIN_FOR_OT_REQUEST
from utils.date_time import curr_date_time_with_tz

# configure logging
logging.basicConfig(
    filename="logs/attendance.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)




class Command(BaseCommand):
    help = "Compute attendance every hour based on shift computation time"

    def __init__(self) -> None:
        super().__init__()
        self.scans_count = 0
        self.attendance_computation_status = "started"
        self.attendance_computation_history_obj = None
        self.employee_count = 0
        self.is_holiday = False
        self.org_timezone = "UTC"
        self.max_minutes = 1440

        self.actual_shift_end_dt = None
        self.actual_shift_start_dt = None

    def limit_duration(self, duration):
        """function to limit the minutes to maximum minutes"""
        # if duration is exceeding 24 hours
        # take duration as 24 hours in minutes
        return duration if duration <= self.max_minutes else self.max_minutes

    def add_attendance(self, organization, employee, date, scans, shift):
        """function to create attendance with overtime, late check-in, early check-in, status details for current employee"""

        scans_length = self.scans_count

        logging.info(f"Scan length: {scans_length}")

        # If even number of scans -> Calculate duration of all scans
        # If odd number of scans -> Calculate duration of all scans except the last scan
        duration = self.calc_duration(scans, scans_length if scans_length % 2 == 0 else (scans_length - 1))

        logging.info(f"duration in minutes: {duration}")


        # attendance, created = Attendance.objects.get_or_create(
        #     member=employee, date=date, organization=organization, defaults={"duration": self.limit_duration(duration)}
        # )

        # If duration is more than 24 h we will just limit to 24
        limited_duration = self.limit_duration(duration)

        attendance, created = Attendance.objects.get_or_create(
            member=employee, date=date, organization=organization, defaults={"duration": limited_duration}, shift=shift
        )

        logging.info(f"attendance.duration: {attendance.duration}")
        attendance.duration = limited_duration

        logging.info(f"attendance.duration: {attendance.duration}")
        logging.info(f"attendance: {attendance}")
        logging.info(f"attendance created: {created}")
        logging.info(f"self.limit_duration(duration): {self.limit_duration(duration)}")



        # ******************************** LATE CHECK-IN COMPUTATION ******************************
        try:
            first_scan = scans[0]

            # shift_start_time = tz.make_aware(tz.datetime.combine(date, shift.start_time), timezone=self.org_timezone)
            shift_start_time = self.actual_shift_start_dt
            first_scan_time = tz.localtime(first_scan.date_time, timezone=self.org_timezone)


            logging.info(f"first_scan_time: {first_scan_time}")
            logging.info(f"shift_start_time: {shift_start_time}")

            # print("here", first_scan_time, shift_start_time)

            # Calculate the seconds the employee was late by
            late_duration = first_scan_time - shift_start_time

            # Convert seconds to minutes
            late_duration = late_duration.total_seconds() / 60

            if late_duration > 0:

                attendance.late_check_in = float(self.limit_duration(late_duration))

        except Exception as e:
            logging.error(f"Error {e.__class__.__name__}: {e}")
            logging.error(f"Failed to compute late check in for " f"{employee} on {date}")

        # ******************************** EARLY CHECK-OUT & OVERTIME COMPUTATION *************************
        try:
            # if number of member scan is greater than 1
            if scans_length > 1:
                # take last even scan as last scan, because even scans are check-out scans
                # odd scan will be considered as check-in scans
                last_scan = scans[scans_length - 1] if scans_length % 2 == 0 else scans[scans_length - 2]

                # if night shift
                # shift end date will be considered as current date
                # shift_end_date = date + tz.timedelta(days=1) if shift.start_time > shift.end_time else date

                # shift_end_time = tz.make_aware(
                #     tz.datetime.combine(shift_end_date, shift.end_time), timezone=self.org_timezone
                # )
                shift_end_time = self.actual_shift_end_dt
                last_scan_time = tz.localtime(last_scan.date_time, timezone=self.org_timezone)

                # print(last_scan_time, shift_end_time, last_scan_time - shift_end_time)
                # Calculate the time difference
                duration_difference = last_scan_time - shift_end_time

                logging.info(f"last_scan_time: {last_scan_time}")
                logging.info(f"shift_end_time: {shift_end_time}")

                # Convert seconds to minutes
                duration_difference = duration_difference.total_seconds() / 60

                print("********************************")
                print(f"duration_difference: {duration_difference}")
                print("********************************")

                shift_present_working_min = shift.present_working_hours * 60
                total_attendance_duration_in_min = attendance.duration

                print(f"shift_present_working_min: {shift_present_working_min}")
                print(f"total_attendance_duration: {total_attendance_duration_in_min}")

                # Calculate overtime using shift present working hour.
                overtime = 0
                if total_attendance_duration_in_min > shift_present_working_min:
                    overtime = total_attendance_duration_in_min - shift_present_working_min

                print(f"overtime: {overtime}")

                # Check overtime is exists then give for OT approval.
                if overtime > 0:
                    overtime = self.limit_duration(overtime)
                    attendance.overtime = overtime
                    attendance_duration = attendance.duration

                    org_ot_approval = organization.shift_management_settings.get(
                        "ot_approval", False
                    )
                    automated_ot_approval = organization.shift_management_settings.get(
                        "automated_ot_approval", True
                    )

                    print("attendance_duration: ", attendance_duration)
                    print("overtime: ", overtime)

                    if org_ot_approval is True:
                        if overtime >= MAX_MIN_FOR_OT_REQUEST:
                            if automated_ot_approval is False:
                                # Enable ot manually
                                attendance.ot_status = "ot_available"
                            else:
                                # Raise request automatically
                                attendance.ot_status = "ot_requested"

                            attendance.duration = attendance_duration - overtime
                        else:
                            attendance.ot_status = None
                            attendance.duration = attendance_duration
                    else:
                        attendance.ot_status = None
                        attendance.duration = attendance_duration

                if duration_difference > 0:
                    # Late check out
                    late_check_out_in_min = self.limit_duration(duration_difference)
                    attendance.late_check_out = late_check_out_in_min
                else:
                    # Early check out
                    attendance.early_check_out = float(abs(self.limit_duration(duration_difference)))

                # if last scan time is greater than shift end time
                # take that shift end time to last scan time as overtime
                # if duration_difference > 0:
                #     # TODO Add late check out
                #     late_check_out = self.limit_duration(duration_difference)
                #     attendance.late_check_out = late_check_out

                    # # =========== New Logic ===========
                    # overtime = self.limit_duration(duration_difference)
                    # attendance.overtime = overtime
                    # attendance_duration = attendance.duration

                    # org_ot_approval = organization.shift_management_settings.get(
                    #     "ot_approval", False
                    # )

                    # print("attendance_duration: ", attendance_duration)
                    # print("overtime: ", overtime)

                    # if org_ot_approval is True:
                    #     if overtime >= MAX_MIN_FOR_OT_REQUEST:
                    #         print("======Overtime Fount")
                    #         attendance.ot_status = "ot_requested"
                    #         attendance.duration = attendance_duration - overtime
                    #         print("new attendance duration", attendance.duration)
                    #     else:
                    #         attendance.ot_status = None
                    #         attendance.duration = attendance_duration
                    # else:
                    #     attendance.ot_status = None
                    #     attendance.duration = attendance_duration

                    # =========== Old Logic ===========

                    # late_check_in = attendance.late_check_in if attendance.late_check_in else 0
                    # overtime = self.limit_duration(duration_difference)
                    # # if overtime greater than late_check_in time
                    # # overtime minus late_check_in time, we can consider remaining time as overtime
                    # if overtime > late_check_in:
                    #     attendance.overtime = float(overtime - late_check_in)

                # if last scan time is lesser than shift end time
                # take that last scan time to shift end time as early check-out time
                # else:
                #     attendance.early_check_out = float(abs(self.limit_duration(duration_difference)))

        except Exception as e:
            logging.error(f"Error {e.__class__.__name__}: {e}")
            logging.error(f"Failed to compute early check out for " f"{employee} on {date}")

        # ***************************** SET ATTENDANCE STATUS ********************************

        total_shift_present_hours, total_shift_partial_hours = shift.present_working_hours, shift.partial_working_hours

        logging.info(f"{total_shift_present_hours=} \n {total_shift_partial_hours=}")

        # convert minutes to hours
        attendance_duration_in_hours = attendance.duration / 60

        logging.info(f"attendance_duration_in_hours: {attendance_duration_in_hours}")
        logging.info(f"attendance.duration: {attendance.duration}")

        if attendance_duration_in_hours >= total_shift_present_hours:
            logging.info(f"attendance_duration_in_hours >= total_shift_present_hours: {attendance_duration_in_hours >= total_shift_present_hours}")
            attendance.status = "present"
        elif attendance_duration_in_hours >= total_shift_partial_hours:
            logging.info(f"attendance_duration_in_hours >= total_shift_partial_hours: {attendance_duration_in_hours >= total_shift_partial_hours}")
            attendance.status = "partial"
        else:
            logging.info(f"None of the condition worked mark as absent.")
            attendance.status = "absent"

        # mark attendance status as weekend
        # if weekday is in skip days
        if date.weekday() in shift.skip_days:
            attendance.status = "weekend"

        # attendance date is holiday
        if self.is_holiday:
            attendance.status = "holiday"

        # convert minutes to HH:MM format
        attendance_dur_in_hm = f"{int(duration // 60)}:{int(duration % 60)}"
        logging.info(f"Duration (HH:MM): {attendance_dur_in_hm} Status: {attendance.status}")

        # ********************************** SET MEMBER SCAN STATUS ***********************************************

        evenScans = list(scans.values_list("id", flat=True))
        oddScans = []

        logging.info(f"evenScans: {evenScans}")

        # if length of scan objects is odd
        if scans_length % 2 != 0:
            print("odd scans")
            evenScans = evenScans[: scans_length - 1]
            oddScans = list(scans.values_list("id", flat=True)[scans_length - 1 :])

        logging.info(f"evenScans: {evenScans}")
        logging.info(f"oddScans: {oddScans}")

        # print(connection.queries[-1])
        # print(f"{evenScans=} \n {oddScans=}")

        # Get all the even number of scans
        # change status to computed and set is_computed to True
        if evenScans:
            MemberScan.objects.filter(id__in=evenScans).update(is_computed=True, status="computed")
            # print(connection.queries[-1])

        # Get odd number of scans
        # change status to expired and set is_computed to True
        if oddScans:
            MemberScan.objects.filter(id__in=oddScans).update(is_computed=True, status="expired")

        attendance.scans.add(*evenScans, *oddScans)
        # save attendance instance
        attendance.save()

        # print(len(connection.queries))
        # *****************************************************************************************************

    def calc_duration(self, scans, length):
        """function to calculate time difference between every two scans"""
        i = 0
        total_duration = 0

        # Fetch duration between every 2 scans
        # If 4 scans, calculate difference between (1, 2) and (3, 4).
        # Add up the differences to get total duration
        while i < length:
            start_scan, end_scan = scans[i], scans[i + 1]

            duration = tz.localtime(end_scan.date_time, timezone=self.org_timezone) - tz.localtime(
                start_scan.date_time, timezone=self.org_timezone
            )
            # duration in minutes
            duration = duration.total_seconds() / 60

            total_duration += duration

            i += 2

        # total_duration in minutes
        return total_duration

    def mark_attendance(self, organization, employee, date, status, shift=None):

        _, created = Attendance.objects.get_or_create(
            member=employee,
            date=date,
            organization=organization,
            shift=shift,
            defaults={
                "duration": 0.0,
                "status": status,
            },
        )

        logging.info(f"created: {created}")

        if not created:
            logging.info(f"Duplicate attendance record for {employee} prevented.")

    def update_attendance_computation_history(self):
        try:
            history_obj = self.attendance_computation_history_obj
            # if attendance_computation is not failed set status as completed else as failed
            history_obj.status = "completed" if self.attendance_computation_status != "failed" else "failed"
            # set employee count
            history_obj.employee_count = self.employee_count
            # set attendance computation end time
            history_obj.computation_ended_at = tz.localtime(tz.now(), timezone=self.org_timezone)
            # save the attendance computation history instance
            history_obj.save()
        except Exception as error:
            logging.info(f"Error {error.__class__.__name__}: {error}")

    # # TODO deprecated
    # def check_holiday(self, organization, attendance_date, shift):
    #     # Filter holidays by current date
    #     holidays = Holiday.objects.filter(organization=organization, date=attendance_date, is_active=True)

    #     # if there is a holiday for attendance date and,
    #     # there is no org location for that holiday
    #     # holiday will be applicable for all the employees
    #     if holiday and not holiday.org_location:
    #         # holiday = holidays.first()
    #         return True

    #     # if there is a holiday with org location for attendance date
    #     # only for that org location employee this holiday will be applicable
    #     elif holiday and holiday.org_location and shift.holiday_org_location:
    #         holidays = holidays.filter(org_location=shift.holiday_org_location)
    #         if holidays.exists():
    #             return True

    #     return False


    def is_have_holiday(self, organization, attendance_date, shift, employee):
        # Filter holidays by current date
        logging.info("")
        logging.info(f"Checking Holiday for : {employee}")

        holidays = Holiday.objects.filter(organization=organization, date=attendance_date, is_active=True)

        # Applicable holiday for all the members in the org
        if holidays.filter(org_location__isnull=True).exists():
            return True
        logging.info(f"No common holiday found")

        employee_org_location = employee.org_location
        if not employee_org_location:
            return False

        logging.info(f"employee_org_location : {employee_org_location},  is org loc active : {employee_org_location.status}")

        if (employee_org_location) and (employee_org_location.status == "active") and (holidays.filter(org_location=employee_org_location).exists()):
            return True
        logging.info(f"No Holiday found")

        return False
    
    def find_attendance_history_ids(self, attendance_computation_history, current_date):
        """
        Find ids for exclude. dates convert to org timezone and check wth current date. If
        its matches those ids will exclude
        """

        logging.info(f"attendance_computation_history: {attendance_computation_history}")
        logging.info(f"current_date: {current_date}")
        logging.info("find_attendance_history_ids started")

        attendance_history_ids = []
        for attendance_history in attendance_computation_history:
            attendance_history_created_at = attendance_history.created_at

            logging.info(f"attendance_history_created_at: {attendance_history_created_at}, shift: {attendance_history.shift}")

            converted_time_to_tz = tz.localtime(attendance_history_created_at, timezone=self.org_timezone)
            logging.info(f"converted_time_to_tz: {converted_time_to_tz}, shift: {attendance_history.shift}")

            logging.info(f"converted_time_to_tz.date(): {converted_time_to_tz.date()}, current_date: {current_date}")
            if converted_time_to_tz.date() == current_date:
                attendance_history_ids.append(attendance_history.id)
        
        logging.info("find_attendance_history_ids ended")
        return attendance_history_ids

    def handle(self, *args, **options):

        logging.info("")
        logging.info("")
        logging.info("")

        # get all organization objects
        # organizations = Organization.objects.values_list("id", flat=True)
        org_uuid = "0f402266-023a-4c7d-9f40-cd9703b84f46"
        organizations = Organization.objects.filter(uuid=org_uuid)

        # iterate each organization
        for organization in organizations:

            # For django health pkg
            organization.last_attendance_computed_at = curr_date_time_with_tz()
            organization.save()

            self.org_timezone = zoneinfo.ZoneInfo(organization.timezone if organization.timezone else "UTC")

            now = tz.localtime(tz.now(), timezone=self.org_timezone)
            logging.info(f"now: {now}")

            import datetime
            # date_string = "2024-04-06 7:00:00"
            date_string = "2024-04-08 23:15:00"
            date_time_obj = datetime.datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            now = tz.make_aware(date_time_obj, timezone=self.org_timezone)

            logging.info(f"date_string: {date_string}")
            logging.info(f"now: {now}")

            current_time = now.time()
            current_date = now.date()

            logging.info("-" * 50)
            logging.info(f"Date Time: {current_date} {current_time}")
            logging.info(f"Organization: {organization}")

            # print(connection.queries)

            # get all attendance computation history of current day
            # get only shift ids from the filtered queryset
            
            yesterday_date = current_date - tz.timedelta(days=1)
            logging.info(f"yesterday_date: {yesterday_date}")
            attendance_computation_history = AttendanceComputationHistory.objects.filter(
                Q(organization=organization) & Q(created_at__date__range=[yesterday_date, current_date])
            )

            logging.info(f"attendance_computation_history just filtered: {attendance_computation_history}")

            logging.info("")
            attendance_history_ids = self.find_attendance_history_ids(attendance_computation_history, current_date)
            logging.info(f"attendance_history_ids: {attendance_history_ids}")
            logging.info("")
            
            
            attendance_computation_history = attendance_computation_history.filter(
                id__in=attendance_history_ids
            ).values_list("shift_id", flat=True)

            print(attendance_computation_history)
            logging.info(f"attendance_computation_history after filtering: {attendance_computation_history}")
            logging.info(f"current_time.hour: {current_time.hour}")

            # Get shifts whose computation hour is less than or equal to current hour, also
            # those shifts should not be in attendance computation history objects of current day.
            shifts = Shift.objects.filter(
                # Q(status="active") &
                Q(organization=organization)
                & Q(computation_time__hour__lte=current_time.hour)
                & Q(uuid__in=["7591ee65-a7d8-4b64-a27c-1aadbd5013dc"])
            )

            logging.info(f"shifts: {shifts}")


            # print(connection.queries[-1])

            # iterate each shift
            for shift in shifts:
                print(f"shift name: {shift.name}")
                print(f"shift uuid: {shift.uuid}")
                logging.info(f"shift name: {shift.name}")
                logging.info(f"shift uuid: {shift.uuid}")
                logging.info(f"____________________________{shift.name}________________________________")

                print(len(connection.queries))

                # reset attendance computation history data
                self.attendance_computation_status = "started"
                self.employee_count = 0

                self.is_holiday = False

                # * create new attendance computation history object for the current shift
                # set status as started
                # set employee_count as zero
                self.attendance_computation_history_obj = AttendanceComputationHistory.objects.create(
                    shift=shift,
                    organization=organization,
                    status=self.attendance_computation_status,
                    employee_count=self.employee_count,
                    computation_started_at=now,
                )
                logging.info(f"{self.attendance_computation_history_obj}")

                # filter shift schedule logs by current shift and
                # current date should be within the start_date and end_date of ShiftScheduleLog
                shift_schedule_logs = ShiftScheduleLog.objects.filter(
                    Q(start_date__lte=current_date, end_date__gte=current_date)
                    | Q(start_date__lte=current_date, end_date=None),
                    organization=organization,
                    shift=shift,
                    status="active",
                )

                # print(shift_schedule_logs)

                # print(connection.queries)

                # night shift or shift start time > current time that means shift started at previous day
                # attendance_date = (
                #     current_date - tz.timedelta(days=1)
                #     if shift.start_time > shift.end_time or shift.start_time > current_time
                #     else current_date
                # )

                computation_time = shift.computation_time

                # curr_date_with_computation_time = tz.make_aware(
                #     tz.datetime.combine(current_date, computation_time),
                #     timezone=self.org_timezone,
                # )

                logging.info(f"computation_time.hour: {computation_time.hour}")
                logging.info(f"shift.start_time.hour: {shift.start_time.hour}")

                diff_in_start_comp_hour = computation_time.hour - shift.start_time.hour
                diff_in_end_comp_hour = computation_time.hour - shift.end_time.hour

                logging.info(f"diff_in_start_comp_hour: {diff_in_start_comp_hour}")
                logging.info(f"diff_in_end_comp_hour: {diff_in_end_comp_hour}")

                if diff_in_start_comp_hour < 0:
                    attendance_date = current_date - tz.timedelta(days=1)

                    self.actual_shift_start_dt = tz.make_aware(
                        tz.datetime.combine(attendance_date, shift.start_time),
                        timezone=self.org_timezone,
                    )

                elif diff_in_start_comp_hour > 0:
                    attendance_date = current_date

                    self.actual_shift_start_dt = tz.make_aware(
                        tz.datetime.combine(attendance_date, shift.start_time),
                        timezone=self.org_timezone,
                    )
                else:
                    logging.info("Value is 0")
                    logging.info(f"diff_in_start_comp_hour: {diff_in_start_comp_hour}")



                if diff_in_end_comp_hour < 0:
                    self.actual_shift_end_dt = tz.make_aware(
                        tz.datetime.combine(current_date - tz.timedelta(days=1), shift.end_time),
                        timezone=self.org_timezone,
                    )
                elif diff_in_end_comp_hour > 0:
                    self.actual_shift_end_dt = tz.make_aware(
                        tz.datetime.combine(current_date, shift.end_time),
                        timezone=self.org_timezone,
                    )
                else:
                    logging.info("Value is 0")
                    logging.info(f"diff_in_end_comp_hour: {diff_in_end_comp_hour}")

                logging.info(f"attendance_date: {attendance_date}")
                logging.info(f"self.actual_shift_start_dt: {self.actual_shift_start_dt}")
                logging.info(f"self.actual_shift_end_dt: {self.actual_shift_end_dt}")
                logging.info("")

                # shift computation_time
                computation_time = shift.computation_time

                # computation start date time (previous day Computation time)
                computation_start_date_time = tz.make_aware(
                    tz.datetime.combine(current_date - tz.timedelta(days=1), computation_time),
                    timezone=self.org_timezone,
                )

                # computation end date time (current day Computation time)
                computation_end_date_time = tz.make_aware(
                    tz.datetime.combine(current_date, computation_time), timezone=self.org_timezone
                )

                logging.info(f"computation_start_date_time: {computation_start_date_time}")
                logging.info(f"computation_end_date_time: {computation_end_date_time}")
                logging.info(f"computation_time: {computation_time}")

                # print(computation_start_date_time, computation_end_date_time)

                # *********************** CHECK HOLIDAY *********************************************************
                # check attendance date is holiday or not
                # self.is_holiday = self.check_holiday(organization, attendance_date, shift)

                # ************************************************************************************************

                # iterate each shift schedule logs
                for shift_schedule_log in shift_schedule_logs:

                    # print(connection.queries)

                    print(len(connection.queries))

                    # get employee of that shift schedule log
                    employee = shift_schedule_log.employee

                    if employee.status == "inactive":
                        continue

                    # *********************** CHECK HOLIDAY *********************************************************
                    self.is_holiday = self.is_have_holiday(organization, attendance_date, shift, employee)
                    # ************************************************************************************************

                    # get scans for an employee in chronological order
                    scans = employee.scans.filter(
                        Q(status="pending")
                        & Q(is_computed=False)
                        & Q(date_time__gte=computation_start_date_time)
                        & Q(date_time__lte=computation_end_date_time)
                    ).order_by("date_time")

                    # print(scans)

                    # self.scans_count = scans.count()
                    self.scans_count = len(scans)
                    logging.info(f"self.scans_count: {self.scans_count}")
                    logging.info(f"employee scans: {scans}")

                    # print(connection.queries[-1])
                    print(len(connection.queries))

                    try:

                        # If member scan count is more than zero, compute attendance
                        if self.scans_count > 0:
                            # create attendance object with
                            # other details (late check-in, early check-in, overtime, status) for the current employee
                            logging.info("First condition met. Scan found.")
                            self.add_attendance(organization, employee, attendance_date, scans, shift)

                        # mark attendance status as weekend
                        # if weekday is in skip days
                        elif attendance_date.weekday() in shift.skip_days:
                            print(len(connection.queries))
                            logging.info("Marking weekend (elif attendance_date.weekday() in shift.skip_days:)")
                            self.mark_attendance(organization, employee, attendance_date, "weekend", shift)

                        # mark attendance status as holiday
                        # if current day is holiday
                        elif self.is_holiday:
                            print(len(connection.queries))
                            logging.info("Marking holiday (elif self.is_holiday:)")
                            self.mark_attendance(organization, employee, attendance_date, "holiday", shift)

                        # If no scans, mark employee as absent
                        else:
                            print(len(connection.queries))
                            logging.info("Marking absent. else condition worked")
                            self.mark_attendance(organization, employee, attendance_date, "absent", shift)

                        # if attendance computation for this employee is successfull
                        # increment the employee count by one
                        self.employee_count += 1

                    except Exception as error:
                        logging.error(f"Error {error.__class__.__name__}: {error}")
                        # if the attendance computation is failed
                        # set the attendance computation history status as failed
                        self.attendance_computation_status = "failed"
                        print(len(connection.queries))

                # update attendance computation history object after current shift computation
                self.update_attendance_computation_history()
