from xml.etree import ElementTree as ET

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from locations.models import Country, District, Mandal, State, Village


SS_NS = {"ss": "urn:schemas-microsoft-com:office:spreadsheet"}


def _cell_texts(row):
    values = []
    for cell in row.findall("ss:Cell", SS_NS):
        data = cell.find("ss:Data", SS_NS)
        values.append((data.text or "").strip() if data is not None and data.text else "")
    return values


class Command(BaseCommand):
    help = "Import Andhra Pradesh LGD villages from XML Spreadsheet .xls."

    def add_arguments(self, parser):
        parser.add_argument("xls_path", help="Path to LGD .xls (XML Spreadsheet format)")
        parser.add_argument(
            "--state-name",
            default="Andhra Pradesh",
            help="State name to assign in local DB (default: Andhra Pradesh)",
        )
        parser.add_argument(
            "--clear-existing-ap",
            action="store_true",
            help="Delete existing villages/mandals/districts for this AP state before import.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        xls_path = options["xls_path"]
        state_name = options["state_name"].strip()
        clear_existing_ap = options["clear_existing_ap"]

        try:
            tree = ET.parse(xls_path)
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {xls_path}") from exc
        except ET.ParseError as exc:
            raise CommandError(
                "Could not parse file as XML Spreadsheet .xls. "
                "Please use LGD exported .xls (XML format)."
            ) from exc

        root = tree.getroot()
        worksheet = root.find("ss:Worksheet", SS_NS)
        table = worksheet.find("ss:Table", SS_NS) if worksheet is not None else None
        rows = table.findall("ss:Row", SS_NS) if table is not None else []
        if not rows:
            raise CommandError("No worksheet rows found in file.")

        country, _ = Country.objects.get_or_create(name="India")
        state, _ = State.objects.get_or_create(country=country, name=state_name)

        if clear_existing_ap:
            Village.objects.filter(mandal__district__state=state).delete()
            Mandal.objects.filter(district__state=state).delete()
            District.objects.filter(state=state).delete()
            self.stdout.write(self.style.WARNING("Cleared existing AP location hierarchy."))

        district_cache = {
            d.name: d for d in District.objects.filter(state=state).only("id", "name")
        }
        mandal_cache = {}
        for m in Mandal.objects.filter(district__state=state).select_related("district").only(
            "id", "name", "district_id", "district__name"
        ):
            mandal_cache[(m.district.name, m.name)] = m

        village_keys = set(
            Village.objects.filter(mandal__district__state=state)
            .select_related("mandal__district")
            .values_list("mandal__district__name", "mandal__name", "name")
        )

        created = {"districts": 0, "mandals": 0, "villages": 0}
        updated_village_active = 0
        skipped = 0

        # LGD data rows start after header rows; we still guard by S.No numeric check.
        for row in rows:
            values = _cell_texts(row)
            if len(values) < 10 or not values[0].isdigit():
                continue

            district_name = values[2].strip()
            mandal_name = values[4].strip()
            village_name = values[7].strip()
            village_status = values[9].strip().lower()

            if not district_name or not mandal_name or not village_name:
                skipped += 1
                continue

            is_active = 1 if village_status.startswith("inhabit") else 0

            district = district_cache.get(district_name)
            if district is None:
                district = District.objects.create(state=state, name=district_name)
                district_cache[district_name] = district
                created["districts"] += 1

            mandal_key = (district_name, mandal_name)
            mandal = mandal_cache.get(mandal_key)
            if mandal is None:
                mandal = Mandal.objects.create(district=district, name=mandal_name)
                mandal_cache[mandal_key] = mandal
                created["mandals"] += 1

            village_key = (district_name, mandal_name, village_name)
            if village_key in village_keys:
                village = Village.objects.filter(mandal=mandal, name=village_name).first()
                if village and village.is_active != bool(is_active):
                    village.is_active = bool(is_active)
                    village.save(update_fields=["is_active"])
                    updated_village_active += 1
                continue

            Village.objects.create(
                mandal=mandal,
                name=village_name,
                is_active=bool(is_active),
            )
            village_keys.add(village_key)
            created["villages"] += 1

        self.stdout.write(self.style.SUCCESS("AP LGD import completed."))
        self.stdout.write(
            f"Created: districts={created['districts']}, "
            f"mandals={created['mandals']}, villages={created['villages']}"
        )
        self.stdout.write(f"Updated villages (is_active): {updated_village_active}")
        self.stdout.write(f"Skipped malformed rows: {skipped}")
