from django.urls import path

from apps.ai.api.views import (
    AIAuthoringSessionStartView,
    AIAuthoringTraceSaveView,
    AIGenerationSessionCommitView,
    AIGenerationSessionDetailView,
    AIGenerationSessionListCreateView,
    AIGenerationSessionReviewView,
)

urlpatterns = [
    path(
        "ai/authoring/sessions/",
        AIAuthoringSessionStartView.as_view(),
        name="ai-authoring-session-start",
    ),
    path(
        "ai/authoring/sessions/<uuid:execution_pk>/save-trace/",
        AIAuthoringTraceSaveView.as_view(),
        name="ai-authoring-trace-save",
    ),
    path(
        "ai/generations/",
        AIGenerationSessionListCreateView.as_view(),
        name="ai-generation-list-create",
    ),
    path(
        "ai/generations/<uuid:pk>/",
        AIGenerationSessionDetailView.as_view(),
        name="ai-generation-detail",
    ),
    path(
        "ai/generations/<uuid:pk>/review/",
        AIGenerationSessionReviewView.as_view(),
        name="ai-generation-review",
    ),
    path(
        "ai/generations/<uuid:pk>/commit/",
        AIGenerationSessionCommitView.as_view(),
        name="ai-generation-commit",
    ),
]
