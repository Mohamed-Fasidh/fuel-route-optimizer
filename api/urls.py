from django.urls import path
from .views import HealthView, RoutePlanView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("route-plan/", RoutePlanView.as_view(), name="route-plan"),
]
