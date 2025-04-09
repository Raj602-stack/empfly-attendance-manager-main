from datetime import date, datetime, timedelta
from typing import Union
from utils.utils import convert_to_date, convert_to_time

# from utils.shift import find_ids_effected
from .models import Shift, ShiftScheduleLog
import utils.shift
from member.models import Member
from export.utils import extract_data_from_object
from utils import date_time

import logging
# configure logging
logging.basicConfig(
    filename="logs/shift_schedule_logic.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
)



def ids_become_inactive(logs: ShiftScheduleLog, starting_id: int) -> None:
    """ When a new SSL is created some of them will deactivated. For find
        the ids we will use this.
    """
    is_effected, effected_ids = False, []

    for i in logs:
        if i.id == starting_id:
            is_effected = True

        if is_effected:
            effected_ids.append(i.id)

    return effected_ids


def create_log_mapping(
    shift: Shift,
    employee: Member,
    start_date: datetime,
    end_date: Union[datetime, None],
) -> None:
    """ Modify SSL. Create new SSL.

        Algorithm
        BDA (Before, During, After)
        When a SSL(Shift schedule Log) split happen Another SSL will create.

        ex:
            current shift schedule log
            DATE                         shift
            ==================================
            01-12-2022 - 04-12-2022         A
            05-12-2022 - 15-12-2022         B
            15-12-2022 - None               C

        if Admin have to assign shift C from 07 to 10. (05-12-2022 - 15-12-2022) this rec will split in BDA format.
            DATE                         shift
            ==================================
            01-12-2022 - 04-12-2022         A
            05-12-2022 - 06-12-2022         B  -> Before
            07-12-2022 - 10-12-2022         C  -> During
            11-12-2022 - 15-12-2022         B  -> After
            15-12-2022 - None               C
        
        (05-12-2022 - 15-12-2022) this old records become inactive
    """


    logging.info("================== create_log_mapping function started ==================")
    # TODO Check
    organization = employee.organization
    logging.info(f"====== organization : {organization} =======")

    today_date = date_time.today_date()
    logging.info(f"===== Today date with org tz : {today_date} ===========")

    # Checking the start date is valid or not.
    if start_date and end_date and start_date > end_date:
        logging.error(f"====== start_date : {start_date}, end_date: {end_date} start date greater than end date =======")
        return

    if start_date < today_date and start_date is None:
        logging.error(f"====== start_date : {start_date}, today_date: {today_date} start date greater than today =======")
        return

    if start_date < today_date:
        start_date = today_date
        if start_date and start_date > end_date:
            return

    employee_logs = ShiftScheduleLog.objects.filter(
        status="active", employee=employee, organization=organization
    ).order_by("start_date")

    if employee_logs.exists() is False:
        return

    print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", employee_logs)

    if not end_date:
        logging.info(f"====== No end date first condition met =======")

        # check start date is in between of some log.
        logs = employee_logs.filter(
            start_date__lte=start_date, end_date__gte=start_date
        )

        # start date must be in between of something. Find the log.
        if logs.count() == 1:
            log = logs.get()
            logging.info(f"========= Prent log : {log} ==========")
            # starting_id = logs.get().id
            # ids = ids_become_inactive(employee_logs.order_by("start_date"), starting_id)

            # if no end date all the records after the start date become inactive
            logs_become_inactive = employee_logs.filter(start_date__gte=log.start_date).values_list("id", flat=True)
            logs_become_inactive = list(logs_become_inactive)
            logging.info(f"========= Logs become inactive : {logs_become_inactive} ==========")

            #  Check for past SSL
            if log.start_date == start_date:
                # if start date is equal to log start date there are no past records. What we have only is during
                logging.info(f"============ No before {log.start_date}, start date: {start_date}")
                # no before
                before_start_date = None
                before_end_date = None
                before_shift = None

            elif log.start_date < start_date:
                # have before
                # Have past records. Past records cannot editable.
                before_start_date = log.start_date
                before_end_date = start_date - timedelta(days=1)
                before_shift = log.shift
                is_before_log_is_shift_mapping = log.is_esm
                logging.info(f"============ Have before {log.start_date}, start date: {start_date}, before_shift: {before_shift}")

            # after and during is same is if end date is specified

            during_start_date = start_date
            during_end_date = end_date
            during_shift = shift
            logging.info(f"============ During strt date {during_start_date}, end date: {during_end_date}, during_shift: {during_shift}")

            # Create Log if any past records found.
            if before_start_date and before_end_date:
                ShiftScheduleLog.objects.create(
                    employee=employee,
                    shift=before_shift,
                    start_date=before_start_date,
                    end_date=before_end_date,
                    is_esm=is_before_log_is_shift_mapping,
                    organization=organization,
                )
                logging.info("============= created brofore ============")

            # Current SSL.
            ShiftScheduleLog.objects.create(
                employee=employee,
                shift=during_shift,
                start_date=during_start_date,
                end_date=during_end_date,
                is_esm=True,
                organization=organization,
            )
            logging.info("============= created during. During and after is same ============")

            employee_logs.filter(id__in=logs_become_inactive).update(status="inactive")
            logging.info("============= Deactivated employees ============")

            return

        # checking start date is the last entry.
        # logs = employee_logs.filter(start_date__lte=start_date, end_date=None)
        logs = employee_logs.filter(start_date__lte=start_date, end_date__isnull=True)

        logging.info(f"====== Second condition met  log: {logs}=======")

        if logs.count() == 1:
            logging.info(f"====== Log is the end one have no end date =======")
            log = logs.get()
            if not start_date >= log.start_date:
                return

            # find B, D
            if log.start_date == start_date:
                # no before
                before_start_date = None
                before_end_date = None
                before_shift = None
            elif log.start_date < start_date:
                # have before
                before_start_date = log.start_date
                before_end_date = start_date - timedelta(days=1)
                before_shift = log.shift
                is_before_log_is_shift_mapping = log.is_esm

            during_start_date = start_date
            during_end_date = end_date
            during_shift = shift

            if before_start_date and before_end_date:
                ShiftScheduleLog.objects.create(
                    employee=employee,
                    shift=before_shift,
                    start_date=before_start_date,
                    end_date=before_end_date,
                    is_esm=is_before_log_is_shift_mapping,
                    organization=organization,
                )

            ShiftScheduleLog.objects.create(
                employee=employee,
                shift=during_shift,
                start_date=during_start_date,
                end_date=during_end_date,
                is_esm=True,
                organization=organization,
            )
            log.status = "inactive"
            log.save()
            return

    elif start_date and end_date:
        # If start date and end date is get from frontend
        # case One
        # check the start date and end date is in between of a log.

        logging.info(f"================ start_date: {start_date} , end_date: {end_date} ===============")

        # If start date and end date found in same SSl
        in_between = employee_logs.filter(
            start_date__lte=start_date, end_date__gte=end_date
        )

        if in_between.count() == 1:
            logging.info(f"======= in between log founded {in_between} =========")
            in_between = in_between.first()
            head_start_date = in_between.start_date
            head_end_date = in_between.end_date

            # Check for before
            if start_date == head_start_date:
                # no before
                before_start_date = None
                before_end_date = None
                before_shift = None
            elif start_date > head_start_date:
                # have before
                before_start_date = head_start_date
                before_end_date = start_date - timedelta(days=1)
                before_shift = in_between.shift
                is_before_log_is_shift_mapping = in_between.is_esm

            # Check for after
            if end_date == head_end_date:
                # no after
                after_start_date = None
                after_end_date = None
                after_shift = None
            elif end_date < head_end_date:
                # have after
                after_start_date = end_date + timedelta(days=1)
                after_end_date = head_end_date
                after_shift = in_between.shift
                is_after_log_is_shift_mapping = in_between.is_esm

            if before_start_date and before_end_date:
                ShiftScheduleLog.objects.create(
                    shift=before_shift,
                    employee=employee,
                    start_date=before_start_date,
                    end_date=before_end_date,
                    is_esm=is_before_log_is_shift_mapping,
                    organization=organization,
                )

            ShiftScheduleLog.objects.create(
                shift=shift,
                employee=employee,
                start_date=start_date,
                end_date=end_date,
                is_esm=True,
                organization=organization,
            )

            if after_start_date and after_end_date:
                ShiftScheduleLog.objects.create(
                    shift=after_shift,
                    employee=employee,
                    start_date=after_start_date,
                    end_date=after_end_date,
                    is_esm=is_after_log_is_shift_mapping,
                    organization=organization,
                )

            in_between.status = "inactive"
            in_between.save()

            return

        # case Two
        # There must be only one log with end_date with None and active status
        print(employee_logs, "000000000000000000")

        # ex:
        #   start, end date = 10-10-2022, 20-10-2022
        #   Log 01-10-2022 - Null
        log_with_no_end = employee_logs.filter(end_date__isnull=True)


        if (
            log_with_no_end.count() == 1
            and start_date >= log_with_no_end.first().start_date
        ):
            logging.info("================ log with no end date is the head ===========")
            logging.info(f"================  head : {log_with_no_end} ===========")
            head = log_with_no_end.first()
            head_start_date = head.start_date
            head_end_date = head.end_date

            if start_date == head_start_date:
                # no before
                before_start_date = None
                before_end_date = None
                before_shift = None
            elif start_date > head_start_date:
                # have before
                before_start_date = head_start_date
                before_end_date = start_date - timedelta(days=1)
                before_shift = head.shift
                is_before_log_is_shift_mapping = head.is_esm

            during_start_date = start_date
            during_end_date = end_date

            if end_date:
                # have after
                after_start_date = end_date + timedelta(days=1)
                after_end_date = None
                after_shift = head.shift
                is_after_log_is_shift_mapping = head.is_esm

            if before_start_date and before_end_date:
                ShiftScheduleLog.objects.create(
                    shift=before_shift,
                    employee=employee,
                    start_date=before_start_date,
                    end_date=before_end_date,
                    is_esm=is_before_log_is_shift_mapping,
                    organization=organization,
                )

            ShiftScheduleLog.objects.create(
                shift=shift,
                employee=employee,
                start_date=during_start_date,
                end_date=during_end_date,
                is_esm=True,
                organization=organization,
            )

            if after_start_date:
                ShiftScheduleLog.objects.create(
                    shift=after_shift,
                    employee=employee,
                    start_date=after_start_date,
                    end_date=after_end_date,
                    is_esm=is_after_log_is_shift_mapping,
                    organization=organization,
                )

            head.status = "inactive"
            head.save()

            return

        print(end_date, "---------end data  case 3 ^^^^^^^^^6666")

        # case Three
        # if start and end date both are in between of different logs.
        # Ex:
        #   start, end date = 10-10-2022, 20-10-2022
        #   ============= SSL =============
        #   05-10-2022 - 15-10-2022
        #   16-10-2022 - 26-10-2022
        head = employee_logs.filter(
            start_date__lte=start_date, end_date__gte=start_date
        )
        tail = employee_logs.filter(start_date__lte=end_date, end_date__gte=end_date)

        if head.count() == 1:
            head = head.first()

        if tail.count() == 1:
            tail = tail.first()
        elif tail.count() == 0:
            print("+++++++++++++++++++++++++++++++++++++++++++++++++", end_date)
            if end_date >= log_with_no_end.first().start_date:
                tail = log_with_no_end.first()

        effected_ids = utils.shift.find_ids_effected(
            employee_logs.order_by("start_date"), head_id=head.id, tail_id=tail.id
        )

        effected_logs = employee_logs.filter(id__in=effected_ids).order_by("start_date")

        # find B, D, A
        head_start_date = head.start_date
        head_end_date = head.end_date

        tail_start_date = tail.start_date
        tail_end_date = tail.end_date

        if start_date == head_start_date:
            # no before
            before_start_date = None
            before_end_date = None
            before_shift = None
        elif start_date > head_start_date:
            # have before
            before_start_date = head_start_date
            before_end_date = start_date - timedelta(days=1)
            before_shift = head.shift
            is_before_log_is_shift_mapping = head.is_esm

        during_start_date = start_date
        during_end_date = end_date  # if shift have no end date during and after is same

        if end_date == tail_end_date:
            # no after
            after_start_date = None
            after_end_date = None
            after_shift = None

        elif tail_end_date is None:
            # have after
            after_start_date = during_end_date + timedelta(days=1)
            after_end_date = None
            after_shift = tail.shift
            is_after_log_is_shift_mapping = tail.is_esm

        elif end_date < tail_end_date:
            # have after
            after_start_date = during_end_date + timedelta(days=1)
            after_end_date = tail_end_date
            after_shift = tail.shift
            is_after_log_is_shift_mapping = tail.is_esm

        if before_start_date and before_end_date:
            ShiftScheduleLog.objects.create(
                shift=before_shift,
                employee=employee,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=is_before_log_is_shift_mapping,
                organization=organization,
            )

        ShiftScheduleLog.objects.create(
            shift=shift,
            employee=employee,
            start_date=during_start_date,
            end_date=during_end_date,
            is_esm=True,
            organization=organization,
        )

        if after_start_date:
            ShiftScheduleLog.objects.create(
                shift=after_shift,
                employee=employee,
                start_date=after_start_date,
                end_date=after_end_date,
                is_esm=is_after_log_is_shift_mapping,
                organization=organization,
            )

        effected_logs.update(status="inactive")

        return


