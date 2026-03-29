from django.core.management.base import BaseCommand

from locations.models import Mandal, Village


class Command(BaseCommand):
    help = (
        "Create one fallback village per mandal (for example: "
        "'<Mandal Name> Urban/Unknown') so users can proceed when exact village is unknown."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            default="Andhra Pradesh",
            help="Limit to this state name (default: Andhra Pradesh). Use '*' for all states.",
        )
        parser.add_argument(
            "--suffix",
            default="Urban",
            help="Fallback suffix appended to mandal name.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without saving.",
        )

    def handle(self, *args, **options):
        state_name = (options["state"] or "").strip()
        suffix = (options["suffix"] or "Urban").strip()
        dry_run = options["dry_run"]

        mandals = Mandal.objects.select_related("district__state").all().order_by(
            "district__state__name", "district__name", "name"
        )

        if state_name and state_name != "*":
            mandals = mandals.filter(district__state__name__iexact=state_name)

        created = 0
        already_present = 0

        for mandal in mandals:
            fallback_name = f"{mandal.name} {suffix}"
            exists = Village.objects.filter(
                mandal=mandal,
                name__iexact=fallback_name,
            ).exists()

            if exists:
                already_present += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would create: {fallback_name} "
                    f"({mandal.name}, {mandal.district.name})"
                )
            else:
                Village.objects.create(
                    mandal=mandal,
                    name=fallback_name,
                    is_active=True,
                )
            created += 1

        self.stdout.write(self.style.SUCCESS(f"Fallback villages created: {created}"))
        self.stdout.write(self.style.WARNING(f"Already present: {already_present}"))
