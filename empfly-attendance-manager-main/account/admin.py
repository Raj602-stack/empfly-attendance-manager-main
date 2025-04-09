from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from account.models import OTP, User, UserActivity, SessionToken, AuthToken


admin.site.register(User, UserAdmin)
# admin.site.register(User)
admin.site.register(UserActivity)
admin.site.register(SessionToken)
admin.site.register(AuthToken)
admin.site.register(OTP)
