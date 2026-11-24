# Malaysia-wide business contact discovery

This fork includes `malaysia_scan.py`, a research-only wrapper around the project's existing location-based scraper. It searches multiple Malaysian city centers and consolidates **publicly found** business email addresses to CSV.

Coverage includes **all 13 Malaysian states and all three federal territories** through 29 city/area seeds. This is a starting point, not an exhaustive census of every company or district. It does **not** send email.

## Setup
Follow the main README to install the scraper's Python dependencies.

Before any run, create a **private** `malaysia_do_not_email.csv` file in the working directory. It must have one column named `email` and must contain all opt-outs from Myroomzie and other exclusion lists. The file is ignored by Git and must never be committed. The scanner refuses to run if it is missing.

## Usage

```bash
python malaysia_scan.py --type "office" --limit 25 --radius-km 20 --fast
```

To research other sectors, change `--type` to a supported category such as `clinic`, `restaurant`, `hotel`, or `coworking` and run again with a distinct `--output`. The underlying tool's OpenStreetMap tag coverage varies by category; unknown types may yield few results.

The consolidated output is `malaysia_public_business_contacts.csv`. Review source URLs, company relevance, address quality and opt-outs before using these records. Addresses are **not** guaranteed valid or deliverable. Do not treat generated email permutations as verified.

This tool should be used for lawful business research and permission-based outreach, not unsolicited mass mailing. Respect platform rate limits, website terms and applicable Malaysian requirements.
