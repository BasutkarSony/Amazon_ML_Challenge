import csv
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "candidate_index.db")
S1_PATH = os.path.join(BASE_DIR, "dataset", "test", "test_source1.tsv")
V2_PATH = os.path.join(BASE_DIR, "output", "candidate_pairs.tsv")
V5_PATH = os.path.join(BASE_DIR, "output", "candidate_pairs_v5.tsv")

# Hard limits so the candidate set does not explode.
MAX_EXACT_NAME = 20
MAX_EXACT_ADDRESS = 10
MAX_TOTAL = 500


def normalize(text):
    if not isinstance(text, str):
        return ""

    import re

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


print("Opening database...")

conn = sqlite3.connect(DB_PATH)

name_query = """
    SELECT entity_id
    FROM records
    WHERE country = ?
      AND name_norm = ?
    LIMIT ?
"""

address_query = """
    SELECT entity_id
    FROM records
    WHERE country = ?
      AND address_norm = ?
    LIMIT ?
"""


print("Loading V2 candidates...")

v2_candidates = {}

with open(
    V2_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:

        value = row["candidate_entity_ids"]

        v2_candidates[row["source1_entity_id"]] = (
            value.split(",") if value else []
        )

print(f"Loaded {len(v2_candidates):,} V2 candidate lists.")


print("Building V5 candidates...")

total = 0
total_original = 0
total_added = 0
total_final = 0
rows_changed = 0
max_final = 0


with open(
    S1_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as s1_file, open(
    V5_PATH,
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

        name = normalize(row["business_name"])
        address = normalize(row["business_address"])

        # ---------------------------------------------------------
        # Start with ALL V2 candidates.
        # Nothing from the baseline is removed.
        # ---------------------------------------------------------

        original = v2_candidates.get(
            s1_id,
            []
        )

        candidate_set = set(original)

        total_original += len(candidate_set)

        before = len(candidate_set)

        # ---------------------------------------------------------
        # Add exact normalized-name candidates.
        # ---------------------------------------------------------

        if name:

            rows = conn.execute(
                name_query,
                (
                    country,
                    name,
                    MAX_EXACT_NAME
                )
            ).fetchall()

            for entity_id, in rows:
                candidate_set.add(entity_id)

        # ---------------------------------------------------------
        # Add exact normalized-address candidates.
        # ---------------------------------------------------------

        if address:

            rows = conn.execute(
                address_query,
                (
                    country,
                    address,
                    MAX_EXACT_ADDRESS
                )
            ).fetchall()

            for entity_id, in rows:
                candidate_set.add(entity_id)

        added = len(candidate_set) - before

        total_added += added

        # ---------------------------------------------------------
        # Safety limit.
        #
        # V2 has a maximum of 480 candidates per S1.
        # Never allow V5 to exceed that.
        # Existing V2 candidates always have priority.
        # ---------------------------------------------------------

        if len(candidate_set) > MAX_TOTAL:

            final_ids = list(original)

            original_set = set(original)

            extra_ids = sorted(
                candidate_set - original_set
            )

            remaining = MAX_TOTAL - len(final_ids)

            if remaining > 0:
                final_ids.extend(
                    extra_ids[:remaining]
                )

            candidate_set = set(final_ids)

        final_ids = sorted(candidate_set)

        if len(final_ids) != len(original):
            rows_changed += 1

        total_final += len(final_ids)

        if len(final_ids) > max_final:
            max_final = len(final_ids)

        writer.writerow([
            s1_id,
            ",".join(final_ids)
        ])

        if total % 100000 == 0:

            print(
                f"Processed: {total:,} | "
                f"Original: {total_original:,} | "
                f"Added: {total_added:,} | "
                f"Final: {total_final:,}"
            )


conn.close()

print()
print("V5 candidate generation complete.")
print(f"Source 1 rows: {total:,}")
print(f"Original V2 candidates: {total_original:,}")
print(f"New candidates added: {total_added:,}")
print(f"Final candidates: {total_final:,}")
print(f"Rows changed: {rows_changed:,}")
print(f"Max candidates per S1: {max_final:,}")
print(f"Output: {V5_PATH}")