def create_log_for_shift(shift: Shift, employee: Member) -> None:
    """ Changes member shift in priority analysis.
    """
    logging.info("======================== create_log_for_shift function started ======================")
    # TODO check
    start_date = date_time.today_date()
    logging.info(f"=================== start date with org timezone: {start_date} ===================")
    logging.info(f"=================== employee : {employee} ===================")
    logging.info(f"=================== shift : {shift} ===================")


    organization = employee.organization

    employee_logs = ShiftScheduleLog.objects.filter(
        employee=employee, status="active", organization=organization
    ).order_by("start_date")

    # find in between
    logs = employee_logs.filter(start_date__lte=start_date, end_date__gte=start_date)

    if logs.count() == 1:
        exclude_ids = []
        log = logs.get()

        if log.start_date == start_date:
            # no before
            before_start_date = None
            before_end_date = None
            before_shift = None
            is_before_log_is_shift_mapping = None

        elif start_date > log.start_date:
            # have before
            before_start_date = log.start_date
            before_end_date = start_date - timedelta(days=1)
            before_shift = log.shift
            is_before_log_is_shift_mapping = log.is_esm

        if (
            before_start_date
            and before_end_date
            and is_before_log_is_shift_mapping is False
        ):
            before = ShiftScheduleLog.objects.create(
                employee=employee,
                shift=before_shift,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=is_before_log_is_shift_mapping,
                organization=organization,
            )

            exclude_ids.append(before.id)

        if log.end_date:
            # have after
            after_start_date = start_date
            after_end_date = log.end_date
            after_shift = shift
            is_after_log_is_shift_mapping = False

        if after_start_date and after_end_date and log.is_esm is False:
            after = ShiftScheduleLog.objects.create(
                employee=employee,
                shift=after_shift,
                start_date=after_start_date,
                end_date=after_end_date,
                is_esm=is_after_log_is_shift_mapping,
                organization=organization,
            )
            exclude_ids.append(after.id)

        current_id = log.id

        employee_logs = employee_logs.order_by("start_date").exclude(id__in=exclude_ids)

        is_found_id = False
        during_shift = shift

        for i in employee_logs:
            if i.id == current_id:
                is_found_id = True
                continue

            if is_found_id is False or i.is_esm is True:
                continue

            employee = i.employee
            during_start_date = i.start_date
            during_end_date = i.end_date

            ShiftScheduleLog.objects.create(
                employee=employee,
                shift=during_shift,
                start_date=during_start_date,
                end_date=during_end_date,
                is_esm=False,
                organization=organization,
            )

            i.status = "inactive"
            i.save()

        if log.is_esm is False:
            log.status = "inactive"
            log.save()

        return

    # log with no end
    logs = employee_logs.filter(start_date__lte=start_date, end_date=None)

    if logs.count() == 1 and start_date >= logs.first().start_date:
        log = logs.get()

        if log.is_esm is True:
            return

        if log.start_date == start_date:
            # no before
            before_start_date = None
            before_end_date = None
            before_shift = None

        elif log.start_date < start_date:
            # have before
            before_start_date = log.start_date
            before_end_date = start_date - timedelta(days=1)
            before_shift = log.shift
            is_before_log_is_shift_mapping = log.is_esm

        # after and during is same is not end date is specified

        if (
            before_start_date
            and before_end_date
            and is_before_log_is_shift_mapping is False
        ):
            ShiftScheduleLog.objects.create(
                employee=employee,
                shift=before_shift,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=is_before_log_is_shift_mapping,
                organization=organization,
            )

        ShiftScheduleLog.objects.create(
            employee=employee,
            shift=shift,
            start_date=start_date,
            end_date=None,
            is_esm=False,
            organization=organization,
        )

        log.status = "inactive"
        log.save()
        return


