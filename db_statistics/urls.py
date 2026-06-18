from django.urls import path

from . import views

urlpatterns = [path("", views.home, name="home"), path("connections/new/", views.create_connection, name="create_connection"), path("connections/<int:pk>/", views.connection_detail, name="connection_detail")]
