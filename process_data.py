#!/usr/bin/env python3
"""Process HCRA Ontario builder data into a single JSON for the static web UI."""

import json
import os
import statistics


def load_json_safe(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def to_int(val):
    try:
        return max(0, int(float(val or 0)))
    except Exception:
        return 0


STATUS_PENALTIES = {
    "Licensed": 0.0,
    "Licensed with Conditions": -0.3,
    "Expired": -0.5,
    "Resigned": -0.3,
    "Refused": -1.0,
    "Revoked": -2.0,
    "Suspended": -1.5,
    "NULL/TarionConviction": -1.5,
    "Unlicensed": -0.5,
    "NULL/UMBRELLA": 0.0,
}


def compute_score(homes, cc, minor, major, convictions, has_conditions, has_breach, status):
    score = 5.0

    if homes > 0:
        cc_rate = cc / homes
        minor_rate = minor / homes
        major_rate = major / homes
        # Conciliation rate: 10% rate = -1.0, max -1.5
        score -= min(cc_rate * 10, 1.5)
        # Minor claims: 10% rate = -0.8, max -1.0
        score -= min(minor_rate * 8, 1.0)
        # Major claims: weighted more heavily, max -1.5
        score -= min(major_rate * 15, 1.5)

    # Convictions: -0.4 each, max -2.0
    score -= min(convictions * 0.4, 2.0)

    if has_conditions:
        score -= 0.3

    if has_breach:
        score -= 1.0

    score += STATUS_PENALTIES.get(status, -0.5)

    return round(max(0.5, min(5.0, score)), 2)


def main():
    os.makedirs("docs", exist_ok=True)

    print("Loading umbrella data...")
    umbrella_cache = {}
    for fname in os.listdir("Umbrella"):
        uid = fname.replace(".json", "")
        data = load_json_safe(f"Umbrella/{fname}")
        if data:
            umbrella_cache[uid] = data

    print(f"Loaded {len(umbrella_cache)} umbrella files")

    print("Loading builders list...")
    with open("builders.json") as f:
        builders_list = json.load(f)

    print(f"Processing {len(builders_list)} builders...")

    output_builders = []

    for idx, binfo in enumerate(builders_list):
        if idx % 5000 == 0:
            print(f"  {idx}/{len(builders_list)}...")

        account = binfo.get("ACCOUNTNUMBER") or ""
        name = binfo.get("NAME") or "Unknown"
        op_name = binfo.get("OPERATINGNAME")
        city = binfo.get("ADDRESS_2_CITY") or ""
        status = binfo.get("LICENSESTATUS") or "Unknown"

        homes = 0
        cc = 0
        minor = 0
        major = 0
        convictions = 0
        has_conditions = False
        has_breach = False
        umbrella_id = None
        umbrella_name = None
        address = ""
        phone = ""
        website = ""
        email = ""

        if status == "NULL/UMBRELLA":
            data = umbrella_cache.get(str(account))
            if data:
                summ_list = data.get("umbrellaSummary", [])
                s = summ_list[0] if summ_list else {}
                homes = to_int(s.get("SUMM_TOTAL"))
                cc = to_int(s.get("SUMM_CC"))
                minor = to_int(s.get("SUMM_MINOR"))
                major = to_int(s.get("SUMM_MAJOR"))
                has_breach = bool(to_int(s.get("BREACH")))
                address = s.get("ADDRESS") or ""
                phone = s.get("TELEPHONE") or ""
                website = s.get("WEBSITEURL") or ""
                email = s.get("EMAIL") or ""
        else:
            data = load_json_safe(f"Builder/{account}.json")
            if data:
                summ_list = data.get("builderSummary", [])
                s = summ_list[0] if summ_list else {}
                homes = to_int(s.get("SUMM_TOTAL"))
                cc = to_int(s.get("SUMM_CC"))
                minor = to_int(s.get("SUMM_MINOR"))
                major = to_int(s.get("SUMM_MAJOR"))
                has_breach = bool(to_int(s.get("BREACH")))
                address = s.get("ADDRESS") or ""
                phone = s.get("TELEPHONE") or ""
                website = s.get("WEBSITEURL") or ""
                email = s.get("EMAIL") or ""

                umbrella_id_raw = s.get("Umbrella ID")
                umbrella_name = s.get("Umbrella")
                if umbrella_id_raw and str(umbrella_id_raw) not in ("None", "null", ""):
                    umbrella_id = str(umbrella_id_raw)

                convictions = len(data.get("builderConvictions") or [])
                has_conditions = bool(data.get("builderConditions"))

                # If part of umbrella, use umbrella's aggregate stats for scoring
                if umbrella_id and umbrella_id in umbrella_cache:
                    umb = umbrella_cache[umbrella_id]
                    us_list = umb.get("umbrellaSummary", [])
                    us = us_list[0] if us_list else {}
                    homes = to_int(us.get("SUMM_TOTAL")) or homes
                    cc = to_int(us.get("SUMM_CC")) or cc
                    minor = to_int(us.get("SUMM_MINOR")) or minor
                    major = to_int(us.get("SUMM_MAJOR")) or major

        score = compute_score(homes, cc, minor, major, convictions, has_conditions, has_breach, status)

        entry = {
            "id": account,
            "n": name,
            "c": city,
            "st": status,
            "sc": score,
            "h": homes,
            "cc": cc,
            "mi": minor,
            "ma": major,
            "cv": convictions,
        }
        if op_name:
            entry["op"] = op_name
        if umbrella_id:
            entry["uid"] = umbrella_id
        if umbrella_name:
            entry["un"] = umbrella_name
        if has_conditions:
            entry["cond"] = True
        if has_breach:
            entry["br"] = True
        if address:
            entry["addr"] = address
        if phone:
            entry["ph"] = phone
        if website and website.strip():
            entry["web"] = website.strip()
        if email:
            entry["em"] = email

        output_builders.append(entry)

    scores = [b["sc"] for b in output_builders]
    avg_score = round(statistics.mean(scores), 2)
    median_score = round(statistics.median(scores), 2)

    output = {
        "builders": output_builders,
        "stats": {
            "total": len(output_builders),
            "avg": avg_score,
            "median": median_score,
        },
    }

    out_path = "docs/data.json"
    print(f"Writing {out_path}...")
    with open(out_path, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    size_mb = os.path.getsize(out_path) / 1024 / 1024
    print(f"Done! {len(output_builders)} builders, avg={avg_score}, median={median_score}")
    print(f"Output size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
