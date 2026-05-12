from django.urls import path

from apps.ai.views import (
    AIGenerationSessionCommitView,
    AIGenerationSessionDetailView,
    AIGenerationSessionListCreateView,
    AIGenerationSessionReviewView,
)

urlpatterns = [
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
