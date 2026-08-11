import csv
import io
import urllib.request
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


# Official 2025 U.S. Census national Places Gazetteer.
# The previous filename used by the project was incorrect and returned 404.
GAZETTEER_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2025_Gazetteer/2025_Gaz_place_national.zip"
)


def clean_city(name: str) -> str:
    """Normalize Census place names to match the CSV's plain city names."""
    name = name.split(",")[0].strip()

    suffixes = [
        " city",
        " town",
        " village",
        " borough",
        " municipality",
        " CDP",
        " urban county",
        " metro township",
    ]

    upper = name.upper()
    for suffix in suffixes:
        if upper.endswith(suffix.upper()):
            name = name[: -len(suffix)].strip()
            break

    return " ".join(name.upper().split())


class Command(BaseCommand):
    help = "Download the U.S. Census Gazetteer and build city_centroids.csv."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=GAZETTEER_URL,
            help="Official Census Places Gazetteer ZIP URL.",
        )
        parser.add_argument(
            "--output",
            default="data/city_centroids.csv",
            help="Output lookup path.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Downloading official U.S. Census Places Gazetteer...")

        try:
            request = urllib.request.Request(
                options["url"],
                headers={"User-Agent": "fuel-route-optimizer/1.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                content = response.read()
        except Exception as exc:
            raise CommandError(f"Could not download Census Gazetteer: {exc}") from exc

        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                txt_names = [
                    name for name in archive.namelist()
                    if name.lower().endswith(".txt")
                ]

                if not txt_names:
                    raise CommandError(
                        "Census Gazetteer ZIP did not contain a TXT file."
                    )

                raw = archive.read(txt_names[0]).decode("utf-8-sig")
        except zipfile.BadZipFile as exc:
            raise CommandError(
                "Downloaded Census file was not a valid ZIP archive."
            ) from exc

        # 2025 Census Gazetteer files are pipe-delimited, not tab-delimited.
        reader = csv.DictReader(io.StringIO(raw), delimiter="|")

        required = {"USPS", "NAME", "INTPTLAT", "INTPTLONG"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise CommandError(
                "Unexpected Census Gazetteer schema. "
                f"Expected {sorted(required)}, got {reader.fieldnames}"
            )

        unique = {}

        for row in reader:
            state = (row.get("USPS") or "").strip().upper()
            name = (row.get("NAME") or "").strip()
            lat = (row.get("INTPTLAT") or "").strip()
            lon = (row.get("INTPTLONG") or "").strip()

            if not state or not name or not lat or not lon:
                continue

            try:
                latitude = float(lat)
                longitude = float(lon)
            except ValueError:
                continue

            city = clean_city(name)
            if not city:
                continue

            # Keep the first official Census representative point for a
            # normalized city/state pair.
            unique.setdefault(
                (city, state),
                {
                    "city": city,
                    "state": state,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )

        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["city", "state", "latitude", "longitude"],
            )
            writer.writeheader()
            writer.writerows(
                sorted(unique.values(), key=lambda x: (x["state"], x["city"]))
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Wrote {len(unique):,} city centroids to {output}."
            )
        )
