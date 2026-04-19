from django.urls import path

from apps.projects.views import (
    ProjectArchiveView,
    ProjectDetailView,
    ProjectListCreateView,
    ProjectMemberDetailView,
    ProjectMemberListCreateView,
    ProjectRestoreView,
)
from apps.projects.views_tree import ProjectTreeView

urlpatterns = [
    path("projects/", ProjectListCreateView.as_view(), name="project-list-create"),
    path("projects/<uuid:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path("projects/<uuid:pk>/tree/", ProjectTreeView.as_view(), name="project-tree"),
    path("projects/<uuid:pk>/archive/", ProjectArchiveView.as_view(), name="project-archive"),
    path("projects/<uuid:pk>/restore/", ProjectRestoreView.as_view(), name="project-restore"),
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