def priority_analysis(employee: Member) -> Shift:
    """ Extract shift from priority analysis. 
        department, designation, org location have shift FK
        using priority analysis we can get the shift for member. 
    """
    org = employee.organization

    priority = org.settings["applicability_settings_priority"]

    arr = [0, 0, 0]

    for i in priority:
        posi = i["priority"]
        arr[posi - 1] = i["name"]

    get_priority = {
        "department": ["department", "shift"],
        "designation": ["designation", "shift"],
        "org_location": ["org_location", "shift"],
    }

    for priority in arr:
        shift = extract_data_from_object(employee, get_priority.get(priority))

        if isinstance(shift, Shift) is True and shift.status == "active":
            return shift

# TODO deprecated
def create_log_for_deactivate(shift: Shift, employee: Member, alternative_shift):
    start_date = date_time.today_date() + timedelta(days=1)

    organization = employee.organization

    employee_logs = ShiftScheduleLog.objects.filter(
        employee=employee, status="active", shift=shift, organization=organization
    ).order_by("start_date")

    # find in between
    logs = employee_logs.filter(start_date__lte=start_date, end_date__gte=start_date)

    if logs.count() == 1:
        exclude_ids = []
        log = logs.get()

        if log.start_date == start_date:
            # no before
            before_start_date = None
            before_end_date = None
            before_shift = None
            is_before_log_is_shift_mapping = None

        elif start_date > log.start_date:
            # have before
            before_start_date = log.start_date
            before_end_date = start_date - timedelta(days=1)
            before_shift = log.shift
            is_before_log_is_shift_mapping = log.is_esm

        if before_start_date and before_end_date:
            before = ShiftScheduleLog.objects.create(
                employee=employee,
                shift=before_shift,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=is_before_log_is_shift_mapping,
                organization=organization,
            )

            exclude_ids.append(before.id)

        if log.end_date:
            # have after
            after_start_date = start_date
            after_end_date = log.end_date
            after_shift = alternative_shift
            is_after_log_is_shift_mapping = False

        if (
            after_start_date
            and after_end_date
            # and log.is_esm is False
        ):
            after = ShiftScheduleLog.objects.create(
                employee=employee,
                shift=after_shift,
                start_date=after_start_date,
                end_date=after_end_date,
                is_esm=log.is_esm,
                organization=organization,
            )
            exclude_ids.append(after.id)

        log.status = "inactive"
        log.save()

        return after_start_date

    # log with no end
    logs = employee_logs.filter(start_date__lte=start_date, end_date=None)

    if logs.count() == 1 and start_date >= logs.first().start_date:
        log = logs.get()

        # if log.is_esm is True:
        #     return

        if log.start_date == start_date:
            # no before
            before_start_date = None
            before_end_date = None
            before_shift = None

        elif log.start_date < start_date:
            # have before
            before_start_date = log.start_date
            before_end_date = start_date - timedelta(days=1)
            before_shift = log.shift
            is_before_log_is_shift_mapping = log.is_esm

        # after and during is same is not end date is specifed

        if (
            before_start_date
            and before_end_date
            # and is_before_log_is_shift_mapping is False
        ):
            ShiftScheduleLog.objects.create(
                employee=employee,
                shift=before_shift,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=is_before_log_is_shift_mapping,
                organization=organization,
            )

        ShiftScheduleLog.objects.create(
            employee=employee,
            shift=shift,
            start_date=start_date,
            end_date=None,
            is_esm=False,
            organization=organization,
        )

        log.status = "inactive"
        log.save()
        return start_date


