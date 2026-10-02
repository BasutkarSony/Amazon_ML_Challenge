import csv

GT_PATH = r"dataset\train\train_ground_truth.tsv"
CAND_PATH = r"output\train_candidate_pairs_v3.tsv"

print("Loading ground truth...")

gt = {}

with open(GT_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        s1 = row["source1_entity_id"]
        raw = row["matched_entity_ids"]

        if not raw:
            gt[s1] = set()
        else:
            gt[s1] = set(
                x.strip()
                for x in raw.split(",")
                if x.strip()
            )

print("Ground-truth S1:", len(gt))

print("Checking candidates...")

seen = {}
total_candidate_links = 0

with open(CAND_PATH, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        s1 = row["source1_entity_id"]

        candidates = set(
            x.strip()
            for x in row["candidate_entity_ids"].split(",")
            if x.strip()
        )

        seen[s1] = candidates
        total_candidate_links += len(candidates)

print("Candidate links:", total_candidate_links)

total_true = 0
covered_true = 0
s1_with_missed = 0

for s1, actual in gt.items():

    if not actual:
        continue

    total_true += len(actual)

    candidates = seen.get(s1, set())

    covered = actual & candidates

    covered_true += len(covered)

    if len(covered) < len(actual):
        s1_with_missed += 1

print()
print("RESULT")
print("======")
print("Total true links:", total_true)
print("True links inside candidates:", covered_true)
print("Missed true links:", total_true - covered_true)
print("Candidate recall:", covered_true / total_true)
print("S1 with at least one missed true link:", s1_with_missed)