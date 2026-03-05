import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from locations.models import Country, District, Mandal, State, Village


TRUTHY_VALUES = {"1", "true", "yes", "y"}
DEMO_MANDAL_PATTERN = re.compile(r".+\sMandal\s\d+$", re.IGNORECASE)
DEMO_VILLAGE_PATTERN = re.compile(r".+\sVillage\s\d+-\d+$", re.IGNORECASE)


class Command(BaseCommand):
    help = (
        "Import hierarchical location master data from CSV with columns: "
        "country,state,district,mandal,village,is_active"
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to CSV file")
        parser.add_argument(
            "--replace-demo",
            action="store_true",
            help="Delete demo-style mandal/village names before import",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"]).expanduser().resolve()
        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            required = {"country", "state", "district", "mandal", "village"}
            if not reader.fieldnames:
                raise CommandError("CSV has no header row.")

            fields = {name.strip().lower() for name in reader.fieldnames}
            missing = required - fields
            if missing:
                raise CommandError(
                    "CSV missing required columns: " + ", ".join(sorted(missing))
                )

            rows = list(reader)
            if not rows:
                raise CommandError("CSV contains no data rows.")

        created = {
            "countries": 0,
            "states": 0,
            "districts": 0,
            "mandals": 0,
            "villages": 0,
        }
        updated_villages = 0

        with transaction.atomic():
            if options["replace_demo"]:
                deleted_villages, deleted_mandals = self._delete_demo_records()
                self.stdout.write(
                    self.style.WARNING(
                        f"Deleted demo records: {deleted_villages} villages, "
                        f"{deleted_mandals} mandals."
                    )
                )

            for idx, row in enumerate(rows, start=2):
                country_name = (row.get("country") or "").strip()
                state_name = (row.get("state") or "").strip()
                district_name = (row.get("district") or "").strip()
                mandal_name = (row.get("mandal") or "").strip()
                village_name = (row.get("village") or "").strip()
                is_active_raw = (row.get("is_active") or "true").strip().lower()

                if not all(
                    [country_name, state_name, district_name, mandal_name, village_name]
                ):
                    raise CommandError(
                        f"Row {idx}: country/state/district/mandal/village are required."
                    )

                is_active = is_active_raw in TRUTHY_VALUES

                country, was_created = Country.objects.get_or_create(name=country_name)
                created["countries"] += int(was_created)

                state, was_created = State.objects.get_or_create(
                    country=country, name=state_name
                )
                created["states"] += int(was_created)

                district, was_created = District.objects.get_or_create(
                    state=state, name=district_name
                )
                created["districts"] += int(was_created)

                mandal, was_created = Mandal.objects.get_or_create(
                    district=district, name=mandal_name
                )
                created["mandals"] += int(was_created)

                village, was_created = Village.objects.get_or_create(
                    mandal=mandal, name=village_name,
                    defaults={"is_active": is_active},
                )
                if was_created:
                    created["villages"] += 1
                elif village.is_active != is_active:
                    village.is_active = is_active
                    village.save(update_fields=["is_active"])
                    updated_villages += 1

        self.stdout.write(self.style.SUCCESS("Location import completed."))
        self.stdout.write(
            f"Created: countries={created['countries']}, "
            f"states={created['states']}, districts={created['districts']}, "
            f"mandals={created['mandals']}, villages={created['villages']}"
        )
        self.stdout.write(f"Updated villages (is_active): {updated_villages}")

    def _delete_demo_records(self):
        village_ids = [
            village_id
            for village_id, name in Village.objects.values_list("id", "name")
            if DEMO_VILLAGE_PATTERN.match((name or "").strip())
        ]

        mandal_ids = [
            mandal_id
            for mandal_id, name in Mandal.objects.values_list("id", "name")
            if DEMO_MANDAL_PATTERN.match((name or "").strip())
        ]

        deleted_villages = Village.objects.filter(id__in=village_ids).delete()[0]
        deleted_mandals = Mandal.objects.filter(id__in=mandal_ids).delete()[0]
        return deleted_villages, deleted_mandals
