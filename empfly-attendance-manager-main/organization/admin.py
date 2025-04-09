from django.contrib import admin 
from organization.models import (
    Organization,
    Designation,
    Department,
    CostCenter,
    Holiday,
    # Country,
    # State,
    # City,
    Role,
    OrgLocation,
    SystemLocation,
)
from django.db import models
from .forms import OrgAdmin


admin.site.register(Organization, OrgAdmin)
admin.site.register(OrgLocation)
admin.site.register(Designation)
admin.site.register(Department)
admin.site.register(CostCenter)
admin.site.register(Holiday)
admin.site.register(Role)
admin.site.register(SystemLocation)
