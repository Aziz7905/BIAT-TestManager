from django.core.management.base import BaseCommand, CommandError

from apps.specs.services import evaluate_retrieval_cases, load_evaluation_cases


class Command(BaseCommand):
    help = "Evaluate keyword vs vector retrieval on a labeled dataset."

    def add_arguments(self, parser):
        parser.add_argument("dataset", type=str, help="Path to a JSON evaluation dataset.")
        parser.add_argument("--top-k", type=int, default=5)

    def handle(self, *args, **options):
        try:
            cases = load_evaluation_cases(options["dataset"])
        except FileNotFoundError as error:
            raise CommandError(str(error)) from error

        result = evaluate_retrieval_cases(cases, top_k=options["top_k"])
        summary = result["summary"]

        self.stdout.write(
            self.style.SUCCESS(
                "FTS recall@k={full_text_recall:.3f}, FTS mrr={full_text_mrr:.3f}, "
                "hybrid recall@k={hybrid_recall:.3f}, hybrid mrr={hybrid_mrr:.3f}, "
                "vector recall@k={vector_recall:.3f}, vector mrr={vector_mrr:.3f}".format(
                    full_text_recall=summary["full_text"]["recall_at_k"],
                    full_text_mrr=summary["full_text"]["mrr"],
                    hybrid_recall=summary["hybrid"]["recall_at_k"],
                    hybrid_mrr=summary["hybrid"]["mrr"],
                    vector_recall=summary["vector"]["recall_at_k"],
                    vector_mrr=summary["vector"]["mrr"],
                )
            )
        )
