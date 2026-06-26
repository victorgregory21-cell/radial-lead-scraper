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

For free self-hosting, use Streamlit Community Cloud. It is simpler for this project than Vercel because this is a Python Streamlit app. Vercel is excellent for JavaScript/Next.js apps, but long-running Python scraping jobs are not a good fit for Vercel serverless time limits.

Install dashboard dependencies:

```bash
python -m pip install ".[dashboard]"
```

Run the dashboard:

```bash
streamlit run dashboard.py
```

Host it free on Streamlit Community Cloud:

1. Push this repo to GitHub.
2. Go to `https://share.streamlit.io/`.
3. Sign in with GitHub.
4. Create a new app from this repo.
5. Set the app file to `dashboard.py`.
6. Add app secrets before sharing the URL:

```toml
APP_USERNAME = "your-username"
APP_PASSWORD = "your-password"
```

7. Deploy.

Your colleagues can then use the app from a normal browser without installing Python.

Do not commit real usernames/passwords to GitHub. Put them in Streamlit app secrets or environment variables only.

The dashboard lets users enter:

- Country
- Location input method: `Simple`, `Full address`, or `Coordinates`
- Place name, street address, city, region, postal code, and country when using `Full address`
- Business type or custom business type
- Radius in kilometers
- Max leads
- Worker count
- Fast mode
- Search results per query

Then it displays the enriched leads in-browser and provides a CSV download button.

Beginner-friendly defaults:

- Use `Full address` if a landmark is not found.
- Use `Coordinates` if the location still fails.
- Click `Check Location` before `Find Leads` to confirm the app can find the starting point.
- Use `Fast mode` on.
- Keep `Speed level` at `8`.
- Start with `Maximum leads` between `10` and `25`.
- Use city and country in the location field.

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
Distance | Business Name      | Domain                | Real Found Emails
0.000    | Demo Hotel         | demohotel.example     | hello@demohotel.example
0.142    | Demo Dental Studio | demodental.example    | hello@demodental.example
```

## CLI Options

| Option | Required | Default | Description |
|---|---:|---:|---|
| `--address` | Yes | none | Seed address or public landmark to search from. This is used for geocoding and is not written to the CSV. |
| `--place` | No | empty | Place/landmark/business name for structured address input. |
| `--street` | No | empty | Street address for structured address input. |
| `--city` | No | empty | City for structured address input. |
| `--region` | No | empty | State, province, district, or region for structured address input. |
| `--postal-code` | No | empty | Postal or ZIP code for structured address input. |
| `--country` | No | empty | Country for structured address input. |
| `--coords` | No | empty | Exact `latitude,longitude`. This is the most precise option. |
| `--type` | Yes | none | Business type to search for, e.g. `hotel`, `dental clinic`, `specialty coffee`, `hair salon`. |
| `--radius-km` | No | `15.0` | Search radius around the seed point in kilometers. |
| `--limit` | No | `100` | Maximum number of businesses to enrich after distance sorting. |
| `--output` | No | auto-generated | Output CSV path. |
| `--workers` | No | `8` | Concurrent enrichment workers. Higher is faster but can trigger more rate limiting. Max is capped at `16`. |
| `--fast` | No | off | Uses shorter timeouts and fewer pages per domain for faster test runs. |
| `--max-search-results` | No | `8` | Maximum web-search results checked per enrichment query. |

## Address Input Guidance

The most reliable input methods are, in order:

1. `Coordinates`: exact latitude/longitude copied from a map.
2. `Full address`: place name + street + city + country.
3. `Simple`: landmark or open-ended text.

`--address` can be a street address, public landmark, neighborhood, city center, or place name that free geocoders can resolve.

The app now tries several free geocoding methods automatically:

- Direct latitude/longitude coordinates
- Built-in aliases for common landmarks such as `Marina Bay Sands Singapore` and `Grand Indonesia`
- Nominatim geocoding
- OpenStreetMap search API
- Photon geocoding fallback

This makes common inputs much more forgiving, but no free geocoder is perfect. If a location still fails, paste coordinates from Google Maps or Apple Maps.

Structured address input is recommended for non-technical users because it reduces ambiguity:

```bash
radial-leads \
  --place "Grand Indonesia Shopping Town" \
  --street "Jl. M.H. Thamrin No.1" \
  --city "Jakarta" \
  --region "Jakarta Pusat" \
  --country "Indonesia" \
  --type "cafe" \
  --radius-km 2 \
  --limit 25 \
  --fast
