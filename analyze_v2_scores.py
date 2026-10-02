import csv
import os
import re
import sqlite3
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "candidate_index.db")
S1_PATH = os.path.join(BASE_DIR, "dataset", "test", "test_source1.tsv")
CANDIDATE_PATH = os.path.join(BASE_DIR, "output", "candidate_pairs.tsv")
V2_PATH = os.path.join(BASE_DIR, "output", "matching_results_v2.tsv")
V4_PATH = os.path.join(BASE_DIR, "output", "matching_results_v4.tsv")


def normalize(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def load_match_file(path):
    result = {}

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            ids = row["matched_entity_ids"]

            if ids:
                result[row["source1_entity_id"]] = set(ids.split(","))

    return result


print("Loading V2 matches...")
v2_matches = load_match_file(V2_PATH)

print("Loading V4 matches...")
v4_matches = load_match_file(V4_PATH)

v2_only = {
    s1_id: ids
    for s1_id, ids in v2_matches.items()
    if s1_id not in v4_matches
}

print(f"V2 matched: {len(v2_matches):,}")
print(f"V2-only: {len(v2_only):,}")


print("Loading candidate pairs...")

candidates = {}

with open(CANDIDATE_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        ids = row["candidate_entity_ids"]
        candidates[row["source1_entity_id"]] = (
            ids.split(",") if ids else []
        )

print(f"Loaded candidate lists: {len(candidates):,}")


print("Loading records...")

conn = sqlite3.connect(DB_PATH)

record_map = {}

for entity_id, name_norm, address_norm, country in conn.execute(
    "SELECT entity_id, name_norm, address_norm, country FROM records"
):
    record_map[entity_id] = (
        name_norm or "",
        address_norm or "",
        country or ""
    )

conn.close()

print(f"Loaded records: {len(record_map):,}")
print("Analyzing V2-only rows...")


bins = {
    "0.00-0.79": 0,
    "0.80-0.84": 0,
    "0.85-0.87": 0,
    "0.88-0.89": 0,
    "0.90-0.91": 0,
    "0.92-0.93": 0,
    "0.94-0.95": 0,
    "0.96-0.97": 0,
    "0.98-1.00": 0,
}

processed = 0

with open(S1_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:

        s1_id = row["entity_id"]

        if s1_id not in v2_only:
            continue

        country = row["country"] or ""

        s1_name = normalize(row["business_name"])
        s1_address = normalize(row["business_address"])

        scored = []

        for candidate_id in candidates.get(s1_id, []):

            record = record_map.get(candidate_id)

            if record is None:
                continue

            c_name, c_address, c_country = record

            if c_country != country:
                continue

            name_score = similarity(s1_name, c_name)
            address_score = similarity(s1_address, c_address)

            if s1_name and s1_address:

                if s1_name == c_name and s1_address == c_address:
                    score = 1.0
                else:
                    score = (
                        0.60 * name_score +
                        0.40 * address_score
                    )

            elif s1_name:
                score = name_score

            elif s1_address:
                score = address_score

            else:
                score = 0.0

            scored.append(score)

        if scored:

            best = max(scored)

            if best < 0.80:
                bins["0.00-0.79"] += 1
            elif best < 0.85:
                bins["0.80-0.84"] += 1
            elif best < 0.88:
                bins["0.85-0.87"] += 1
            elif best < 0.90:
                bins["0.88-0.89"] += 1
            elif best < 0.92:
                bins["0.90-0.91"] += 1
            elif best < 0.94:
                bins["0.92-0.93"] += 1
            elif best < 0.96:
                bins["0.94-0.95"] += 1
            elif best < 0.98:
                bins["0.96-0.97"] += 1
            else:
                bins["0.98-1.00"] += 1

        processed += 1

        if processed % 5000 == 0:
            print(f"V2-only processed: {processed:,}")


print()
print("V2-only best-score distribution")
print("--------------------------------")
print(f"Rows analyzed: {processed:,}")

for key, value in bins.items():
    print(f"{key}: {value:,}")