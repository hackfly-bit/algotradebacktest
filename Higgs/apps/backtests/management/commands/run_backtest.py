from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.backtests.models import BacktestRun
from apps.backtests.tasks import enqueue_run
from apps.marketdata.models import Dataset


class Command(BaseCommand):
    help = "Create a BacktestRun and enqueue it (ImmediateBackend runs inline)."

    def add_arguments(self, parser):
        parser.add_argument("--dataset-id", type=int, default=None)
        parser.add_argument("--strategy", default="ema_rsi_volume")
        parser.add_argument("--debug-bars", type=int, default=0, help="If >0, trim H1 cache in-task is not applied; use for docs only.")

    def handle(self, *args, **options):
        ds = (
            Dataset.objects.filter(pk=options["dataset_id"]).first()
            if options["dataset_id"]
            else Dataset.objects.order_by("-created_at").first()
        )
        if ds is None:
            raise CommandError("Tidak ada Dataset. Ingest CSV dulu.")

        with transaction.atomic():
            run = BacktestRun.objects.create(
                dataset=ds,
                strategy_name=options["strategy"],
                params={"volume_usable": ds.volume_usable},
                status=BacktestRun.Status.QUEUED,
            )
            run_id = run.pk

        def _enqueue():
            result = enqueue_run.enqueue(run_id)
            BacktestRun.objects.filter(pk=run_id).update(task_id=str(getattr(result, "id", "") or ""))

        transaction.on_commit(_enqueue)
        # ImmediateBackend may already have finished inside enqueue
        run.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(f"run={run_id} status={run.status} trades={run.trades.count()}"))
