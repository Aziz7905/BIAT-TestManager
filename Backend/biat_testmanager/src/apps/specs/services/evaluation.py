from dataclasses import dataclass
import json
from pathlib import Path

from apps.projects.models import Project
from apps.specs.models import Specification
from apps.specs.services.indexing import keyword_retrieve_chunks, retrieve_similar_chunks
from apps.specs.services.mlflow_tracking import MLflowRunLogger


@dataclass
class RetrievalEvaluationCase:
    query: str
    expected_chunk_ids: list[str]
    project_id: str | None = None
    specification_id: str | None = None


def load_evaluation_cases(dataset_path: str) -> list[RetrievalEvaluationCase]:
    raw = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    return [
        RetrievalEvaluationCase(
            query=item["query"],
            expected_chunk_ids=item.get("expected_chunk_ids", []),
            project_id=item.get("project_id"),
            specification_id=item.get("specification_id"),
        )
        for item in raw
    ]


def _score_case(result_chunks, expected_chunk_ids: list[str]) -> tuple[float, float]:
    if not expected_chunk_ids:
        return 0.0, 0.0

    ids = [str(chunk.id) for chunk in result_chunks]
    hit_rank = next(
        (
            index + 1
            for index, chunk_id in enumerate(ids)
            if chunk_id in expected_chunk_ids
        ),
        None,
    )
    recall = 1.0 if hit_rank is not None else 0.0
    mrr = 1.0 / hit_rank if hit_rank is not None else 0.0
    return recall, mrr


def evaluate_retrieval_cases(
    cases: list[RetrievalEvaluationCase],
    *,
    top_k: int = 5,
) -> dict:
    summary = {
        "keyword": {"recall_at_k": 0.0, "mrr": 0.0},
        "vector": {"recall_at_k": 0.0, "mrr": 0.0},
    }
    case_results = []

    with MLflowRunLogger(
        "spec_retrieval_evaluation",
        params={
            "top_k": top_k,
            "case_count": len(cases),
        },
        tags={"pipeline": "spec_retrieval_evaluation"},
    ) as tracker:
        for case in cases:
            project = Project.objects.filter(pk=case.project_id).first() if case.project_id else None
            specification = (
                Specification.objects.filter(pk=case.specification_id).first()
                if case.specification_id
                else None
            )

            keyword_results = keyword_retrieve_chunks(
                case.query,
                top_k=top_k,
                project=project,
                specification=specification,
            )
            vector_results = retrieve_similar_chunks(
                case.query,
                top_k=top_k,
                project=project,
                specification=specification,
            )

            keyword_recall, keyword_mrr = _score_case(keyword_results, case.expected_chunk_ids)
            vector_recall, vector_mrr = _score_case(vector_results, case.expected_chunk_ids)

            summary["keyword"]["recall_at_k"] += keyword_recall
            summary["keyword"]["mrr"] += keyword_mrr
            summary["vector"]["recall_at_k"] += vector_recall
            summary["vector"]["mrr"] += vector_mrr

            case_results.append(
                {
                    "query": case.query,
                    "expected_chunk_ids": case.expected_chunk_ids,
                    "keyword_chunk_ids": [str(chunk.id) for chunk in keyword_results],
                    "vector_chunk_ids": [str(chunk.id) for chunk in vector_results],
                    "keyword_recall": keyword_recall,
                    "keyword_mrr": keyword_mrr,
                    "vector_recall": vector_recall,
                    "vector_mrr": vector_mrr,
                }
            )

        if cases:
            for strategy in ("keyword", "vector"):
                summary[strategy]["recall_at_k"] /= len(cases)
                summary[strategy]["mrr"] /= len(cases)

        tracker.log_metrics(
            {
                "keyword_recall_at_k": summary["keyword"]["recall_at_k"],
                "keyword_mrr": summary["keyword"]["mrr"],
                "vector_recall_at_k": summary["vector"]["recall_at_k"],
                "vector_mrr": summary["vector"]["mrr"],
            }
        )
        tracker.log_dict(
            {
                "summary": summary,
                "cases": case_results,
            },
            "retrieval_evaluation.json",
        )

    return {
        "summary": summary,
        "cases": case_results,
    }
