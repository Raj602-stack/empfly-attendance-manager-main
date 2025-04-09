from env import HEALTH_CHECK_AUTH_TOKEN
import json
from django.http import JsonResponse
from rest_framework.renderers import JSONRenderer
from health_check.views import MainView
from attendance.models import Attendance, AttendanceComputationHistory
from utils.date_time import curr_date_time_with_tz
from organization.models import Organization
from django.db.models import Max



class CustomHealthCheckView(MainView):
    def get(self, request, *args, **kwargs):
        # Add any additional logic or customization here
    
        if "HTTP_X_HEALTH_CHECK_AUTH_TOKEN" not in request.META:
            renderer = JSONRenderer()
            response = renderer.render({'message': 'Authentication credentials were not provided.'}, renderer_context={'request': request})
            return JsonResponse(json.loads(response), status=401)

        health_check_token_in_request = request.META["HTTP_X_HEALTH_CHECK_AUTH_TOKEN"]

        if health_check_token_in_request != HEALTH_CHECK_AUTH_TOKEN:
            renderer = JSONRenderer()
            response = renderer.render({'message': 'Authentication credentials were not provided.'}, renderer_context={'request': request})
            return JsonResponse(json.loads(response), status=401)

        default_response = super().get(request, *args, **kwargs)
        default_data = default_response.content.decode('utf-8')
        default_data_dict = json.loads(default_data)


        org = Organization.objects.aggregate(max_computed_dt=Max("last_attendance_computed_at"))
        max_computed_dt = org["max_computed_dt"]

        if not max_computed_dt:
            default_data_dict.update({"AttendanceComputation": "working"})
            # return JsonResponse(default_data_dict, safe=False)
        else:
            curr_time = curr_date_time_with_tz()

            diff = (curr_time - max_computed_dt).total_seconds() // 60

            if diff <= 70:
                default_data_dict.update({"AttendanceComputation": "working"})
                # return JsonResponse(default_data_dict, safe=False)
            else:
                default_data_dict.update({"AttendanceComputation": f"Not working. Last attendance is computed at {max_computed_dt}."})

        for _ , curr_status in default_data_dict.items():
            if curr_status == "working":
                continue
            # If some service is not working throw 500 error.
            return JsonResponse(default_data_dict, safe=False, status=500)

        return JsonResponse(default_data_dict, safe=False)
