#src/app/projects/views_tree.py
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.projects.access import get_project_queryset_for_actor
from apps.testing.serializers.tree import ProjectRepositoryTreeSerializer
from apps.testing.services import (
    build_project_repository_tree_summary,
    get_repository_tree_suites,
)


class ProjectTreeView(APIView):
    """
    GET /api/projects/<pk>/tree/

    Returns the full sidebar outline for a project in a single response:
      suites → sections (nested) → scenarios (title + case_count only)

    Cases are not included — they load on-demand when a scenario is selected.

    Query budget: ~4 queries regardless of tree depth.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(
            get_project_queryset_for_actor(request.user),
            pk=pk,
        )
        serializer = ProjectRepositoryTreeSerializer(
            {
                "project_id": project.id,
                "project_name": project.name,
                "summary": build_project_repository_tree_summary(project),
                "suites": get_repository_tree_suites(project),
            }
        )
        return Response(serializer.data)
