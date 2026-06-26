#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import streamlit as st

from radial_lead_scraper import (
    CSV_COLUMNS,
    Contacts,
    TYPE_PROFILES,
    Target,
    discover_targets,
    enrich_target,
)


st.set_page_config(page_title="Radial Lead Scraper", page_icon="📍", layout="wide")


def rows_to_csv_bytes(rows: List[Dict[str, str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def run_scrape(
    address: str,
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
        address=address,
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


st.title("Radial Lead Scraper")
st.caption("Free, API-keyless, worldwide radial lead discovery and enrichment.")

with st.sidebar:
    st.header("Search Inputs")
    address = st.text_input("Seed address or landmark", value="Marina Bay Sands Singapore")
    known_types = sorted(TYPE_PROFILES.keys())
    selected_type = st.selectbox("Known business type", options=known_types, index=known_types.index("hotel"))
    custom_type = st.text_input("Or custom business type", value="")
    business_type = custom_type.strip() or selected_type
    radius_km = st.slider("Radius (km)", min_value=0.5, max_value=50.0, value=3.0, step=0.5)
    limit = st.slider("Max leads", min_value=1, max_value=500, value=25, step=1)
    workers = st.slider("Workers", min_value=1, max_value=16, value=8, step=1)
    fast = st.checkbox("Fast mode", value=True)
    max_search_results = st.slider("Search results per query", min_value=3, max_value=20, value=8, step=1)
    run_button = st.button("Run Scraper", type="primary")

st.markdown(
    """
    Enter a public address or landmark, choose a business type, then download the enriched CSV.
    Use public landmarks for demos and avoid committing generated lead files.
    """
)

if run_button:
    if not address.strip() or not business_type.strip():
        st.error("Address and business type are required.")
    else:
        with st.spinner("Discovering and enriching leads..."):
            try:
                result_rows = run_scrape(
                    address=address.strip(),
                    business_type=business_type.strip(),
                    radius_km=radius_km,
                    limit=limit,
                    workers=workers,
                    fast=fast,
                    max_search_results=max_search_results,
                )
            except RuntimeError as exc:
                st.error(str(exc))
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
