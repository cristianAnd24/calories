"""Build foods.json, the app's offline food database, from USDA FoodData Central.

Expects the JSON downloads from https://fdc.nal.usda.gov/download-datasets/
(public domain), either the .zip as downloaded or the single .json inside it:

  SR Legacy, April 2018 (final release; will not change)
    https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip
  FNDDS 2021-2023 (Survey foods), FDC release 2024-10-31
    https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_json_2024-10-31.zip

A newer FNDDS release should drop in unchanged; the release label in "source" is
read from the data. The script checks every nutrient id and unit it uses against
the files and stops if one has changed.

Usage (stdlib only; run with -I since the inputs are downloaded files):
  python -I tools/build_foods.py SR_LEGACY.zip FNDDS.zip foods.json

Output: {"v","built","source","n","u","foods"}, each food being
[fdc_id, description, "s"|"f", nutrients per 100 g (null = not measured),
 [[portion label, grams], ...]].
"""

import argparse
import datetime
import gzip
import json
import re
import sys
import zipfile
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

# key, unit written to "u", FDC nutrient ids in order of preference, unit in the data
NUTRIENTS = [
    ("kcal", "kcal", (1008, 2047, 2048), "kcal"),
    ("protein", "g", (1003,), "g"),
    ("fat", "g", (1004,), "g"),
    ("carbs", "g", (1005,), "g"),
    ("fiber", "g", (1079,), "g"),
    ("sugar", "g", (2000, 1063), "g"),
    ("satfat", "g", (1258,), "g"),
    ("sodium", "mg", (1093,), "mg"),
    ("potassium", "mg", (1092,), "mg"),
    ("calcium", "mg", (1087,), "mg"),
    ("iron", "mg", (1089,), "mg"),
    ("magnesium", "mg", (1090,), "mg"),
    ("zinc", "mg", (1095,), "mg"),
    ("vitA", "µg", (1106,), "µg"),     # RAE
    ("vitC", "mg", (1162,), "mg"),
    ("vitD", "µg", (1114,), "µg"),     # D2 + D3
    ("vitE", "mg", (1109,), "mg"),               # alpha-tocopherol
    ("vitK", "µg", (1185,), "µg"),     # phylloquinone
    ("vitB12", "µg", (1178,), "µg"),
    ("folate", "µg", (1190,), "µg"),   # DFE
]
MAX_PORTIONS = 6

ONE = Decimal("1")
TENTH = Decimal("0.1")


