from django.urls import path

from apps.projects.views import (
    ProjectDetailView,
    ProjectListCreateView,
    ProjectMemberDetailView,
    ProjectMemberListCreateView,
)

urlpatterns = [
    path("projects/", ProjectListCreateView.as_view(), name="project-list-create"),
    path("projects/<uuid:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path(
        "projects/<uuid:project_pk>/members/",
        ProjectMemberListCreateView.as_view(),
        name="project-member-list-create",
    ),
    path(
        "projects/<uuid:project_pk>/members/<uuid:membership_pk>/",
        ProjectMemberDetailView.as_view(),
        name="project-member-detail",
    ),
]
