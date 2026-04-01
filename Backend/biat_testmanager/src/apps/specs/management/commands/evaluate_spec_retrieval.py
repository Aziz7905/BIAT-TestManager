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
                "Keyword recall@k={keyword_recall:.3f}, keyword mrr={keyword_mrr:.3f}, "
                "vector recall@k={vector_recall:.3f}, vector mrr={vector_mrr:.3f}".format(
                    keyword_recall=summary["keyword"]["recall_at_k"],
                    keyword_mrr=summary["keyword"]["mrr"],
                    vector_recall=summary["vector"]["recall_at_k"],
                    vector_mrr=summary["vector"]["mrr"],
                )
            )
        )
