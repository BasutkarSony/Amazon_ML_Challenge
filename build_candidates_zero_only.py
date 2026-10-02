import csv
import os
import re
import sqlite3
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "candidate_index.db")
S1_PATH = os.path.join(BASE_DIR, "dataset", "test", "test_source1.tsv")
BASE_CANDIDATES = os.path.join(
    BASE_DIR, "output", "candidate_pairs.tsv"
)
OUTPUT_PATH = os.path.join(
    BASE_DIR, "output", "candidate_pairs_zero_only.tsv"
)

MAX_PER_TOKEN = 20
MAX_NEW_PER_S1 = 60

STOPWORDS = {
    "the", "and", "for", "with", "from",
    "llc", "inc", "ltd", "limited",
    "private", "pvt", "corp", "corporation",
    "company", "co", "plc", "group",
    "services", "india", "usa", "united"
}


def normalize(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def informative_tokens(name):
    return {
        token
        for token in name.split()
        if len(token) >= 4 and token not in STOPWORDS
    }


print("Loading Source 1 tokens...")

s1_tokens = {}

with open(S1_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        tokens = informative_tokens(
            normalize(row["business_name"])
        )
        s1_tokens[row["entity_id"]] = tokens

print(f"S1 records: {len(s1_tokens):,}")


print("Building token -> S1 map...")

zero_ids = set()
with open(BASE_CANDIDATES, "r", encoding="utf-8", newline="") as zf:
    for zr in csv.DictReader(zf, delimiter="\t"):
        if not zr["candidate_entity_ids"]:
            zero_ids.add(zr["source1_entity_id"])
print(f"Zero-candidate S1 records: {len(zero_ids):,}")

token_to_s1 = defaultdict(list)

for s1_id, tokens in s1_tokens.items():
    if s1_id not in zero_ids:
        continue
    for token in tokens:
        token_to_s1[token].append(s1_id)

print(f"Unique tokens: {len(token_to_s1):,}")


print("Opening training candidate database...")

conn = sqlite3.connect(DB_PATH)

cursor = conn.execute(
    """
    SELECT entity_id, name_norm, country
    FROM records
    WHERE name_norm != ''
    """
)

new_candidates = defaultdict(set)
token_counts = defaultdict(int)

processed = 0

print("Scanning S2 + S3 records...")

for entity_id, name_norm, country in cursor:

    processed += 1

    tokens = informative_tokens(name_norm)

    for token in tokens:

        s1_list = token_to_s1.get(token)

        if not s1_list:
            continue

        key = (country or "", token)

        if token_counts[key] >= MAX_PER_TOKEN:
            continue

        token_counts[key] += 1

        for s1_id in s1_list:

            if len(new_candidates[s1_id]) >= MAX_NEW_PER_S1:
                continue

            new_candidates[s1_id].add(entity_id)

    if processed % 1_000_000 == 0:
        print(
            f"Scanned: {processed:,} | "
            f"S1 with token candidates: {len(new_candidates):,}"
        )

conn.close()

print()
print(f"Database records scanned: {processed:,}")
print(
    f"S1 with token candidates: "
    f"{len(new_candidates):,}"
)


print("Merging with existing training candidates...")

total = 0
expanded = 0
base_total = 0
added_total = 0
final_total = 0
max_final = 0

with open(
    BASE_CANDIDATES,
    "r",
    encoding="utf-8",
    newline=""
) as in_file, open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8",
    newline=""
) as out_file:

    reader = csv.DictReader(in_file, delimiter="\t")
    writer = csv.writer(out_file, delimiter="\t")

    writer.writerow([
        "source1_entity_id",
        "candidate_entity_ids"
    ])

    for row in reader:

        total += 1

        s1_id = row["source1_entity_id"]

        old_ids = (
            set(row["candidate_entity_ids"].split(","))
            if row["candidate_entity_ids"]
            else set()
        )

        added_ids = new_candidates.get(s1_id, set())

        combined = old_ids | added_ids

        added = len(combined) - len(old_ids)

        if added > 0:
            expanded += 1

        base_total += len(old_ids)
        added_total += added
        final_total += len(combined)

        if len(combined) > max_final:
            max_final = len(combined)

        writer.writerow([
            s1_id,
            ",".join(sorted(combined))
        ])

        if total % 100000 == 0:
            print(
                f"Merged: {total:,} | "
                f"Expanded: {expanded:,} | "
                f"Added: {added_total:,}"
            )

print()
print("=" * 60)
print("TRAINING V3 CANDIDATE GENERATION COMPLETE")
print("=" * 60)
print(f"S1 rows:              {total:,}")
print(f"Original candidates:  {base_total:,}")
print(f"New candidates:       {added_total:,}")
print(f"Final candidates:     {final_total:,}")
print(f"S1 rows expanded:     {expanded:,}")
print(f"Max candidates/S1:    {max_final:,}")
print(f"Output:               {OUTPUT_PATH}")