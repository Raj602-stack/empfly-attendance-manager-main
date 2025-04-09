from django.contrib import admin
from django.urls import path, include
from . import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from account.views import helath_check_view

urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/", include("api.urls")),

    path('api/health-check/3lFKuiwfuesGdAMOmADlSEdYK_V2oLCpF8yUARzLyGM/', helath_check_view.CustomHealthCheckView.as_view()),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
