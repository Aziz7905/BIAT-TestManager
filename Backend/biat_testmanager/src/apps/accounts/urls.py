from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import (
    AdminUserDetailView,
    AdminUserListCreateView,
    ChangeMyPasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
    MyProfileView,
    OrganizationDetailView,
    OrganizationListCreateView,
    TeamDetailView,
    TeamListCreateView,
    TeamMemberDetailView,
    TeamMemberListCreateView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="me"),
    path("admin/users/", AdminUserListCreateView.as_view(), name="admin-user-list-create"),
    path("admin/users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("organizations/", OrganizationListCreateView.as_view(), name="organization-list-create"),
    path("organizations/<uuid:pk>/", OrganizationDetailView.as_view(), name="organization-detail"),
    path("teams/", TeamListCreateView.as_view(), name="team-list-create"),
    path("teams/<uuid:pk>/", TeamDetailView.as_view(), name="team-detail"),
    path("teams/<uuid:team_pk>/members/", TeamMemberListCreateView.as_view(), name="team-member-list-create"),
    path(
        "teams/<uuid:team_pk>/members/<uuid:membership_pk>/",
        TeamMemberDetailView.as_view(),
        name="team-member-detail",
    ),
    path("profile/", MyProfileView.as_view(), name="my-profile"),
    path("profile/change-password/", ChangeMyPasswordView.as_view(), name="change-my-password"),
]
