import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

S1_PATH = os.path.join(BASE_DIR, "dataset", "test", "test_source1.tsv")
S2_PATH = os.path.join(BASE_DIR, "dataset", "test", "test_source2.tsv")
S3_PATH = os.path.join(BASE_DIR, "dataset", "test", "test_source3.tsv")

CANDIDATE_PATH = os.path.join(
    BASE_DIR, "output", "candidate_pairs.tsv"
)

V2_PATH = os.path.join(
    BASE_DIR, "output", "matching_results_v2.tsv"
)

V4_PATH = os.path.join(
    BASE_DIR, "output", "matching_results_v4.tsv"
)


def load_table(path):
    result = {}

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            result[row["entity_id"]] = row

    return result


def load_matches(path):
    result = {}

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")

        for row in reader:
            if row["matched_entity_ids"]:
                result[row["source1_entity_id"]] = row["matched_entity_ids"].split(",")

    return result


print("Loading source tables...")
s1 = load_table(S1_PATH)
s2 = load_table(S2_PATH)
s3 = load_table(S3_PATH)

print("Loading V2...")
v2 = load_matches(V2_PATH)

print("Loading V4...")
v4 = load_matches(V4_PATH)

v2_only = {
    sid: ids
    for sid, ids in v2.items()
    if sid not in v4
}

print(f"V2-only: {len(v2_only):,}")


shown = 0

with open(CANDIDATE_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:

        sid = row["source1_entity_id"]

        if sid not in v2_only:
            continue

        candidate_ids = row["candidate_entity_ids"].split(",")

        if len(candidate_ids) <= 20:
            continue

        print()
        print("=" * 100)

        r1 = s1[sid]

        print("S1:", sid)
        print("Country:", r1["country"])
        print("Name:", r1["business_name"])
        print("Address:", r1["business_address"])

        print()
        print("V2 MATCHES:")

        for mid in v2_only[sid]:
            if mid.startswith("S2-"):
                r = s2.get(mid)
            else:
                r = s3.get(mid)

            if r:
                print(" ", mid)
                print("    Name:", r["business_name"])
                print("    Address:", r["business_address"])

        shown += 1

        if shown >= 5:
            break


print()
print("Shown:", shown)