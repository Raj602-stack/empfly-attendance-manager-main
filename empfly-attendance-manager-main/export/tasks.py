from celery import shared_task

from export.models import ExportRequest


import json
import logging

from .utils import (
    export_attendance_csv,
    export_attendance_register_csv,
    # export_cluster_csv,
    export_department_csv,
    export_designation_csv,
    export_fr_image_csv,
    export_holidays_csv,
    export_members_csv,
    export_system_location_csv,
    export_visitation_register_csv,
    export_visitations_csv,
    export_visitor_csv,
    update_export_request,
    export_shift_calendar_csv,
    member_curr_day_attendance_status_csv
)


logger = logging.getLogger(__name__)


@shared_task(name="export_requests_task")
def export_requests_task():
    export_requests = ExportRequest.objects.filter(status="pending")
    for export_request in export_requests:

        converted_data = json.loads(export_request.content)
        object_type = converted_data.get("object_type")
        object_ids = converted_data.get("object_ids")
        filters = export_request.filter

        export_csv_functions = {
            "system_locations": export_system_location_csv,
            "members": export_members_csv,
            "departments": export_department_csv,
            "designation": export_designation_csv,
            "visitor": export_visitor_csv,
            "attendance": export_attendance_csv,
            "visitations": export_visitations_csv,
            "visitation_register": export_visitation_register_csv,
            "attendance_register": export_attendance_register_csv,
            # "cluster": export_cluster_csv,
            "holidays": export_holidays_csv,
            "fr_image": export_fr_image_csv,
            "shift_calendar": export_shift_calendar_csv,
            "member_curr_day_attendance_status": member_curr_day_attendance_status_csv
        }

        export_csv_fun = export_csv_functions.get(object_type)

        if object_type == "shift_calendar" or object_type == "member_curr_day_attendance_status":
            filename = export_csv_fun(export_request, object_ids, filters)
        else:
            filename = export_csv_fun(export_request, object_ids)

        update_export_request(export_request, filename)

        # if object_type == "system_locations":
        #     filename =  export_system_location_csv(export_request, object_ids)

        # elif object_type == "members":
        #     filename =  export_members_csv(export_request, object_ids)

        # elif object_type == "departments":
        #     filename =  export_department_csv(export_request, object_ids)

        # elif object_type == "designation":
        #     filename =  export_designation_csv(export_request, object_ids)

        # elif object_type == "visitors":
        #     filename =  export_visitor_csv(export_request, object_ids)

        # elif object_type == "attendance":
        #     filename =  export_attendance_csv(export_request, object_ids)

        # elif object_type == "visitations":
        #     filename =  export_visitations_csv(export_request, object_ids)

        # elif object_type == "visitation_register":
        #     filename =  export_visitation_register_csv(export_request, object_ids)

        # elif object_type == "attendance_register":
        #     filename =  export_attendance_register_csv(export_request, object_ids)

        # elif object_type == "cluster":
        #     filename =  export_cluster_csv(export_request, object_ids)

        # elif object_type == "holidays":
        #     filename =  export_holidays_csv(export_request, object_ids)

