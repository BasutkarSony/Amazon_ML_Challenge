import csv
import os
import re
import sqlite3
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "candidate_index.db")

S1_PATH = os.path.join(
    BASE_DIR, "dataset", "test", "test_source1.tsv"
)

CANDIDATE_PATH = os.path.join(
    BASE_DIR, "output", "candidate_pairs.tsv"
)

V2_PATH = os.path.join(
    BASE_DIR, "output", "matching_results_v2.tsv"
)

V5_PATH = os.path.join(
    BASE_DIR, "output", "matching_results_v5.tsv"
)


def normalize(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def similarity(a, b):
    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


print("Finding V5-only Source-1 records...")

v2_matches = {}
v5_matches = {}

with open(V2_PATH, "r", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        ids = row["matched_entity_ids"]
        v2_matches[row["source1_entity_id"]] = (
            set(ids.split(",")) if ids else set()
        )

with open(V5_PATH, "r", encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f, delimiter="\t"):
        ids = row["matched_entity_ids"]
        v5_matches[row["source1_entity_id"]] = (
            set(ids.split(",")) if ids else set()
        )

v5_only = []

for s1_id, v5_ids in v5_matches.items():
    v2_ids = v2_matches.get(s1_id, set())

    if v5_ids and not v2_ids:
        v5_only.append(s1_id)

print(f"V5-only S1 records: {len(v5_only):,}")

v5_only_set = set(v5_only)


print("Loading candidate pairs...")

candidates = {}

with open(
    CANDIDATE_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:
    for row in csv.DictReader(f, delimiter="\t"):

        s1_id = row["source1_entity_id"]

        if s1_id in v5_only_set:

            ids = row["candidate_entity_ids"]

            candidates[s1_id] = (
                ids.split(",") if ids else []
            )

print(
    f"Loaded candidate lists for "
    f"{len(candidates):,} V5-only records."
)


print("Loading candidate records...")

needed_ids = set()

for ids in candidates.values():
    needed_ids.update(ids)

print(
    f"Unique candidate IDs needed: "
    f"{len(needed_ids):,}"
)

conn = sqlite3.connect(DB_PATH)

record_map = {}

cursor = conn.execute(
    """
    SELECT
        entity_id,
        name_norm,
        address_norm,
        country
    FROM records
    """
)

count = 0

for entity_id, name_norm, address_norm, country in cursor:

    if entity_id in needed_ids:

        record_map[entity_id] = (
            name_norm or "",
            address_norm or "",
            country or ""
        )

    count += 1

conn.close()

print(
    f"Loaded required records: "
    f"{len(record_map):,}"
)


print("Reading Source-1 records...")

s1_data = {}

with open(
    S1_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    for row in csv.DictReader(f, delimiter="\t"):

        s1_id = row["entity_id"]

        if s1_id in v5_only_set:

            s1_data[s1_id] = (
                row["country"] or "",
                normalize(row["business_name"]),
                normalize(row["business_address"])
            )


print("Analyzing V5-only scores...")

score_buckets = {
    "0.88-0.89": 0,
    "0.90-0.91": 0,
    "0.92-0.93": 0,
    "0.94-0.95": 0,
    "0.96-0.97": 0,
    "0.98-1.00": 0,
}

examples = []

for s1_id in v5_only:

    country, s1_name, s1_address = s1_data[s1_id]

    scored = []

    for candidate_id in candidates.get(s1_id, []):

        record = record_map.get(candidate_id)

        if record is None:
            continue

        c_name, c_address, c_country = record

        if c_country != country:
            continue

        name_score = similarity(
            s1_name,
            c_name
        )

        address_score = similarity(
            s1_address,
            c_address
        )

        if s1_name and s1_address:

            if (
                s1_name == c_name
                and
                s1_address == c_address
            ):
                score = 1.0

            else:
                score = (
                    0.70 * name_score
                    +
                    0.30 * address_score
                )

        elif s1_name:

            score = name_score

        elif s1_address:

            score = address_score

        else:

            score = 0.0

        scored.append(
            (candidate_id, score)
        )

    if not scored:
        continue

    scored.sort(
        key=lambda x: x[1],
        reverse=True
    )

    best_id, best_score = scored[0]

    if best_score >= 0.88:

        if best_score < 0.90:
            bucket = "0.88-0.89"
        elif best_score < 0.92:
            bucket = "0.90-0.91"
        elif best_score < 0.94:
            bucket = "0.92-0.93"
        elif best_score < 0.96:
            bucket = "0.94-0.95"
        elif best_score < 0.98:
            bucket = "0.96-0.97"
        else:
            bucket = "0.98-1.00"

        score_buckets[bucket] += 1

        if len(examples) < 30:

            examples.append(
                (
                    s1_id,
                    best_id,
                    best_score,
                    s1_name,
                    s1_address,
                    record_map[best_id][0],
                    record_map[best_id][1]
                )
            )


print()
print("V5-only best-score distribution")
print("--------------------------------")

for bucket, count in score_buckets.items():

    print(
        f"{bucket}: {count:,}"
    )


print()
print("Sample V5-only matches")
print("----------------------")

for example in examples:

    (
        s1_id,
        candidate_id,
        score,
        s1_name,
        s1_address,
        c_name,
        c_address
    ) = example

    print()
    print(f"S1:        {s1_id}")
    print(f"Candidate: {candidate_id}")
    print(f"Score:     {score:.4f}")
    print(f"S1 name:   {s1_name}")
    print(f"C name:    {c_name}")
    print(f"S1 addr:   {s1_address}")
    print(f"C addr:    {c_address}")