from django.core.management.base import BaseCommand, CommandError

from apps.projects.models import Project
from apps.specs.models import Specification
from apps.specs.services import reindex_specification_queryset


class Command(BaseCommand):
    help = "Rebuild chunk embeddings for specifications."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=str, help="Project UUID to limit reindexing.")
        parser.add_argument(
            "--specification",
            type=str,
            help="Specification UUID to reindex a single specification.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recompute embeddings even when chunks are already indexed.",
        )

    def handle(self, *args, **options):
        queryset = Specification.objects.all()

        if options["project"]:
            project = Project.objects.filter(pk=options["project"]).first()
            if project is None:
                raise CommandError("Project not found.")
            queryset = queryset.filter(project=project)

        if options["specification"]:
            queryset = queryset.filter(pk=options["specification"])

        count = reindex_specification_queryset(queryset, force=options["force"])
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} specification(s)."))

