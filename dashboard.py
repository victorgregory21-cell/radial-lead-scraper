#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import hmac
import io
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import streamlit as st

from radial_lead_scraper import (
    CSV_COLUMNS,
    Contacts,
    DEFAULT_WORKERS,
    TYPE_PROFILES,
    Target,
    build_structured_address,
    discover_targets,
    enrich_target,
    geocode_address,
)


st.set_page_config(page_title="Radial Lead Scraper", page_icon="📍", layout="wide")

COUNTRY_EXAMPLES = {
    "Singapore": {
        "place": "Marina Bay Sands",
        "street": "10 Bayfront Avenue",
        "city": "Singapore",
        "region": "",
        "postal": "018956",
        "coords": "1.2837, 103.8607",
    },
    "Indonesia": {
        "place": "Grand Indonesia Shopping Town",
        "street": "Jl. M.H. Thamrin No.1",
        "city": "Jakarta",
        "region": "Jakarta Pusat",
        "postal": "10310",
        "coords": "-6.1951, 106.8206",
    },
    "United Kingdom": {
        "place": "Soho",
        "street": "221B Baker Street",
        "city": "London",
        "region": "",
        "postal": "NW1 6XE",
        "coords": "51.5234, -0.1582",
    },
    "United States": {
        "place": "Empire State Building",
        "street": "350 5th Avenue",
        "city": "New York",
        "region": "NY",
        "postal": "10118",
        "coords": "40.7484, -73.9857",
    },
}


