from django.core.management.base import BaseCommand, CommandError

from apps.marketdata.ingest import ingest_dataset


class Command(BaseCommand):
    help = "Ingest CSV M1, cache H1 parquet, dan simpan Dataset."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path filesystem ke CSV M1")
        parser.add_argument("--source-name", default="", help="Nama tampilan. Default: nama file.")
        parser.add_argument("--symbol", default="XAUUSD")
        parser.add_argument("--timeframe", default="1H")

    def handle(self, *args, **options):
        try:
            dataset = ingest_dataset(
                options["csv_path"],
                source_name=options["source_name"] or None,
                symbol=options["symbol"],
                timeframe=options["timeframe"],
            )
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"id={dataset.pk} source_name={dataset.source_name} "
                f"rows_m1={dataset.rows_m1} rows_h1={dataset.rows_h1} "
                f"volume_usable={dataset.volume_usable}"
            )
        )
