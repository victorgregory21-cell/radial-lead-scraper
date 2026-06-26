# Radial Lead Scraper

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![No API Keys](https://img.shields.io/badge/API%20keys-not%20required-brightgreen.svg)](#data-sources)
[![Free & Open Source](https://img.shields.io/badge/free%20%26%20open--source-yes-brightgreen.svg)](LICENSE)

Author: Elroy Jahjaloo

Radial Lead Scraper is a free, API-keyless, worldwide lead discovery and enrichment tool. It starts from a seed address, finds nearby businesses of a chosen type through OpenStreetMap/Overpass, sorts them by distance, then enriches each lead with a likely official domain, decision-maker name, generated email permutations, public emails, and phone numbers.

No paid APIs, API keys, browser accounts, or SaaS subscriptions are required.

## Features

- Worldwide radial search from any address or public landmark
- Free geocoding via Nominatim
- Free business discovery via Overpass/OpenStreetMap
- Free web search via `ddgs`
- Concurrent enrichment with configurable worker count
- Official-domain discovery with directory/OTA/social blocklist filtering
- Decision-maker discovery from public search snippets
- Corporate email permutation generation
- Public website email and phone scraping
- CSV output designed for CRM/import workflows
- Graceful handling of bad addresses and zero-result searches

## Install

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install as a local CLI package:

```bash
python -m pip install .
radial-leads --help
```

Install with dashboard dependencies:

```bash
python -m pip install ".[dashboard]"
```

## Quick Start

```bash
python radial_lead_scraper.py \
  --address "Marina Bay Sands Singapore" \
  --type "hotel" \
  --radius-km 5 \
  --limit 25 \
  --workers 8 \
  --fast
```

If installed with `pip install .`, use the CLI command:

```bash
radial-leads --address "Marina Bay Sands Singapore" --type "hotel" --radius-km 5 --limit 25 --workers 8 --fast
```

By default, the output file is generated automatically using the business type and address, for example:

```text
leads_hotel_marina_bay_sands_singapore.csv
```

Use `--output` to choose a file name:

```bash
python radial_lead_scraper.py --address "Raffles Place Singapore" --type "cafe" --output cafes.csv --fast
```

## Dashboard

The project includes a Streamlit dashboard for non-technical users.

Install dashboard dependencies:

```bash
python -m pip install ".[dashboard]"
```

Run the dashboard:

```bash
streamlit run dashboard.py
```

The dashboard lets users enter:

- Seed address or public landmark
- Business type or custom business type
- Radius in kilometers
- Max leads
- Worker count
- Fast mode
- Search results per query

Then it displays the enriched leads in-browser and provides a CSV download button.

## Screenshots

Dashboard input form:

```text
┌─────────────────────────────────────────────┐
│ Radial Lead Scraper                         │
│ Free, API-keyless worldwide lead discovery  │
├─────────────────────────────────────────────┤
│ Seed address: Marina Bay Sands Singapore    │
│ Business type: hotel                        │
│ Radius: 3 km                                │
│ Max leads: 25                               │
│ Workers: 8                                  │
│ [Run Scraper]                               │
└─────────────────────────────────────────────┘
```

CSV preview:

```text
Distance | Business Name      | Domain                | Public Emails
0.000    | Demo Hotel         | demohotel.example     | hello@demohotel.example
0.142    | Demo Dental Studio | demodental.example    | hello@demodental.example
```

## CLI Options

| Option | Required | Default | Description |
|---|---:|---:|---|
| `--address` | Yes | none | Seed address or public landmark to search from. This is used for geocoding and is not written to the CSV. |
| `--type` | Yes | none | Business type to search for, e.g. `hotel`, `dental clinic`, `specialty coffee`, `hair salon`. |
| `--radius-km` | No | `15.0` | Search radius around the seed point in kilometers. |
| `--limit` | No | `100` | Maximum number of businesses to enrich after distance sorting. |
| `--output` | No | auto-generated | Output CSV path. |
| `--workers` | No | `8` | Concurrent enrichment workers. Higher is faster but can trigger more rate limiting. Max is capped at `16`. |
| `--fast` | No | off | Uses shorter timeouts and fewer pages per domain for faster test runs. |
| `--max-search-results` | No | `8` | Maximum web-search results checked per enrichment query. |

## Address Input Guidance

`--address` can be a street address, public landmark, neighborhood, city center, or place name that Nominatim can geocode.

Best practice is to include enough geographic context to avoid ambiguity:

```bash
radial-leads --address "3 Killiney Road, Singapore" --type "cafe" --radius-km 2 --limit 25 --fast
```

Prefer this format:

```text
street number + street + city + country
```

Examples that are usually reliable:

```text
3 Killiney Road, Singapore
Marina Bay Sands Singapore
Shibuya Station Tokyo, Japan
Soho London, United Kingdom
Union Square San Francisco, USA
```

Avoid overly ambiguous addresses like:

```text
3 Killiney Road
Main Street
Central Station
```

Ambiguous addresses may geocode to the wrong country or city. If the location looks wrong, add city, state/region, postal code, and country.

The seed address is only used to calculate the starting latitude/longitude. It is not written to the output CSV.

## How The Parameters Work

`--address` defines the center point for the radial search. All distances are calculated from this point.

`--type` controls which OpenStreetMap tags are queried. For example, `hotel` maps to `tourism=hotel`, while `hair salon` maps to `shop=hairdresser` and `shop=beauty`.

`--radius-km` controls how far from the seed point to search. Dense cities usually need smaller radii; rural areas may need larger radii.

`--limit` caps how many discovered targets are enriched after distance sorting. A higher limit means more leads but a longer run.

`--workers` controls concurrent enrichment after geospatial discovery. It speeds up domain search, decision-maker search, and website scraping, but it does not speed up the initial Overpass query. Very high worker counts can increase rate limiting, so `8` is a good default and `16` is the hard cap.

`--fast` uses shorter network timeouts and fewer website pages per domain. Use it for testing or quick runs; omit it for deeper enrichment.

`--max-search-results` controls how many web-search results are checked for domain and decision-maker discovery. Increasing it may improve accuracy but slows the run.

`--output` controls the CSV file path. If omitted, a filename is generated from the business type and address.

## Runtime Expectations

Runtime depends on target count, worker count, search-provider speed, target website speed, and whether external services are rate limiting.

Fast test run:

```bash
radial-leads --address "3 Killiney Road, Singapore" --type "cafe" --radius-km 2 --limit 10 --workers 8 --fast
```

Deeper run:

```bash
radial-leads --address "3 Killiney Road, Singapore" --type "cafe" --radius-km 2 --limit 100 --workers 8
```

If Overpass or web search is slow, reduce `--limit`, use `--fast`, or retry later.

## Supported Business Types

The scraper includes built-in OpenStreetMap tag profiles for common business categories:

| Input Examples | OSM Tags Used |
|---|---|
| `hotel` | `tourism=hotel` |
| `hostel` | `tourism=hostel` |
| `dental clinic`, `dentist` | `amenity=dentist`, `healthcare=dentist` |
| `aesthetic clinic` | `healthcare=clinic`, `amenity=clinic`, `shop=beauty` |
| `clinic` | `healthcare=clinic`, `amenity=clinic`, `healthcare=doctor` |
| `physio`, `physiotherapy` | `healthcare=physiotherapist`, `amenity=clinic` |
| `cafe` | `amenity=cafe` |
| `coffee`, `specialty coffee` | `amenity=cafe`, `shop=coffee` |
| `restaurant` | `amenity=restaurant` |
| `food stall` | `amenity=fast_food`, `amenity=food_court` |
| `waffle stall` | `amenity=fast_food`, `shop=bakery` |
| `hair salon`, `salon` | `shop=hairdresser`, `shop=beauty` |
| `coworking`, `workspace` | `office=coworking`, `amenity=coworking_space` |
| `gym` | `leisure=fitness_centre` |
| `spa` | `leisure=spa`, `shop=massage` |

Unknown/custom business types fall back to a name-based OpenStreetMap search. For very niche categories, results depend heavily on how well that category is tagged in OpenStreetMap.

## Examples

Hotels near Marina Bay Sands:

```bash
python radial_lead_scraper.py --address "Marina Bay Sands Singapore" --type "hotel" --radius-km 5 --limit 50 --workers 8 --fast
```

Dental clinics near Raffles Place:

```bash
python radial_lead_scraper.py --address "Raffles Place Singapore" --type "dental clinic" --radius-km 3 --limit 30 --workers 8 --fast
```

Hair salons in Soho, London:

```bash
python radial_lead_scraper.py --address "Soho London" --type "hair salon" --radius-km 1 --limit 25 --workers 8 --fast
```

Specialty coffee near Shibuya Station, Tokyo:

```bash
python radial_lead_scraper.py --address "Shibuya Station Tokyo" --type "specialty coffee" --radius-km 1 --limit 25 --workers 8 --fast
```

Coworking spaces near Union Square, San Francisco:

```bash
python radial_lead_scraper.py --address "Union Square San Francisco" --type "coworking" --radius-km 3 --limit 25 --workers 8 --fast
```

Restaurants near Sydney Opera House:

```bash
python radial_lead_scraper.py --address "Sydney Opera House" --type "restaurant" --radius-km 2 --limit 25 --workers 8 --fast
```

## Output Schema

The CSV contains these columns:

| Column | Description |
|---|---|
| `Distance (km)` | Distance from the seed address to the business. |
| `Business Name` | Name from OpenStreetMap. |
| `Business Type` | Business type input used for the run. |
| `Address` | Best available address from OpenStreetMap tags. |
| `Domain` | Likely official domain found through public web search. |
| `Decision Maker Name` | Possible decision-maker name from public search snippets. |
| `Generated Emails` | Email permutations generated from decision-maker name and domain. |
| `Public Emails` | Public emails scraped from the business website. |
| `Phone Number` | Public phone number scraped from the business website. |
| `Latitude` | Business latitude. |
| `Longitude` | Business longitude. |
| `Source` | Discovery source, currently `osm`. |

## Demo Sample Output

A fake/demo CSV is included at:

```text
examples/demo_sample_output.csv
```

The sample uses `.example` domains and fake businesses only. It is safe to commit and use in docs.

## Accuracy Notes

- Discovery quality depends on OpenStreetMap coverage and tagging quality in the selected area.
- Some business categories are tagged inconsistently across countries and cities.
- `--type` is interpreted through OpenStreetMap tags, not Google Maps categories.
- For custom business types, the scraper falls back to name-based OpenStreetMap matching, which can be broader or weaker than built-in profiles.
- Very niche categories like `waffle stall` may map to broader OSM tags such as `fast_food` or `bakery`, so results may need manual review.
- Decision-maker names come from public search snippets and should be treated as leads, not verified identities.
- Generated email permutations are guesses, not verified deliverable addresses.
- Public emails and phone numbers are scraped from public-facing websites and can include generic role accounts.
- `Domain` is a best-effort official-site guess. Directory, social, and OTA domains are filtered, but manual review is still recommended.

## Performance Tips

- Use `--fast` while testing.
- Start with `--limit 10` or `--limit 25` before large runs.
- Increase `--workers` for speed, but avoid excessive concurrency to reduce rate limiting.
- Use smaller `--radius-km` values for dense cities.

## Privacy And Publishing Notes

- Do not commit CSV output files containing lead data unless you intend to publish them.
- Do not include private home addresses in examples, tests, issues, screenshots, or documentation.
- Use public landmarks in documentation and demos.

## Data Sources

- Nominatim/OpenStreetMap for geocoding
- Overpass/OpenStreetMap for business discovery
- DDGS for public web search
- Public business websites for emails and phone numbers

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