def get_config_secret(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def check_password() -> bool:
    expected_user = get_config_secret("APP_USERNAME")
    expected_password = get_config_secret("APP_PASSWORD")

    if not expected_user or not expected_password:
        st.error("Dashboard login is not configured.")
        st.info("Set APP_USERNAME and APP_PASSWORD in Streamlit secrets or environment variables before using the dashboard.")
        return False

    if st.session_state.get("authenticated"):
        return True

    st.title("Radial Lead Scraper")
    st.caption("Private dashboard")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if submitted:
        user_ok = hmac.compare_digest(username, expected_user)
        password_ok = hmac.compare_digest(password, expected_password)
        if user_ok and password_ok:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect username or password.")

    return False


def rows_to_csv_bytes(rows: List[Dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def run_scrape(
    seed_input: str,
    business_type: str,
    radius_km: float,
    limit: int,
    workers: int,
    fast: bool,
    max_search_results: int,
) -> List[Dict[str, str]]:
    search_timeout = 5 if fast else 10
    request_timeout = 8 if fast else 16
    overpass_timeout = 18 if fast else 50
    max_pages = 2 if fast else 6

    targets = discover_targets(
        address=seed_input,
        business_type=business_type,
        radius_km=radius_km,
        limit=limit,
        timeout=overpass_timeout,
    )

    if not targets:
        return []

    domain_cache: Dict[str, str] = {}
    contact_cache: Dict[str, Contacts] = {}
    rows: List[Optional[Dict[str, str]]] = [None] * len(targets)

    progress = st.progress(0)
    status = st.empty()

    with ThreadPoolExecutor(max_workers=max(1, min(workers, 16))) as executor:
        future_map = {
            executor.submit(
                enrich_target,
                target,
                business_type,
                max_search_results,
                search_timeout,
                request_timeout,
                max_pages,
                domain_cache,
                contact_cache,
            ): idx
            for idx, target in enumerate(targets)
        }

        total = len(future_map)
        for completed, future in enumerate(as_completed(future_map), start=1):
            idx = future_map[future]
            target: Target = targets[idx]
            try:
                rows[idx] = future.result()
            except Exception:
                rows[idx] = {
                    "Distance (km)": f"{target.distance_km:.3f}",
                    "Business Name": target.name,
                    "Business Type": business_type,
                    "Address": target.address,
                    "Domain": "",
                    "Decision Maker Name": "",
                    "Generated Emails": "",
                    "Public Emails": "",
                    "Phone Number": "",
                    "Latitude": f"{target.lat:.7f}",
                    "Longitude": f"{target.lon:.7f}",
                    "Source": target.source,
                }
            progress.progress(completed / total)
            status.write(f"Enriched {completed}/{total}: {target.name}")

    return [row for row in rows if row is not None]


st.title("Find Nearby Business Leads")
st.caption("Enter a location and business type. Get a downloadable CSV of nearby leads.")

if not check_password():
    st.stop()

with st.sidebar:
    st.header("1. Where should we search from?")
    country = st.selectbox(
        "Country",
        options=list(COUNTRY_EXAMPLES.keys()) + ["Other / custom"],
        help="Choosing a country helps avoid ambiguous locations.",
    )
    example = COUNTRY_EXAMPLES.get(country, COUNTRY_EXAMPLES["Singapore"])

    input_mode = st.radio(
        "Location input method",
        options=["Full address", "Simple", "Coordinates"],
        horizontal=True,
        help="Full address is recommended. Coordinates are the most precise fallback.",
    )

    if input_mode == "Simple":
        simple_location = st.text_input(
            "Place, landmark, or address",
            value=f"{example['place']}, {example['city']}, {country}" if country != "Other / custom" else "Marina Bay Sands Singapore",
            help="Good for famous places. If it fails, switch to Full address or Coordinates.",
        )
        seed_input = simple_location.strip()
    elif input_mode == "Full address":
        place = st.text_input("Place name (optional)", value=example["place"], help="Example: Grand Indonesia Shopping Town")
        street = st.text_input("Street address", value=example["street"], help="Example: Jl. M.H. Thamrin No.1 or 10 Bayfront Avenue")
        city = st.text_input("City", value=example["city"], help="Example: Jakarta, Singapore, London, New York")
        region = st.text_input("State / region (optional)", value=example["region"], help="Example: NY, Jakarta Pusat")
        postal_code = st.text_input("Postal / ZIP code (optional)", value=example["postal"])
        country_field = st.text_input("Country", value="" if country == "Other / custom" else country)
        seed_input = build_structured_address(
            place=place,
            street=street,
            city=city,
            region=region,
            country=country_field,
            postal_code=postal_code,
        )
        st.caption(f"Search will start from: {seed_input or 'Fill in address fields'}")
    else:
        coords = st.text_input(
            "Latitude, longitude",
            value=example["coords"],
            help="Most foolproof option. In Google Maps, right-click a place and copy the coordinates.",
        )
        seed_input = coords.strip()

    st.info(
        "Best success rate: use Full address. If that fails, paste coordinates from Google Maps or Apple Maps."
    )

    if st.button("Check Location", use_container_width=True):
        if not seed_input.strip():
            st.error("Enter a location first.")
        else:
            with st.spinner("Checking location..."):
                coords_found = geocode_address(seed_input.strip())
            if coords_found:
                st.success(f"Location found: {coords_found[0]:.6f}, {coords_found[1]:.6f}")
                st.caption("If this looks right, click Find Leads below.")
            else:
                st.error("Location not found. Use coordinates for the most reliable result.")
                st.markdown(
                    """
                    How to get coordinates:
                    1. Open Google Maps or Apple Maps.
                    2. Search for the place.
                    3. Right-click / long-press the exact spot.
                    4. Copy the latitude and longitude.
                    5. Switch this form to `Coordinates` and paste them.
                    """
                )

    st.header("2. What kind of business?")
    known_types = sorted(TYPE_PROFILES.keys())
    selected_type = st.selectbox(
        "Choose a common business type",
        options=known_types,
        index=known_types.index("hotel"),
        help="These are mapped to OpenStreetMap categories behind the scenes.",
    )
    custom_type = st.text_input(
        "Or type your own business type",
        value="",
        help="Optional. Use this only if the dropdown does not have what you need.",
    )
    business_type = custom_type.strip() or selected_type

    st.header("3. Search size")
    radius_km = st.slider(
        "How far around this location?",
        min_value=0.5,
        max_value=50.0,
        value=3.0,
        step=0.5,
        help="Smaller radius = faster and more local. Dense cities usually only need 1-5 km.",
    )
    limit = st.slider(
        "Maximum leads to return",
        min_value=1,
        max_value=500,
        value=25,
        step=1,
        help="Higher numbers take longer because each business gets enriched.",
    )

    with st.expander("Advanced settings", expanded=False):
        workers = st.slider(
            "Speed level",
            min_value=1,
            max_value=16,
            value=DEFAULT_WORKERS,
            step=1,
            help="This controls how many businesses are enriched at the same time. 8 is a good default.",
        )
        fast = st.checkbox(
            "Fast mode",
            value=True,
            help="Recommended. Faster runs with shorter website checks. Turn off only if you want deeper enrichment.",
        )
        max_search_results = st.slider(
            "Search depth",
            min_value=3,
            max_value=20,
            value=8,
            step=1,
            help="How many web-search results to check per business. Higher may improve results but is slower.",
        )

    run_button = st.button("Find Leads", type="primary", use_container_width=True)

st.markdown(
    """
    ### How it works
    1. Finds the location you entered.
    2. Searches nearby businesses of the selected type.
    3. Sorts them nearest-first.
    4. Finds websites, public emails, phone numbers, and possible decision makers.
    5. Lets you download everything as a CSV.

    If a location is not found, add the city and country or paste coordinates.

    ### For first-time users
    Use `Full address` first. If the app cannot find the location, use Google Maps or Apple Maps to copy coordinates and switch to `Coordinates` mode.
    """
)

if run_button:
    if not seed_input.strip() or not business_type.strip():
        st.error("Location and business type are required.")
    else:
        with st.spinner("Discovering and enriching leads..."):
            try:
                result_rows = run_scrape(
                    seed_input=seed_input.strip(),
                    business_type=business_type.strip(),
                    radius_km=radius_km,
                    limit=limit,
                    workers=workers,
                    fast=fast,
                    max_search_results=max_search_results,
                )
            except RuntimeError as exc:
                st.error(str(exc))
                st.info(
                    "Try a clearer location like 'Grand Indonesia Shopping Town, Jakarta, Indonesia', "
                    "'Marina Bay Sands Singapore', or coordinates like '1.2837, 103.8607'."
                )
                result_rows = []

        if result_rows:
            st.success(f"Generated {len(result_rows)} leads.")
            st.dataframe(result_rows, use_container_width=True)
            st.download_button(
                "Download CSV",
                data=rows_to_csv_bytes(result_rows),
                file_name="radial_leads.csv",
                mime="text/csv",
            )
        else:
            st.warning("No leads found. Try a larger radius, broader business type, or different location.")
