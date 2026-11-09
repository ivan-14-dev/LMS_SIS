from django.urls import re_path

from .access_views import AccessView, TeachingView
from .capabilities import LMSCapabilitiesView
from .views import AccountView

urlpatterns = [
    re_path(r"^capabilities/$", LMSCapabilitiesView.as_view(), name="capabilities"),
    re_path(r"^accounts/(?P<username>[\w-]{2,30})/$", AccountView.as_view(), name="account"),
    re_path(r"^courses/(?P<course_key>course-v1:[^/]+)/enrollments/(?P<username>[\w-]{2,30})/$", AccessView.as_view(), name="enrollment"),
    re_path(r"^courses/(?P<course_key>course-v1:[^/]+)/teaching/(?P<username>[\w-]{2,30})/$", TeachingView.as_view(), name="teaching"),
]
