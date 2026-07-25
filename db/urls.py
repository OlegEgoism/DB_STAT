from django.contrib import admin
from django.urls import include, path

handler404 = "db_statistics.views.page_not_found"

urlpatterns = [path("admin/", admin.site.urls), path("", include("db_statistics.urls"))]
