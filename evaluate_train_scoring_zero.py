import csv
import os
import re
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

S1_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "train",
    "train_source1.tsv"
)

GT_PATH = os.path.join(
    BASE_DIR,
    "dataset",
    "train",
    "train_ground_truth.tsv"
)

CANDIDATE_PATH = os.path.join(
    BASE_DIR,
    "output",
    "train_candidate_pairs_v3.tsv"
)

DB_PATH = os.path.join(
    BASE_DIR,
    "train_candidate_index.db"
)


def normalize(text):
    if not isinstance(text, str):
        return ""

    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def seq_sim(a, b):
    if not a or not b:
        return 0.0

    if a == b:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


def token_jaccard(a, b):
    ta = set(a.split())
    tb = set(b.split())

    if not ta or not tb:
        return 0.0

    return len(ta & tb) / len(ta | tb)


print("Loading training data...")

s1 = {}

with open(
    S1_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    for row in csv.DictReader(f, delimiter="\t"):

        s1[row["entity_id"]] = (
            row["country"] or "",
            normalize(row["business_name"]),
            normalize(row["business_address"])
        )

ground_truth = {}

with open(
    GT_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    for row in csv.DictReader(f, delimiter="\t"):

        ids = row["matched_entity_ids"]

        ground_truth[row["source1_entity_id"]] = (
            set(ids.split(",")) if ids else set()
        )


print("Loading candidates...")

candidates = {}

with open(
    CANDIDATE_PATH,
    "r",
    encoding="utf-8",
    newline=""
) as f:

    for row in csv.DictReader(f, delimiter="\t"):

        ids = row["candidate_entity_ids"]

        candidates[row["source1_entity_id"]] = (
            ids.split(",") if ids else []
        )


print("Loading candidate records...")

import sqlite3

needed_ids = set()

for ids in candidates.values():
    needed_ids.update(ids)

conn = sqlite3.connect(DB_PATH)

record_map = {}

cursor = conn.execute(
    """
    SELECT entity_id, name_norm, address_norm, country
    FROM records
    """
)

for entity_id, name_norm, address_norm, country in cursor:

    if entity_id in needed_ids:

        record_map[entity_id] = (
            name_norm or "",
            address_norm or "",
            country or ""
        )

conn.close()

print(
    f"Loaded candidate records: "
    f"{len(record_map):,}"
)


print("Creating scored candidate lists...")

# Each entry:
# (S1 id, candidate id, score, is_true)

scored_pairs = []

processed = 0

for s1_id, true_ids in ground_truth.items():

    if not true_ids:
        continue

    s1_row = s1.get(s1_id)

    if s1_row is None:
        continue

    country, s1_name, s1_address = s1_row

    for candidate_id in candidates.get(s1_id, []):

        record = record_map.get(candidate_id)

        if record is None:
            continue

        c_name, c_address, c_country = record

        if c_country != country:
            continue

        name_seq = seq_sim(
            s1_name,
            c_name
        )

        address_seq = seq_sim(
            s1_address,
            c_address
        )

        name_jac = token_jaccard(
            s1_name,
            c_name
        )

        address_jac = token_jaccard(
            s1_address,
            c_address
        )

        scored_pairs.append(
            (
                s1_id,
                candidate_id,
                name_seq,
                address_seq,
                name_jac,
                address_jac,
                candidate_id in true_ids
            )
        )

    processed += 1

    if processed % 100000 == 0:

        print(
            f"Processed S1: {processed:,}"
        )


print(
    f"Scored candidate pairs: "
    f"{len(scored_pairs):,}"
)


# ---------------------------------------------------------
# Evaluation
# ---------------------------------------------------------

def evaluate(
    weight_name_seq,
    weight_address_seq,
    weight_name_jac,
    weight_address_jac,
    threshold
):

    best_by_s1 = {}

    for (
        s1_id,
        candidate_id,
        name_seq,
        address_seq,
        name_jac,
        address_jac,
        is_true
    ) in scored_pairs:

        score = (
            weight_name_seq * name_seq
            +
            weight_address_seq * address_seq
            +
            weight_name_jac * name_jac
            +
            weight_address_jac * address_jac
        )

        current = best_by_s1.get(s1_id)

        if current is None or score > current[0]:

            best_by_s1[s1_id] = (
                score,
                candidate_id,
                is_true
            )

    tp = 0
    fp = 0
    fn = 0

    for s1_id, true_ids in ground_truth.items():

        if not true_ids:
            continue

        prediction = best_by_s1.get(s1_id)

        if prediction is None:
            fn += len(true_ids)
            continue

        score, candidate_id, is_true = prediction

        if score >= threshold:

            if is_true:
                tp += 1
            else:
                fp += 1

            # We predict only one entity here.
            fn += max(
                0,
                len(true_ids) - 1
            )

        else:

            fn += len(true_ids)

    if tp + fp == 0:
        precision = 0.0
    else:
        precision = tp / (tp + fp)

    if tp + fn == 0:
        recall = 0.0
    else:
        recall = tp / (tp + fn)

    if precision + recall == 0:
        f05 = 0.0
    else:
        f05 = (
            1.25
            * precision
            * recall
            /
            (0.25 * precision + recall)
        )

    return (
        f05,
        precision,
        recall,
        tp,
        fp,
        fn
    )


experiments = [
    (
        "ADDRESS_SEQ",
        0.10, 0.70, 0.05, 0.15
    ),
    (
        "ADDRESS_JAC",
        0.10, 0.15, 0.05, 0.70
    ),
    (
        "ADDRESS_HEAVY",
        0.10, 0.55, 0.10, 0.25
    ),
    (
        "ADDRESS_BALANCED",
        0.15, 0.45, 0.10, 0.30
    ),
    (
        "ALL_EQUAL",
        0.25, 0.25, 0.25, 0.25
    ),
    (
        "NAME_SEQ_ADDRESS_JAC",
        0.20, 0.10, 0.10, 0.60
    )
]


print()
print("Testing scoring strategies...")
print()


thresholds = [
    0.70,
    0.75,
    0.80,
    0.82,
    0.84,
    0.86,
    0.88,
    0.90,
    0.92,
    0.94
]

results = []

for (
    name,
    w_ns,
    w_as,
    w_nj,
    w_aj
) in experiments:

    for threshold in thresholds:

        result = evaluate(
            w_ns,
            w_as,
            w_nj,
            w_aj,
            threshold
        )

        f05, precision, recall, tp, fp, fn = result

        results.append(
            (
                f05,
                precision,
                recall,
                name,
                threshold,
                tp,
                fp,
                fn
            )
        )


results.sort(
    key=lambda x: x[0],
    reverse=True
)


print()
print("TOP SCORING STRATEGIES")
print("======================")

for result in results[:20]:

    (
        f05,
        precision,
        recall,
        name,
        threshold,
        tp,
        fp,
        fn
    ) = result

    print(
        f"{name:24s} "
        f"threshold={threshold:.2f} "
        f"F0.5={f05:.4f} "
        f"P={precision:.4f} "
        f"R={recall:.4f} "
        f"TP={tp:,} "
        f"FP={fp:,} "
        f"FN={fn:,}"
    )


print()
print("Evaluation complete.")