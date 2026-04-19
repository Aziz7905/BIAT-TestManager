from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404

from apps.projects.access import get_project_queryset_for_actor
from apps.testing.serializers import (
    ProjectDashboardOverviewSerializer,
    ProjectFailureHotspotsSerializer,
    ProjectPassRateTrendSerializer,
)
from apps.testing.services import (
    build_project_pass_rate_trend,
    build_project_quality_dashboard,
    list_project_failure_hotspots,
)


class ProjectDashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_pk):
        project = get_object_or_404(get_project_queryset_for_actor(request.user), pk=project_pk)
        recent_run_limit = _parse_bounded_int(
            request.query_params.get("recent_runs"),
            default=5,
            minimum=1,
            maximum=20,
        )
        payload = build_project_quality_dashboard(
            project,
            recent_run_limit=recent_run_limit,
        )
        serializer = ProjectDashboardOverviewSerializer(payload)
        return Response(serializer.data)


class ProjectPassRateTrendView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_pk):
        project = get_object_or_404(get_project_queryset_for_actor(request.user), pk=project_pk)
        days = _parse_bounded_int(
            request.query_params.get("days"),
            default=14,
            minimum=1,
            maximum=90,
        )
        payload = build_project_pass_rate_trend(project, days=days)
        serializer = ProjectPassRateTrendSerializer(payload)
        return Response(serializer.data)


class ProjectFailureHotspotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_pk):
        project = get_object_or_404(get_project_queryset_for_actor(request.user), pk=project_pk)
        days = _parse_bounded_int(
            request.query_params.get("days"),
            default=30,
            minimum=1,
            maximum=180,
        )
        limit = _parse_bounded_int(
            request.query_params.get("limit"),
            default=10,
            minimum=1,
            maximum=50,
        )
        payload = list_project_failure_hotspots(project, days=days, limit=limit)
        serializer = ProjectFailureHotspotsSerializer(payload)
        return Response(serializer.data)


def _parse_bounded_int(raw_value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(raw_value) if raw_value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))