def load(path, key):
    """Read the food list from a downloaded .zip or the .json inside it."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".json")]
            if len(names) != 1:
                sys.exit(f"{path}: expected one .json inside, found {names}")
            with z.open(names[0]) as f:
                data = json.load(f)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    if key not in data:
        sys.exit(f"{path}: no top-level {key!r} (found {list(data)})")
    return data[key]


def num(x, places=TENTH):
    """Round half-up on the decimal value as written, and emit 12 rather than 12.0."""
    d = Decimal(repr(float(x))).quantize(places, rounding=ROUND_HALF_UP)
    return int(d) if d == d.to_integral_value() else float(d)


def check_units(foods, seen):
    """Record the (name, unit) each nutrient id carries, to verify against NUTRIENTS."""
    for food in foods:
        for fn in food.get("foodNutrients", []):
            n = fn.get("nutrient") or {}
            seen.setdefault(n.get("id"), set()).add((n.get("name"), n.get("unitName")))


def nutrients(food):
    by_id = {}
    for fn in food.get("foodNutrients", []):
        amount = fn.get("amount")
        nid = (fn.get("nutrient") or {}).get("id")
        if amount is not None and nid is not None:
            by_id[nid] = amount
    out = []
    for key, _unit, ids, _data_unit in NUTRIENTS:
        v = next((by_id[i] for i in ids if i in by_id), None)
        if v is None:
            out.append(None)              # not measured: never 0
        else:
            out.append(num(v, ONE) if key == "kcal" else num(v))
    return out


FRACTIONS = {
    Decimal("0.08"): "1/12", Decimal("0.1"): "1/10", Decimal("0.12"): "1/8",
    Decimal("0.125"): "1/8", Decimal("0.16"): "1/6", Decimal("0.2"): "1/5",
    Decimal("0.25"): "1/4", Decimal("0.33"): "1/3", Decimal("0.5"): "1/2",
    Decimal("0.66"): "2/3", Decimal("0.67"): "2/3", Decimal("0.75"): "3/4",
}


def amount_text(a):
    """1.0 -> "1", 0.5 -> "1/2", 1.5 -> "1 1/2", 3.52 -> "3.52" (FNDDS writes fractions)."""
    d = Decimal(repr(float(a))).normalize()
    whole = int(d)
    frac = d - whole
    if frac == 0:
        return str(whole)
    if frac in FRACTIONS:
        return f"{whole} {FRACTIONS[frac]}" if whole else FRACTIONS[frac]
    return format(d, "f")


LEADING_QTY = re.compile(r"^\s*[\d.]+(?:[ -]\d+/\d+|/\d+)?\s+")
RANKS = [  # lower is shown first; ties keep USDA's own order
    (4, re.compile(r"^(cubic|surface|linear) inch|^(quarts?|pints?|gallons?|liters?|litres?)\b|\bpot\b(?! pie)", re.I)),
    (3, re.compile(r"^(fl\.? ?oz|oz|ounces?|lbs?|pounds?|g|grams?|kg)\b", re.I)),
    (2, re.compile(r"^(extra[- ]?large|extra[- ]?small|jumbo|very large)\b", re.I)),
    (1, re.compile(r"^(cups?|tbsp|tablespoons?|tsp|teaspoons?|ml|milliliters?)\b", re.I)),
    (1, re.compile(r"^([\w-]+ ){0,3}(containers?|packages?|cans?|bottles?|jars?|bags?|packets?"
                   r"|box(es)?|pouch(es)?|tubs?|cartons?|envelopes?)\b", re.I)),
]


def rank(label):
    """Natural units (1 large, 1 slice, 1 banana) first, then spoons, cups and
    packaging, then outlying sizes, then weights and fl oz (grams cover those),
    then inches, quarts and pots."""
    measure = LEADING_QTY.sub("", label)
    return next((r for r, rx in RANKS if rx.search(measure)), 0)


def portions(food, source, dropped):
    rows = []
    for p in food.get("foodPortions", []):
        grams = p.get("gramWeight")
        if grams is None or num(grams) <= 0:   # checked after rounding: a 0.03 g tablet is 0
            dropped["grams<=0"] += 1
            continue
        if source == "s":
            amount = p.get("amount")
            modifier = (p.get("modifier") or "").strip()
            if not amount or amount <= 0:     # 18 SR rows say "0 cup" etc.: unusable
                dropped["SR amount 0"] += 1
                continue
            if not modifier:
                dropped["no label"] += 1
                continue
            label = f"{amount_text(amount)} {modifier}"
        else:
            label = (p.get("portionDescription") or "").strip()
            if label == "Quantity not specified":
                dropped["Quantity not specified"] += 1
                continue
            if label.startswith("Guideline amount"):   # recipe add-on amounts, not servings
                dropped["FNDDS guideline amount"] += 1
                continue
            if not label:
                dropped["no label"] += 1
                continue
        rows.append((rank(label), p.get("sequenceNumber") or 0, label, num(grams)))
    rows.sort(key=lambda r: (r[0], r[1]))
    out, seen = [], set()
    for _r, _s, label, grams in rows:
        if label.casefold() in seen:
            dropped["duplicate label"] += 1
            continue
        seen.add(label.casefold())
        out.append([label, grams])
    dropped["over limit"] += max(0, len(out) - MAX_PORTIONS)
    return out[:MAX_PORTIONS]


def fndds_is_infant(food):
    """WWEIA 9002-9602: baby foods, baby juice/water, infant formula, human milk."""
    for a in food.get("foodAttributes", []):
        if a.get("name") == "WWEIA Category number":
            try:
                return 9000 <= int(a.get("value")) < 9800
            except (TypeError, ValueError):
                pass
    cat = (food.get("wweiaFoodCategory") or {}).get("wweiaFoodCategoryDescription") or ""
    return cat.startswith(("Baby", "Formula", "Human milk"))


def sr_is_infant(food):
    return (food.get("foodCategory") or {}).get("description") == "Baby Foods"


def fndds_release(foods):
    def year(s):
        return (s or "").rsplit("/", 1)[-1]
    start = min((year(f.get("startDate")) for f in foods), default="")
    end = max((year(f.get("endDate")) for f in foods), default="")
    pub = Counter(f.get("publicationDate") for f in foods).most_common(1)[0][0]
    m, d, y = pub.split("/")
    return f"{start}-{end}, published {y}-{int(m):02d}-{int(d):02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sr", help="SR Legacy JSON download (.zip or .json)")
    ap.add_argument("fndds", help="FNDDS / Survey foods JSON download (.zip or .json)")
    ap.add_argument("out", help="output path, e.g. foods.json")
    args = ap.parse_args()

    sr = load(args.sr, "SRLegacyFoods")
    fndds = load(args.fndds, "SurveyFoods")

    seen = {}
    check_units(sr, seen)
    check_units(fndds, seen)
    bad = []
    for key, _unit, ids, data_unit in NUTRIENTS:
        present = [i for i in ids if i in seen]
        if not present:
            bad.append(f"{key}: none of {ids} occur in the data")
        for i in present:
            units = {u for _n, u in seen[i]}
            if units != {data_unit}:
                bad.append(f"{key}: id {i} has unit(s) {units}, expected {data_unit}")
    if bad:
        sys.exit("Nutrient table changed:\n  " + "\n  ".join(bad))

    foods, skipped, dropped = [], Counter(), Counter()
    for source, items, infant in (("s", sr, sr_is_infant), ("f", fndds, fndds_is_infant)):
        for food in items:
            if infant(food):
                skipped[source + " infant/baby"] += 1
                continue
            n = nutrients(food)
            if n[0] is None:
                skipped[source + " no kcal"] += 1
                continue
            foods.append([food["fdcId"], food["description"].strip(), source, n,
                          portions(food, source, dropped)])
    foods.sort(key=lambda f: (f[1].casefold(), f[1], f[0]))

    doc = {
        "v": 1,
        "built": datetime.date.today().isoformat(),
        "source": "USDA FoodData Central — SR Legacy (2018-04) and FNDDS "
                  f"({fndds_release(fndds)}). Public domain.",
        "n": [k for k, *_ in NUTRIENTS],
        "u": [u for _k, u, *_ in NUTRIENTS],
        "foods": foods,
    }
    raw = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    with open(args.out, "wb") as f:
        f.write(raw)

    count = Counter(f[2] for f in foods)
    print(f"wrote {args.out}: {len(foods)} foods (SR {count['s']}, FNDDS {count['f']})")
    print(f"size: {len(raw):,} B raw, {len(gzip.compress(raw, 6)):,} B gzip -6, "
          f"{len(gzip.compress(raw, 9)):,} B gzip -9")
    print("skipped:", dict(skipped))
    print("portions dropped:", dict(dropped))
    print("non-null per nutrient (all / SR / FNDDS):")
    for i, key in enumerate(doc["n"]):
        per = Counter(f[2] for f in foods if f[3][i] is not None)
        print(f"  {key:10} {per['s'] + per['f']:6} {per['s']:6} {per['f']:6}")


if __name__ == "__main__":
    main()
