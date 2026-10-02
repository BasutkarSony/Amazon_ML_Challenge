import os
import re
import csv
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

OUTPUT_PATH = os.path.join(
    BASE_DIR, "output", "matching_results_all_equal.tsv"
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


def token_jaccard(a, b):
    if not a or not b:
        return 0.0

    sa = set(a.split())
    sb = set(b.split())

    if not sa or not sb:
        return 0.0

    return len(sa & sb) / len(sa | sb)


print("Loading candidate pairs...")

candidates = {}

with open(
    CANDIDATE_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        ids = row["candidate_entity_ids"]

        candidates[row["source1_entity_id"]] = (
            ids.split(",") if ids else []
        )

print("Loaded", len(candidates), "candidate lists.")

print("Loading Source-1...")

source1 = {}

with open(
    S1_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        sid = row["entity_id"]

        source1[sid] = (
            normalize(row.get("business_name", "")),
            normalize(row.get("business_address", ""))
        )

print("Loaded", len(source1), "Source-1 records.")

print("Loading candidate records...")

conn = sqlite3.connect(DB_PATH)

candidate_ids = set()

for ids in candidates.values():
    candidate_ids.update(ids)

print("Unique candidate IDs:", len(candidate_ids))

placeholders = ",".join("?" for _ in candidate_ids)

records = {}

if candidate_ids:
    cur = conn.cursor()
    candidate_ids = list(candidate_ids)

    for start in range(0, len(candidate_ids), 500):
        batch = candidate_ids[start:start + 500]

        placeholders = ",".join("?" for _ in batch)

        query = f"""
            SELECT entity_id, name_norm, address_norm
            FROM records
            WHERE entity_id IN ({placeholders})
        """

        for row in cur.execute(query, batch):
            records[row[0]] = (
                normalize(row[1]),
                normalize(row[2])
            )

        if start % 50000 == 0:
            print(
                f"Loaded candidate records: "
                f"{min(start + 500, len(candidate_ids))}/{len(candidate_ids)}"
            )

conn.close()

print("Loaded", len(records), "candidate records.")

print("Scoring...")

with open(
    OUTPUT_PATH,
    "w",
    encoding="utf-8",
    newline=""
) as f:

    writer = csv.writer(f, delimiter="\t")

    writer.writerow([
        "source1_entity_id",
        "matched_entity_ids"
    ])

    matched_count = 0

    for idx, (sid, candidate_list) in enumerate(candidates.items(), 1):

        s1_name, s1_address = source1.get(
            sid,
            ("", "")
        )

        scored = []

        for cid in candidate_list:

            rec = records.get(cid)

            if not rec:
                continue

            c_name, c_address = rec

            name_seq = similarity(s1_name, c_name)
            address_seq = similarity(s1_address, c_address)

            name_jac = token_jaccard(s1_name, c_name)
            address_jac = token_jaccard(
                s1_address,
                c_address
            )

            score = (
                0.25 * name_seq +
                0.25 * address_seq +
                0.25 * name_jac +
                0.25 * address_jac
            )

            scored.append((cid, score))

        matches = []

        if scored:

            scored.sort(
                key=lambda x: x[1],
                reverse=True
            )

            best_id, best_score = scored[0]

            # Same threshold as the best training experiment.
            if best_score >= 0.70:

                matches.append(best_id)

                for cid, score in scored[1:]:

                    if (
                        score >= 0.85
                        and best_score - score <= 0.05
                    ):
                        matches.append(cid)

        if matches:
            matched_count += 1

        writer.writerow([
            sid,
            ",".join(matches)
        ])

        if idx % 100000 == 0:
            print(
                f"Processed {idx}/{len(candidates)} "
                f"| matched={matched_count}"
            )

print()
print("Done.")
print("Source 1 records:", len(candidates))
print("Matched records:", matched_count)
print("Coverage:", matched_count / len(candidates))
print("Output:", OUTPUT_PATH)