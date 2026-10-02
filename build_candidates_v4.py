import csv
import os
import re
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "candidate_index.db")

S1_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "test",
    "test_source1.tsv"
)

V2_CANDIDATE_PATH = os.path.join(
    BASE_DIR,
    "output",
    "candidate_pairs.tsv"
)

OUTPUT_PATH = os.path.join(
    BASE_DIR,
    "output",
    "candidate_pairs_v5.tsv"
)


def normalize(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


print("Loading V2 candidate pairs...")

v2_candidates = {}

with open(
    V2_CANDIDATE_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:

        ids = row["candidate_entity_ids"]

        v2_candidates[row["source1_entity_id"]] = (
            ids.split(",") if ids else []
        )

print(
    f"Loaded V2 candidate lists: "
    f"{len(v2_candidates):,}"
)


print("Opening database...")

conn = sqlite3.connect(DB_PATH)

name_query = """
    SELECT entity_id
    FROM records
    WHERE country = ?
      AND name_norm = ?
    LIMIT 100
"""

address_query = """
    SELECT entity_id
    FROM records
    WHERE country = ?
      AND address_norm = ?
    LIMIT 50
"""


print("Building V5 candidates...")

total = 0

original_candidates = 0
new_candidates = 0
final_candidates = 0

name_hits = 0
address_hits = 0

rows_changed = 0
max_candidates = 0


with open(
    S1_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as s1_file, open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8",
    newline=""
) as out_file:

    reader = csv.DictReader(
        s1_file,
        delimiter="\t"
    )

    writer = csv.writer(
        out_file,
        delimiter="\t"
    )

    writer.writerow([
        "source1_entity_id",
        "candidate_entity_ids"
    ])

    for row in reader:

        total += 1

        s1_id = row["entity_id"]
        country = row["country"] or ""

        name = normalize(
            row["business_name"]
        )

        address = normalize(
            row["business_address"]
        )

        # --------------------------------------------------
        # Start with ALL V2 candidates.
        # This guarantees that V5 never loses V2 candidates.
        # --------------------------------------------------

        candidate_ids = set(
            v2_candidates.get(s1_id, [])
        )

        original_count = len(candidate_ids)

        original_candidates += original_count

        # --------------------------------------------------
        # Add exact normalized name candidates.
        # --------------------------------------------------

        if name:

            name_rows = conn.execute(
                name_query,
                (country, name)
            ).fetchall()

            if name_rows:
                name_hits += 1

                for entity_id, in name_rows:
                    candidate_ids.add(entity_id)

        # --------------------------------------------------
        # Add exact normalized address candidates.
        # --------------------------------------------------

        if address:

            address_rows = conn.execute(
                address_query,
                (country, address)
            ).fetchall()

            if address_rows:
                address_hits += 1

                for entity_id, in address_rows:
                    candidate_ids.add(entity_id)

        # --------------------------------------------------
        # Count only genuinely new candidates.
        # --------------------------------------------------

        final_count = len(candidate_ids)

        added = final_count - original_count

        new_candidates += added

        if added > 0:
            rows_changed += 1

        final_candidates += final_count

        if final_count > max_candidates:
            max_candidates = final_count

        ids = sorted(candidate_ids)

        writer.writerow([
            s1_id,
            ",".join(ids)
        ])

        if total % 100000 == 0:

            print(
                f"Processed: {total:,} | "
                f"Original V2: {original_candidates:,} | "
                f"New: {new_candidates:,} | "
                f"Final: {final_candidates:,}"
            )


conn.close()


print()
print("=" * 60)
print("V5 candidate generation complete")
print("=" * 60)

print(f"Source 1 rows:          {total:,}")
print(f"Original V2 candidates: {original_candidates:,}")
print(f"New candidates added:   {new_candidates:,}")
print(f"Final candidates:       {final_candidates:,}")
print(f"Rows changed:           {rows_changed:,}")
print(f"Max candidates/S1:     {max_candidates:,}")
print(f"Name-hit rows:          {name_hits:,}")
print(f"Address-hit rows:       {address_hits:,}")
print(f"Output:                 {OUTPUT_PATH}")