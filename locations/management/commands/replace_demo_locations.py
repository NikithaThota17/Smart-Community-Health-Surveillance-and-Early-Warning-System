import re

from django.core.management.base import BaseCommand
from django.db import transaction

from locations.models import District, Mandal, Village


DEMO_MANDAL_PATTERN = re.compile(r".+\sMandal\s\d+$", re.IGNORECASE)
DEMO_VILLAGE_PATTERN = re.compile(r".+\sVillage\s\d+-\d+$", re.IGNORECASE)


DISTRICT_MASTER = {
    "Hyderabad": [
        ("Shaikpet", ["Toli Chowki", "Nanal Nagar", "Manikonda"]),
        ("Ameerpet", ["SR Nagar", "Yousufguda", "Madhura Nagar"]),
        ("Charminar", ["Shalibanda", "Falaknuma", "Hussaini Alam"]),
    ],
    "Warangal": [
        ("Hanamkonda", ["Kazipet", "Subedari", "Nakkalagutta"]),
        ("Hasanparthy", ["Elkathurthy", "Pegadapally", "Chintagattu"]),
        ("Wardhannapet", ["Inavole", "Kothapet", "Ramavaram"]),
    ],
    "Karimnagar": [
        ("Karimnagar Rural", ["Bommakal", "Chamanpally", "Malkapur"]),
        ("Huzurabad", ["Jammikunta", "Shalapally", "Veenavanka"]),
        ("Choppadandi", ["Aravapally", "Rukmapur", "Gopalraopet"]),
    ],
    "Nizamabad": [
        ("Nizamabad South", ["Dichpally", "Mopanpally", "Madhavnagar"]),
        ("Bodhan", ["Saloora", "Sangam", "Amdapur"]),
        ("Armoor", ["Perkit", "Mendora", "Ankapur"]),
    ],
    "Khammam": [
        ("Khammam Urban", ["Raghunadhapalem", "Mamidipalli", "Allipuram"]),
        ("Kusumanchi", ["Gattu Singaram", "Jujjularao Peta", "Palair"]),
        ("Wyra", ["Garikapadu", "Somavaram", "Narayana Puram"]),
    ],
    "Visakhapatnam": [
        ("Bheemunipatnam", ["Tagarapuvalasa", "Nidigattu", "Mudasarlova"]),
        ("Anandapuram", ["Gambheeram", "Bakkannapalem", "Vellanki"]),
        ("Pendurthi", ["Chinamushidiwada", "Sujatha Nagar", "Pulaganipalem"]),
    ],
    "Vijayawada": [
        ("Vijayawada Urban", ["Patamata", "Gollapudi", "Gunadala"]),
        ("Penamaluru", ["Poranki", "Kanuru", "Yanamalakuduru"]),
        ("Kankipadu", ["Punadipadu", "Prodduturu", "Kankipadu Village"]),
    ],
    "Guntur": [
        ("Amaravathi", ["Mandadam", "Velagapudi", "Uddandarayunipalem"]),
        ("Tadikonda", ["Pedaparimi", "Ponnekallu", "Lam"]),
        ("Mangalagiri", ["Nidamarru", "Atmakur", "Nutakki"]),
    ],
    "Tirupati": [
        ("Tirupati Rural", ["Tanapalli", "Peruru", "Mukkoti"]),
        ("Renigunta", ["Karakambadi", "Thukivakam", "Settipalli"]),
        ("Chandragiri", ["Mallavaram", "Agarala", "Mungilipattu"]),
    ],
    "Kurnool": [
        ("Kurnool Urban", ["Kallur", "Sunkesula", "Joharapuram"]),
        ("Nandyal", ["Ayyalur", "Mahanandi", "Panyam"]),
        ("Adoni", ["Isvi", "Pandavagallu", "Basarakodu"]),
    ],
}


class Command(BaseCommand):
    help = "Replace demo mandal/village names in-place without CSV."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview rename operations without saving changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        renamed_mandals = 0
        renamed_villages = 0
        unknown_districts = []

        with transaction.atomic():
            for district in District.objects.all().order_by("id"):
                plans = DISTRICT_MASTER.get(district.name)
                if not plans:
                    unknown_districts.append(district.name)
                    continue

                mandals = list(Mandal.objects.filter(district=district).order_by("id"))
                for i, mandal in enumerate(mandals):
                    if i >= len(plans):
                        break

                    new_mandal_name, village_names = plans[i]
                    if DEMO_MANDAL_PATTERN.match(mandal.name):
                        if not dry_run:
                            mandal.name = new_mandal_name
                            mandal.save(update_fields=["name"])
                        renamed_mandals += 1

                    villages = list(Village.objects.filter(mandal=mandal).order_by("id"))
                    for j, village in enumerate(villages):
                        if j >= len(village_names):
                            break
                        if DEMO_VILLAGE_PATTERN.match(village.name):
                            if not dry_run:
                                village.name = village_names[j]
                                village.save(update_fields=["name"])
                            renamed_villages += 1

            if dry_run:
                transaction.set_rollback(True)

        if unknown_districts:
            self.stdout.write(
                self.style.WARNING(
                    "No mapping defined for districts: " + ", ".join(sorted(set(unknown_districts)))
                )
            )

        mode = "Preview complete" if dry_run else "Rename complete"
        self.stdout.write(self.style.SUCCESS(mode))
        self.stdout.write(f"Mandals renamed: {renamed_mandals}")
        self.stdout.write(f"Villages renamed: {renamed_villages}")
