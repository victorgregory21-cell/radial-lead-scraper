"""Run the existing radial lead scraper across major Malaysian cities.

Research only: does not send mail. Results are not verified delivery addresses.
Usage: python malaysia_scan.py --type "office" --limit 25 --fast
"""
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

LOCATIONS = [
    ("Johor", "Johor Bahru"), ("Johor", "Batu Pahat"),
    ("Kedah", "Alor Setar"), ("Kedah", "Sungai Petani"),
    ("Kelantan", "Kota Bharu"), ("Melaka", "Melaka"),
    ("Negeri Sembilan", "Seremban"), ("Negeri Sembilan", "Nilai"),
    ("Pahang", "Kuantan"), ("Pahang", "Temerloh"),
    ("Perak", "Ipoh"), ("Perak", "Taiping"),
    ("Perlis", "Kangar"),
    ("Pulau Pinang", "George Town"), ("Pulau Pinang", "Butterworth"),
    ("Sabah", "Kota Kinabalu"), ("Sabah", "Sandakan"), ("Sabah", "Tawau"),
    ("Sarawak", "Kuching"), ("Sarawak", "Miri"), ("Sarawak", "Sibu"),
    ("Selangor", "Petaling Jaya"), ("Selangor", "Shah Alam"),
    ("Selangor", "Klang"), ("Selangor", "Subang Jaya"),
    ("Terengganu", "Kuala Terengganu"),
    ("Kuala Lumpur", "Kuala Lumpur"),
    ("Putrajaya", "Putrajaya"),
    ("Labuan", "Victoria, Labuan"),
]
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
COLUMNS = ["State", "City", "Business Name", "Business Type", "Address", "Domain",
           "Public Email", "Email Sources", "Phone Number", "Source"]


def main():
    p = argparse.ArgumentParser(description="Nationwide Malaysia business email research; no emailing")
    p.add_argument("--type", required=True, help="Business category supported by radial_lead_scraper.py")
    p.add_argument("--limit", type=int, default=25, help="Max businesses per city, default 25")
    p.add_argument("--radius-km", type=float, default=20)
    p.add_argument("--fast", action="store_true")
    p.add_argument("--output", default="malaysia_public_business_contacts.csv")
    p.add_argument("--opt-outs", default="malaysia_do_not_email.csv",
                   help="Required private CSV with an email column to exclude opt-outs")
    args = p.parse_args()
    if not 1 <= args.limit <= 100 or not 1 <= args.radius_km <= 50:
        p.error("--limit must be 1..100 and --radius-km 1..50")

    excluded = set()
    optout_path = Path(args.opt_outs)
    if not optout_path.exists():
        p.error(f"Missing private suppression list: {optout_path}. Create a CSV with an email header and all opt-outs before scanning.")
    if optout_path.exists():
        with optout_path.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                value = (row.get("email") or row.get("Email") or "").strip().lower()
                if value:
                    excluded.add(value)

    tmp = Path("malaysia_scan_parts")
    tmp.mkdir(exist_ok=True)
    combined, seen = [], set()
    for state, city in LOCATIONS:
        filename = tmp / (re.sub(r"[^a-z0-9]+", "_", f"{state}_{city}".lower()) + ".csv")
        command = [sys.executable, str(Path(__file__).with_name("radial_lead_scraper.py")),
                   "--address", f"{city}, {state}, Malaysia",
                   "--type", args.type, "--radius-km", str(args.radius_km),
                   "--limit", str(args.limit), "--workers", "4",
                   "--output", str(filename)]
        if args.fast:
            command.append("--fast")
        print(f"Searching {city}, {state}...", flush=True)
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            print(f"Skipping failed search in {city}: {exc}", file=sys.stderr)
            continue
        if not filename.exists():
            continue
        with filename.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                # Only include emails explicitly found on public websites/OSM.
                found = row.get("Real Found Emails") or row.get("Public Emails") or ""
                for email in re.split(r"\s*\|\s*", found):
                    email = email.strip().lower()
                    if not EMAIL_RE.fullmatch(email) or email in excluded:
                        continue
                    key = (email, (row.get("Business Name") or "").strip().lower())
                    if key in seen:
                        continue
                    seen.add(key)
                    combined.append({
                        "State": state, "City": city,
                        "Business Name": row.get("Business Name", ""),
                        "Business Type": row.get("Business Type", args.type),
                        "Address": row.get("Address", ""),
                        "Domain": row.get("Domain", ""),
                        "Public Email": email,
                        "Email Sources": row.get("Email Sources", ""),
                        "Phone Number": row.get("Phone Number", ""),
                        "Source": row.get("Source", ""),
                    })
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(combined)
    print(f"Wrote {len(combined)} publicly found contacts to {args.output}")
    print("No emails have been sent. Review accuracy, consent and local requirements before outreach.")


if __name__ == "__main__":
    main()
