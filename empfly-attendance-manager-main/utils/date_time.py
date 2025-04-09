from datetime import datetime, timedelta
import pytz
from django.utils import timezone
from dateutil import tz
import math
# Get date with tz config in middleware
# By the time of req in the middleware we wil get the user org tz. And get the time according to tz only

# Current time in UTC
temp_date_time = datetime.strptime("05/10/09 00:00:00", "%d/%m/%y %H:%M:%S")
day_start_time = temp_date_time.time()
day_end_time = (temp_date_time - timedelta(microseconds=1)).time()

def curr_date_time_with_tz(tzone="UTC"):
    return datetime.now(pytz.timezone(tzone))

def curr_dt_with_org_tz():
    """ In tz middle ware we ware set the user org tz.
        When we use timezone.localtime() we will get time according to 
        user org tz.
    """
    return timezone.localtime()

def today_date():
    """ Get date user org tz.
    """
    return timezone.localdate()

def curr_time():
    """ get time with user org tz
    """
    return timezone.localtime().time()


def convert_dt_to_another_tz(dt_for_convert: datetime, to_zone : str = 'Asia/Kolkata'):
    """Convert a datetime to diff datetime or tz.

    Args:
        dt_for_convert (datetime): _description_
        to_zone (str, optional): _description_. Defaults to 'Asia/Kolkata'.

    Returns:
        _type_: _description_
    """

    if not dt_for_convert:
        return dt_for_convert

    try:
        to_zone = tz.gettz(to_zone)
        print(f"to_zone: {to_zone}")

        print(f"dt_for_convert tz: {dt_for_convert.astimezone().tzinfo}")

        converted_dt = dt_for_convert.astimezone(to_zone)
        print(f"converted_dt: {converted_dt}")
        print(f"dt_for_convert tz: {converted_dt.astimezone().tzinfo}")
        return converted_dt
    except Exception as err:
        print(err)
        return dt_for_convert


def str_to_int(num: str) -> int:
    """Convert number in str to int.

    Args:
        num (str): string number

    Returns:
        int: number
    """
    if isinstance(num, int):
        return num

    return int(num)

def min_to_hm(minutes: int) -> timedelta:
    """Convert minutes to H:M
    """
    if minutes is None:
        return minutes

    try:
        minutes = str_to_int(minutes)
        hours = minutes // 60
        minutes = minutes % 60

        if hours < 9 and hours >= 0:
            hours = f"0{hours}"
        
        if minutes < 9 and minutes >= 0:
            minutes = f"0{minutes}"

        return f"{hours}:{minutes}"

    except Exception as err:
        print(err)
        print("Error occurred in min_to_hm")
        return minutes

def chop_decimal_point(minutes: int) -> int:
    """Remove decimal point from minutes. Minutes can be string

    Args:
        minutes (int): _description_

    Returns:
        _type_: int
    """
    if minutes is None:
        return minutes
    try:
        minutes = str_to_int(minutes)

        # (0.5678000000000338, 1234.0)
        return math.modf(minutes)[1]
    except Exception as err:
        print(err)
        print("Error occurred in chop_decimal_point")
        return minutes

def NA_or_time(td_time):
    """If time if 00:00:00 return NA or return td_time

    Args:
        td_time (timedelta): timedelta object.

    Returns:
        _type_: it an be na if td_time is 00:00:00 else return the time.
    """

    if td_time in ("00:00", "00:00:00", None):
        return "NA"
    return td_time
    # if isinstance(td_time, timedelta) is False:
    #     return td_time

    # return "NA" if td_time.total_seconds() == 0 else td_time
