import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

V2_PATH = os.path.join(
    BASE_DIR, "output", "matching_results_v2.tsv"
)

V4_CANDIDATE_PATH = os.path.join(
    BASE_DIR, "output", "candidate_pairs_v4.tsv"
)

# Load V2 matches
v2_matches = {}

with open(V2_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        ids = row["matched_entity_ids"]

        if ids:
            v2_matches[row["source1_entity_id"]] = set(
                ids.split(",")
            )

print(f"Loaded V2 matched S1 records: {len(v2_matches):,}")

checked = 0
present = 0
missing = 0

examples = []

# Check whether V2's selected IDs exist in V4 candidate lists
with open(
    V4_CANDIDATE_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:

        s1_id = row["source1_entity_id"]

        if s1_id not in v2_matches:
            continue

        checked += 1

        candidate_ids = set(
            row["candidate_entity_ids"].split(",")
            if row["candidate_entity_ids"]
            else []
        )

        v2_ids = v2_matches[s1_id]

        if v2_ids.issubset(candidate_ids):
            present += 1
        else:
            missing += 1

            if len(examples) < 20:
                missing_ids = sorted(v2_ids - candidate_ids)

                examples.append(
                    (s1_id, missing_ids)
                )

print()
print("V2 match membership in V4 candidates")
print("--------------------------------------")
print(f"V2 matched S1 checked: {checked:,}")
print(f"All V2 matches present: {present:,}")
print(f"At least one V2 match missing: {missing:,}")

print()
print("Examples where V2 match is missing:")

for s1_id, missing_ids in examples:
    print(
        f"S1={s1_id} | "
        f"missing={','.join(missing_ids)}"
    )