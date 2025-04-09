from django.contrib import admin
from visitor.models import Visitor, VisitorScan, Visitation

# Register your models here.

admin.site.register(Visitor)
# admin.site.register(VisitorImage)
admin.site.register(VisitorScan)
admin.site.register(Visitation)
