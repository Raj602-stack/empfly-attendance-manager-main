from django.contrib import admin

from member.models import Member, MemberImage, Profile

admin.site.register(Member)
admin.site.register(MemberImage)
admin.site.register(Profile)