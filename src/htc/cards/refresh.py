"""Fetch the Fabrary card dataset and convert to TSV for the engine.

Usage:
    python3 -m htc.cards.refresh

Downloads the latest card.json from the Fabrary GitHub repository and
converts it to a tab-separated file at data/cards.tsv matching the column
format expected by CardDatabase.
"""

from __future__ import annotations

import csv
import json
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FABRARY_URL = (
    "https://raw.githubusercontent.com/fabrary/cards/main/"
    "packages/cards/scripts/Released/card.json"
)

# Output columns — must match what CardDatabase expects (Title Case, tab-separated).
TSV_COLUMNS = [
    "Unique ID",
    "Name",
    "Color",
    "Pitch",
    "Cost",
    "Power",
    "Defense",
    "Health",
    "Intelligence",
    "Arcane",
    "Types",
    "Traits",
    "Card Keywords",
    "Abilities and Effects",
    "Ability and Effect Keywords",
    "Granted Keywords",
    "Removed Keywords",
    "Interacts with Keywords",
    "Functional Text",
    "Type Text",
    "Card Played Horizontally",
    "Blitz Legal",
    "CC Legal",
    "Commoner Legal",
    "LL Legal",
]

# Map from TSV column name to Fabrary JSON field name.
_FIELD_MAP: dict[str, str] = {
    "Unique ID": "unique_id",
    "Name": "name",
    "Color": "color",
    "Pitch": "pitch",
    "Cost": "cost",
    "Power": "power",
    "Defense": "defense",
    "Health": "health",
    "Intelligence": "intelligence",
    "Arcane": "arcane",
    "Types": "types",
    "Traits": "traits",
    "Card Keywords": "card_keywords",
    "Abilities and Effects": "abilities_and_effects",
    "Ability and Effect Keywords": "ability_and_effect_keywords",
    "Granted Keywords": "granted_keywords",
    "Removed Keywords": "removed_keywords",
    "Interacts with Keywords": "interacts_with_keywords",
    "Functional Text": "functional_text",
    "Type Text": "type_text",
    "Card Played Horizontally": "played_horizontally",
    "Blitz Legal": "blitz_legal",
    "CC Legal": "cc_legal",
    "Commoner Legal": "commoner_legal",
    "LL Legal": "ll_legal",
}


def _to_tsv_value(column: str, raw_value: object) -> str:
    """Convert a single JSON field value to the TSV string representation."""
    if raw_value is None:
        return ""
    if isinstance(raw_value, list):
        # Arrays become comma-separated strings (e.g. types, keywords).
        return ", ".join(str(v) for v in raw_value)
    if isinstance(raw_value, bool):
        return str(raw_value)
    return str(raw_value)


def _convert_card(card: dict) -> list[str]:
    """Convert one Fabrary JSON card object to a list of TSV field values."""
    row: list[str] = []
    for col in TSV_COLUMNS:
        json_key = _FIELD_MAP[col]
        raw = card.get(json_key, "")
        row.append(_to_tsv_value(col, raw))
    return row


def fetch_and_convert(
    output_path: Path | None = None,
    json_path: Path | None = None,
) -> Path:
    """Download the Fabrary dataset and write data/cards.tsv.

    If *json_path* is given, read from a local file instead of fetching.
    Returns the path to the written file.
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent.parent / "data" / "cards.tsv"

    if json_path is not None:
        print(f"Reading card data from {json_path}...")
        data = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        # Fetch JSON — use unverified SSL context as a fallback for environments
        # where Python's certificate store is not configured (e.g. macOS).
        print("Fetching card data from Fabrary...")
        try:
            with urllib.request.urlopen(FABRARY_URL) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(FABRARY_URL, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))

    # Convert to TSV using csv.writer for proper quoting of fields
    # that contain newlines (e.g. functional_text).
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(TSV_COLUMNS)
        for card in data:
            writer.writerow(_convert_card(card))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"Wrote {len(data)} cards to {output_path}")
    print(f"Timestamp: {now}")

    return output_path


def main() -> None:
    fetch_and_convert()


if __name__ == "__main__":
    main()
