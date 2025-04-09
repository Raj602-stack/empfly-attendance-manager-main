# custom_tags.py
from django import template
import datetime as dt

from utils.utils import convert_to_time
register = template.Library()


@register.simple_tag
def current_time(format_string:str):
    """ Used in visitation email. For formate the time in template.
    """

    print(format_string, "%%%%%%%%%%%5", type(format_string))
    format_string = str(format_string)
    count = format_string.count(":")
    if count == 2:
        format_string = format_string.split(":")
        format_string.pop()
        format_string = ":".join(format_string)
    print(format_string, "time format_string ................")
    try:
        validtime = dt.datetime.strptime(format_string, "%H:%M").strftime("%I: %M %p")
        return validtime
    except ValueError:
        return ""
    