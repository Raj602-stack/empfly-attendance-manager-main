import zoneinfo

from django.utils import timezone
from account.authentication import TokenAuthentication


class TimezoneMiddleware:
    """ Any date time is sending to frontend that must be converted to users org tz.
        This middleware get user org tz. So in the response all the date time will
        convert to member org tz.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def get_request_user(self, request):
        """
        Function used to get user from request
        if request has token in request header using that we can take user
        else we can take session authentication request.user as user
        """
        try:
            return TokenAuthentication().authenticate(request)[0]
        except Exception as error:
            print(error)
            print("!!!!!!!!!!!! authentication for mobile !!!!!!!!!!!!")
            return request.user

    def __call__(self, request):
        print("############################# tz middleware started #############################")

        # tzname = request.session.get("django_timezone", "UTC")
        user = self.get_request_user(request)

        print("Current User : ", user)

        tzname = "UTC"
        member = user.members.first() if user.is_authenticated else None
        if member:
            tzname = member.organization.timezone
            print("member org tz : ", tzname)
            tzname = tzname if tzname else "UTC"
            print("final tz of member : ", tzname)
        print("final tz : ", tzname)

        # tzname = "Asia/Kolkata"
        print(tzname)
        if tzname:
            timezone.activate(zoneinfo.ZoneInfo(tzname))
        else:
            timezone.deactivate()

        print()
        
        return self.get_response(request)
