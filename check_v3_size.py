import csv

path = r"output\candidate_pairs_v3.tsv"

rows = 0
total = 0
maxc = 0
over100 = 0
over500 = 0
over1000 = 0

with open(path, encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        rows += 1

        n = len(row["candidate_entity_ids"].split(",")) if row["candidate_entity_ids"] else 0

        total += n
        maxc = max(maxc, n)

        if n > 100:
            over100 += 1
        if n > 500:
            over500 += 1
        if n > 1000:
            over1000 += 1

print("Rows:", rows)
print("Total candidates:", total)
print("Max candidates:", maxc)
print("Rows >100:", over100)
print("Rows >500:", over500)
print("Rows >1000:", over1000)
