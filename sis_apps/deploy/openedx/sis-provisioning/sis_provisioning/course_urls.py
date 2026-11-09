from django.urls import re_path

from .capabilities import CMSCapabilitiesView
from .course_views import CourseView
from .publication_views import PublicationView

urlpatterns = [
    re_path(r"^capabilities/$", CMSCapabilitiesView.as_view(), name="capabilities"),
    re_path(r"^courses/(?P<course_key>course-v1:[^/]+)/$", CourseView.as_view(), name="course"),
    re_path(r"^courses/(?P<course_key>course-v1:[^/]+)/publication/$", PublicationView.as_view(), name="publication"),
]