```

Coordinates are the most foolproof option:

```bash
radial-leads --coords "-6.1951, 106.8206" --type "cafe" --radius-km 2 --limit 25 --fast
```

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
1.2837, 103.8607
-6.1951, 106.8206
```

Avoid overly ambiguous addresses like:

```text
3 Killiney Road
Main Street
Central Station
```

Ambiguous addresses may geocode to the wrong country or city. If the location looks wrong, add city, state/region, postal code, and country.

Coordinates are the most foolproof input. In Google Maps, right-click a location, copy the latitude/longitude, and paste it into the address field.

## Foolproof Location Workflow

For non-technical users, use this order:

1. Try `Full address`.
2. Click `Check Location` in the dashboard.
3. If found, click `Find Leads`.
4. If not found, open Google Maps or Apple Maps.
5. Search for the place manually.
6. Copy the exact latitude/longitude.
7. Switch the dashboard to `Coordinates`.
8. Paste the coordinates and click `Check Location` again.
9. Click `Find Leads`.

Coordinates almost always work because they skip name/address ambiguity entirely.

How to copy coordinates:

- Google Maps desktop: right-click the exact place and click the numbers at the top of the menu.
- Google Maps mobile: long-press the exact place and copy the coordinates shown in the search bar/details.
- Apple Maps: drop a pin, open the place card, and copy latitude/longitude if available.

## Geocoding Test Results

The following public addresses were tested successfully during development:

| City | Input | Result |
|---|---|---|
| Singapore | `3 Killiney Road, Singapore` | Geocoded |
| Singapore | `10 Bayfront Avenue, Singapore` | Geocoded |
| Singapore | `1 Fullerton Road, Singapore` | Geocoded |
| Jakarta | `Jl. M.H. Thamrin No.1, Menteng, Jakarta Pusat, Indonesia` | Geocoded |
| Jakarta | `Jl. M.H. Thamrin No.28-30, Jakarta Pusat, Indonesia` | Geocoded |
| Jakarta | `Jl. Jenderal Sudirman Kav. 52-53, Jakarta, Indonesia` | Geocoded |
| London | `221B Baker Street, London, United Kingdom` | Geocoded |
| London | `10 Downing Street, London, United Kingdom` | Geocoded |
| London | `1 Canada Square, London, United Kingdom` | Geocoded |
| New York | `350 5th Avenue, New York, NY, USA` | Geocoded |
| New York | `11 Wall Street, New York, NY, USA` | Geocoded |
| New York | `30 Rockefeller Plaza, New York, NY, USA` | Geocoded |

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
| `Generated Emails` | Guessed email permutations generated from decision-maker name and domain. These are not found or verified emails. |
| `Real Found Emails` | Emails actually found in public sources such as websites, OSM tags, `mailto:` links, or public search snippets. |
| `Public Emails` | Backward-compatible duplicate of found public emails. Prefer `Real Found Emails`. |
| `Email Sources` | Evidence showing where found emails came from, e.g. website URL, `mailto`, OSM, or search result source. |
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
- `Generated Emails` are guesses only. They are not found emails and are not verified deliverable addresses.
- `Real Found Emails` are actually found in public places, including business websites, `mailto:` links, OSM tags, and public search snippets from related websites such as LinkedIn/RocketReach-style pages.
- Public emails and phone numbers can include generic role accounts.
- `Domain` is a best-effort official-site guess. Directory, social, and OTA domains are filtered, but manual review is still recommended.

## Email Discovery Notes

The scraper separates guessed emails from found emails:

- `Generated Emails`: guessed from a decision-maker name and domain, e.g. `john.smith@example.com`. These may not exist.
- `Real Found Emails`: emails actually found in public sources.
- `Email Sources`: where the found emails came from.

The scraper looks for real emails in:

- OpenStreetMap email/contact tags
- Home page
- Contact pages
- About pages
- Team/staff/people pages
- Leadership/management pages
- Doctors/dentists/therapists pages
- Booking/reservation/enquiry pages
- Careers/press/media/events pages
- `mailto:` links
- Public search snippets from related websites including LinkedIn, RocketReach, Apollo, SignalHire, Lusha, Crunchbase, and similar sources

It does not use paid APIs and does not verify mailbox deliverability.

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