def time_of_shift(shift: Shift):
    start_time = shift.start_time
    end_time = shift.end_time
    if start_time > end_time:
        # night shift
        return
    return


def deactivate_shift(
    shift: Shift, employee: Member, alternative_shift, start_date=date_time.today_date()
):

    prev_shift_start_time = shift.start_time
    prev_shift_end_time = shift.end_time
    prev_computation_time = shift.computation_time
    # start_date = date.today()

    print(prev_shift_start_time)
    print(prev_computation_time)

    # now = datetime.now().time()
    # TODO Check
    now = date_time.curr_time()

    mid_night_time = convert_to_time("00:00:00")[0]
    today_date = date_time.today_date()

    if prev_shift_start_time > prev_computation_time:  # night shift
        if  (now >= prev_shift_start_time and now <= mid_night_time) or (
            now >= mid_night_time and now <= prev_computation_time
        ):
            start_date = today_date
        else:
            start_date = today_date + timedelta(days=1)
    elif prev_shift_start_time <= prev_computation_time:  # normal day shift
        start_date = today_date + timedelta(days=1)

    print(">>>>>>>>>>>>>>>>>>>>>", start_date, ">>>>>>>>>>>>>>>>>>>>>")
    organization = employee.organization

    employee_logs = ShiftScheduleLog.objects.filter(
        employee=employee, status="active", shift=shift, organization=organization
    ).order_by("start_date")

    # check shift is normal or night
    # find in between
    logs = employee_logs.filter(start_date__lte=start_date, end_date__gte=start_date)
    print("###################################" * 4)
    print(start_date, "$$$$$ start date")
    print(logs)
    if logs.count() == 1:
        log = logs.get()

        # find before and after

        if start_date == log.start_date:
            # no before only after
            before_shift = None
            before_start_date = None
            before_end_date = None
            before_esm = None
        elif log.start_date < start_date:
            # have before
            before_shift = log.shift
            before_start_date = log.start_date
            before_end_date = start_date - timedelta(days=1)
            before_esm = log.is_esm

        # find after
        after_start_date = start_date
        after_end_date = log.end_date
        after_shift = alternative_shift

        if before_start_date and before_end_date:
            before = ShiftScheduleLog.objects.create(
                employee=employee,
                shift=before_shift,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=before_esm,
                organization=organization,
            )
        after = ShiftScheduleLog.objects.create(
            employee=employee,
            shift=after_shift,
            start_date=after_start_date,
            end_date=after_end_date,
            organization=organization,
        )

        log.status = "inactive"
        log.save()
        return after.start_date

    # find with null end
    logs = employee_logs.filter(start_date__lte=start_date, end_date__isnull=True)
    print("###################################" * 4)
    print(start_date, "$$$$$ start date")
    print(logs)
    if logs.count() == 1 and start_date >= logs.first().start_date:
        log = logs.get()

        # find before and after

        if start_date == log.start_date:
            # no before only after
            before_shift = None
            before_start_date = None
            before_end_date = None
            before_esm = None
        elif log.start_date < start_date:
            # have before
            before_shift = log.shift
            before_start_date = log.start_date
            before_end_date = start_date - timedelta(days=1)
            before_esm = log.is_esm

        # find after
        after_start_date = start_date
        after_end_date = log.end_date
        after_shift = alternative_shift

        if before_start_date and before_end_date:
            before = ShiftScheduleLog.objects.create(
                employee=employee,
                shift=before_shift,
                start_date=before_start_date,
                end_date=before_end_date,
                is_esm=before_esm,
                organization=organization,
            )
        after = ShiftScheduleLog.objects.create(
            employee=employee,
            shift=after_shift,
            start_date=after_start_date,
            end_date=after_end_date,
            organization=organization,
        )

        log.status = "inactive"
        log.save()
        return after.start_date

    return start_date