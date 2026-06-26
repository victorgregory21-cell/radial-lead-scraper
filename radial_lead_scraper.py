#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Radial Lead Scraper
Author: Elroy Jahjaloo

Free, API-keyless, worldwide radial lead discovery and enrichment pipeline.
Uses Nominatim + Overpass/OpenStreetMap for geospatial discovery and DDGS +
website scraping for public-contact enrichment.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import math
import os
import random
import re
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
import tldextract
from bs4 import BeautifulSoup
from ddgs import DDGS
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


APP_USER_AGENT = "radial-lead-scraper/1.0 (open-source; local-user)"
DEFAULT_OUTPUT = "leads_radial.csv"
DEFAULT_RADIUS_KM = 15.0
DEFAULT_LIMIT = 100
DEFAULT_WORKERS = 8

KNOWN_PLACE_ALIASES: Dict[str, Tuple[float, float]] = {
    "marina bay sands": (1.2836965, 103.8607226),
    "marina bay sands singapore": (1.2836965, 103.8607226),
    "mbs singapore": (1.2836965, 103.8607226),
    "grand indonesia": (-6.195122, 106.820558),
    "grand indonesia jakarta": (-6.195122, 106.820558),
    "grand indonesia shopping town": (-6.195122, 106.820558),
    "plaza indonesia": (-6.193925, 106.822215),
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

REQUEST_HEADERS = {
    "User-Agent": APP_USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s().-]?)?(?:\d[\s().-]?){7,14}\d")
NAME_RE = re.compile(r"\b([A-Z][a-zA-Z'\-]+)\s+([A-Z][a-zA-Z'\-]+)\b")

CSV_COLUMNS = [
    "Distance (km)",
    "Business Name",
    "Business Type",
    "Address",
    "Domain",
    "Decision Maker Name",
    "Generated Emails",
    "Real Found Emails",
    "Public Emails",
    "Email Sources",
    "Phone Number",
    "Latitude",
    "Longitude",
    "Source",
]

EXTERNAL_EMAIL_SOURCE_DOMAINS = {
    "linkedin.com",
    "rocketreach.co",
    "apollo.io",
    "signalhire.com",
    "lusha.com",
    "clay.earth",
    "contactout.com",
    "zoominfo.com",
    "hunter.io",
    "leadIQ.com".lower(),
    "crunchbase.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
}

EMAIL_NOISE_DOMAINS = {
    "sentry.wixpress.com",
    "sentry-next.wixpress.com",
}

EMAIL_NOISE_PATTERNS = (
    "polyfill@",
    "example@",
    "email@email.com",
)

LIKELY_SUBPAGE_PATHS = [
    "contact",
    "contact-us",
    "contacts",
    "about",
    "about-us",
    "team",
    "our-team",
    "staff",
    "people",
    "leadership",
    "leaders",
    "management",
    "managers",
    "doctors",
    "dentists",
    "physicians",
    "therapists",
    "partners",
    "founders",
    "careers",
    "press",
    "media",
    "events",
    "reservations",
    "reservation",
    "booking",
    "book",
    "enquiry",
    "enquiries",
    "inquiry",
    "support",
    "locations",
    "location",
    "branches",
    "outlets",
    "privacy",
    "terms",
]

DOCUMENT_EXTENSIONS = (".pdf", ".doc", ".docx", ".txt")

OTA_AND_DIRECTORY_BLOCKLIST = {
    "agoda.com",
    "booking.com",
    "expedia.com",
    "tripadvisor.com",
    "trivago.com",
    "hotels.com",
    "yelp.com",
    "foursquare.com",
    "trip.com",
    "kayak.com",
    "zomato.com",
    "opentable.com",
    "deliveroo.com",
    "foodpanda.sg",
    "grab.com",
    "classpass.com",
    "practo.com",
    "healthgrades.com",
    "doctoranywhere.com",
    "dentaldepartures.com",
    "medicaldepartures.com",
    "findglocal.com",
    "tiktok.com",
    "parisinsidersguide.com",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "wikipedia.org",
    "google.com",
}

TYPE_PROFILES: Dict[str, List[Tuple[str, str]]] = {
    "hotel": [("tourism", "hotel")],
    "hostel": [("tourism", "hostel")],
    "dental clinic": [("amenity", "dentist"), ("healthcare", "dentist")],
    "dentist": [("amenity", "dentist"), ("healthcare", "dentist")],
    "aesthetic clinic": [("healthcare", "clinic"), ("amenity", "clinic"), ("shop", "beauty")],
    "clinic": [("healthcare", "clinic"), ("amenity", "clinic"), ("healthcare", "doctor")],
    "physio": [("healthcare", "physiotherapist"), ("amenity", "clinic")],
    "physiotherapy": [("healthcare", "physiotherapist"), ("amenity", "clinic")],
    "cafe": [("amenity", "cafe")],
    "coffee": [("amenity", "cafe"), ("shop", "coffee")],
    "specialty coffee": [("amenity", "cafe"), ("shop", "coffee")],
    "restaurant": [("amenity", "restaurant")],
    "food stall": [("amenity", "fast_food"), ("amenity", "food_court")],
    "waffle stall": [("amenity", "fast_food"), ("shop", "bakery")],
    "hair salon": [("shop", "hairdresser")],
    "salon": [("shop", "hairdresser"), ("shop", "beauty")],
    "coworking": [("office", "coworking"), ("amenity", "coworking_space")],
    "workspace": [("office", "coworking"), ("amenity", "coworking_space")],
    "gym": [("leisure", "fitness_centre")],
    "spa": [("leisure", "spa"), ("shop", "massage")],
}

ROLE_QUERIES = {
    "hotel": '("General Manager" OR "Hotel Manager" OR "Front Office Manager")',
    "hostel": '("General Manager" OR "Hostel Manager" OR "Operations Manager")',
    "dental": '("Clinic Manager" OR "Principal Dentist" OR "Dental Director" OR "Founder")',
    "clinic": '("Clinic Manager" OR "Medical Director" OR "Founder" OR "Director")',
    "cafe": '("Owner" OR "Founder" OR "Cafe Manager" OR "Operations Manager")',
    "restaurant": '("Owner" OR "Founder" OR "Restaurant Manager" OR "General Manager")',
    "salon": '("Owner" OR "Founder" OR "Salon Manager" OR "Director")',
    "workspace": '("Founder" OR "Community Manager" OR "General Manager" OR "Operations Manager")',
    "default": '("Owner" OR "Founder" OR "General Manager" OR "Manager" OR "Director")',
}


@dataclass(frozen=True)
class Target:
    name: str
    lat: float
    lon: float
    distance_km: float
    address: str = ""
    source: str = "osm"
    website: str = ""
    email: str = ""
    phone: str = ""


@dataclass
class Contacts:
    emails: Set[str] = field(default_factory=set)
    phones: Set[str] = field(default_factory=set)
    email_sources: Dict[str, Set[str]] = field(default_factory=dict)

    def add_email(self, email: str, source: str) -> None:
        cleaned = clean_email(email)
        if not valid_email(cleaned):
            return
        self.emails.add(cleaned)
        self.email_sources.setdefault(cleaned, set()).add(source)

    def add_emails(self, emails: Iterable[str], source: str) -> None:
        for email in emails:
            self.add_email(email, source)

    def add_phone(self, phone: str) -> None:
        cleaned = normalize_phone(phone)
        if cleaned:
            self.phones.add(cleaned)

    def add_phones(self, phones: Iterable[str]) -> None:
        for phone in phones:
            self.add_phone(phone)


def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "leads"


def normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def build_structured_address(
    place: str = "",
    street: str = "",
    city: str = "",
    region: str = "",
    country: str = "",
    postal_code: str = "",
) -> str:
    parts = [place, street, city, region, postal_code, country]
    return ", ".join(part.strip() for part in parts if part and part.strip())


def parse_coordinates(text: str) -> Optional[Tuple[float, float]]:
    cleaned = (text or "").strip()
    match = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*", cleaned)
    if not match:
        return None
    lat = float(match.group(1))
    lon = float(match.group(2))
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return (lat, lon)
    return None


def address_variants(address: str) -> List[str]:
    original = (address or "").strip()
    if not original:
        return []
    variants = [original]
    compact = re.sub(r"\s+", " ", original)
    variants.append(compact)

    lowered = compact.lower()
    if "singapore" not in lowered and any(token in lowered for token in ("marina bay", "killiney", "raffles place", "orchard")):
        variants.append(f"{compact}, Singapore")
    if "jakarta" not in lowered and "indonesia" not in lowered and any(token in lowered for token in ("grand indonesia", "plaza indonesia", "thamrin")):
        variants.append(f"{compact}, Jakarta, Indonesia")
    if lowered == "grand indonesia":
        variants.extend(
            [
                "Grand Indonesia Shopping Town, Jakarta, Indonesia",
                "Jl. M.H. Thamrin No.1, Menteng, Jakarta Pusat, Indonesia",
            ]
        )
    if lowered == "marina bay sands":
        variants.extend(["Marina Bay Sands Singapore", "10 Bayfront Avenue, Singapore"])

    deduped = []
    seen = set()
    for variant in variants:
        key = normalize_key(variant)
        if key not in seen:
            seen.add(key)
            deduped.append(variant)
    return deduped


def geocode_nominatim(query: str) -> Optional[Tuple[float, float]]:
    try:
        loc = Nominatim(user_agent=APP_USER_AGENT, timeout=20).geocode(query, exactly_one=True)
        if loc:
            return (float(loc.latitude), float(loc.longitude))
    except Exception:
        return None
    return None


def geocode_osm_search(query: str) -> Optional[Tuple[float, float]]:
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1},
            headers=REQUEST_HEADERS,
            timeout=(5, 15),
        )
        response.raise_for_status()
        results = response.json()
        if results:
            return (float(results[0]["lat"]), float(results[0]["lon"]))
    except Exception:
        return None
    return None


def geocode_photon(query: str) -> Optional[Tuple[float, float]]:
    try:
        response = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 1},
            headers=REQUEST_HEADERS,
            timeout=(5, 15),
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        if features:
            lon, lat = features[0]["geometry"]["coordinates"][:2]
            return (float(lat), float(lon))
    except Exception:
        return None
    return None


def geocode_address(address: str) -> Optional[Tuple[float, float]]:
    coords = parse_coordinates(address)
    if coords:
        log("Geocoded from coordinates input.")
        return coords

    alias = KNOWN_PLACE_ALIASES.get(normalize_key(address))
    if alias:
        log("Geocoded from built-in place alias.")
        return alias

    for variant in address_variants(address):
        for provider_name, provider in (
            ("Nominatim", geocode_nominatim),
            ("OSM Search", geocode_osm_search),
            ("Photon", geocode_photon),
        ):
            coords = provider(variant)
            if coords:
                log(f"Geocoded with {provider_name}: {variant}")
                return coords
    return None


def radius_to_bbox(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / max(111.0 * abs(math.cos(math.radians(lat))), 1.0)
    return (lat - lat_delta, lon - lon_delta, lat + lat_delta, lon + lon_delta)


def resolve_type_tags(business_type: str) -> List[Tuple[str, str]]:
    key = normalize_key(business_type)
    if key in TYPE_PROFILES:
        return TYPE_PROFILES[key]

    tokens = key.split()
    if "dental" in tokens or "dentist" in tokens:
        return TYPE_PROFILES["dental clinic"]
    if "coffee" in tokens or "cafe" in tokens:
        return TYPE_PROFILES["coffee"]
    if "physio" in key:
        return TYPE_PROFILES["physio"]
    if "salon" in tokens or "hair" in tokens:
        return TYPE_PROFILES["salon"]
    if "restaurant" in tokens:
        return TYPE_PROFILES["restaurant"]
    if "clinic" in tokens:
        return TYPE_PROFILES["clinic"]
    if "workspace" in tokens or "cowork" in key:
        return TYPE_PROFILES["workspace"]
    return [("name", business_type)]


def overpass_query(tags: Sequence[Tuple[str, str]], bbox: Tuple[float, float, float, float]) -> str:
    south, west, north, east = bbox
    clauses = []
    for key, value in tags:
        safe_key = key.replace('"', "")
        safe_value = value.replace('"', "")
        if safe_key == "name":
            selector = f'["name"~"{safe_value}",i]'
        else:
            selector = f'["{safe_key}"="{safe_value}"]'
        clauses.extend(
            [
                f'node{selector}({south},{west},{north},{east});',
                f'way{selector}({south},{west},{north},{east});',
                f'relation{selector}({south},{west},{north},{east});',
            ]
        )
    body = "\n".join(clauses)
    return textwrap.dedent(
        f"""
        [out:json][timeout:50];
        (
        {body}
        );
        out center tags;
        """
    ).strip()


def endpoint_alive(url: str, timeout: int) -> bool:
    try:
        status_url = url.rsplit("/", 1)[0] + "/status"
        r = requests.get(status_url, headers=REQUEST_HEADERS, timeout=(4, timeout))
        return r.status_code == 200
    except Exception:
        return False


def query_overpass(query: str, timeout: int) -> List[dict]:
    healthy = [u for u in OVERPASS_ENDPOINTS if endpoint_alive(u, timeout=5)]
    if not healthy:
        log("[OVERPASS] health checks failed; trying mirrors directly")
        healthy = OVERPASS_ENDPOINTS

    for endpoint in healthy:
        for retry in range(2):
            try:
                log(f"[OVERPASS] {endpoint} retry={retry + 1}")
                r = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=REQUEST_HEADERS,
                    timeout=(5, timeout),
                )
                if r.status_code == 429:
                    log("[OVERPASS] rate limited")
                    continue
                r.raise_for_status()
                elements = r.json().get("elements", [])
                if elements:
                    log(f"[OVERPASS] elements={len(elements)}")
                    return elements
            except Exception as exc:
                log(f"[OVERPASS] failed: {type(exc).__name__}")
    return []


def target_from_osm(el: dict, seed: Tuple[float, float]) -> Optional[Target]:
    tags = el.get("tags", {}) or {}
    name = (tags.get("name") or tags.get("brand") or "").strip()
    if not name:
        return None
    lat = el.get("lat")
    lon = el.get("lon")
    if lat is None or lon is None:
        center = el.get("center", {}) or {}
        lat = center.get("lat")
        lon = center.get("lon")
    if lat is None or lon is None:
        return None
    address = ", ".join(
        part
        for part in [
            tags.get("addr:housenumber"),
            tags.get("addr:street"),
            tags.get("addr:city"),
            tags.get("addr:country"),
        ]
        if part
    )
    distance = geodesic(seed, (float(lat), float(lon))).km
    website = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
    email = tags.get("email") or tags.get("contact:email") or ""
    phone = tags.get("phone") or tags.get("contact:phone") or ""
    return Target(
        name=name,
        lat=float(lat),
        lon=float(lon),
        distance_km=round(distance, 3),
        address=address,
        website=website,
        email=email,
        phone=phone,
    )


def discover_targets(address: str, business_type: str, radius_km: float, limit: int, timeout: int) -> List[Target]:
    seed = geocode_address(address)
    if not seed:
        raise RuntimeError(
            "Could not find that location. Try adding city and country, e.g. "
            "'Marina Bay Sands Singapore', 'Grand Indonesia, Jakarta, Indonesia', "
            "or paste coordinates like '1.2837, 103.8607'."
        )
    log(f"Seed coordinates: {seed[0]:.6f}, {seed[1]:.6f}")

    tags = resolve_type_tags(business_type)
    bbox = radius_to_bbox(seed[0], seed[1], radius_km)
    elements = query_overpass(overpass_query(tags, bbox), timeout=timeout)
    targets: List[Target] = []
    seen = set()
    for el in elements:
        target = target_from_osm(el, seed)
        if not target:
            continue
        if target.distance_km > radius_km:
            continue
        key = (normalize_key(target.name), round(target.lat, 6), round(target.lon, 6))
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    targets.sort(key=lambda t: t.distance_km)
    return targets[:limit]


def clean_email(email: str) -> str:
    return email.lower().strip(" .;,:<>\"'()[]{}")


def valid_email(email: str) -> bool:
    if "@" not in email or len(email) > 120:
        return False
    local, domain = email.split("@", 1)
    if not local or not domain or "." not in domain:
        return False
    if domain in EMAIL_NOISE_DOMAINS:
        return False
    if any(pattern in email for pattern in EMAIL_NOISE_PATTERNS):
        return False
    if re.fullmatch(r"[a-f0-9]{24,}", local):
        return False
    suffix = domain.rsplit(".", 1)[-1]
    if not suffix.isalpha() or len(suffix) < 2:
        return False
    if re.search(r"@[\d.]+$", email):
        return False
    return not any(email.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".css", ".js", ".svg", ".webp"))


def normalize_phone(phone: str) -> str:
    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)
    if not (8 <= len(digits) <= 15):
        return ""
    if len(set(digits)) <= 2:
        return ""
    has_phone_shape = raw.startswith("+") or any(ch in raw for ch in " -().") or len(digits) <= 10
    if not has_phone_shape:
        return ""
    if raw.startswith("00") and not raw.startswith("+"):
        return ""
    return ("+" + digits) if raw.startswith("+") else digits


def extract_contacts(text: str) -> Contacts:
    emails = {clean_email(e) for e in EMAIL_RE.findall(text or "")}
    emails = {e for e in emails if valid_email(e)}
    phones = {normalize_phone(p) for p in PHONE_RE.findall(text or "")}
    phones = {p for p in phones if p}
    return Contacts(emails=emails, phones=phones)


def merge_contacts(target: Contacts, found: Contacts, source: str) -> None:
    target.add_emails(found.emails, source)
    target.add_phones(found.phones)


def normalize_domain(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or parsed.path or "").lower().replace("www.", "")
        host = host.split("/")[0].split(":")[0]
        ext = tldextract.extract(host)
        if not ext.domain:
            return ""
        domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        if any(domain == b or domain.endswith("." + b) for b in OTA_AND_DIRECTORY_BLOCKLIST):
            return ""
        return domain
    except Exception:
        return ""


def ddgs_search(query: str, max_results: int, timeout: int) -> List[dict]:
    try:
        with DDGS(timeout=timeout) as ddgs:
            return list(ddgs.text(query, max_results=max_results, backend="auto", safesearch="off"))
    except Exception:
        return []


def discover_domain(name: str, business_type: str, max_results: int, timeout: int, address: str = "") -> str:
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", name) if len(t) >= 4]
    candidates = []
    query = f'"{name}" "{business_type}" "{address}" official website' if address else f'"{name}" "{business_type}" official website'
    for result in ddgs_search(query, max_results=max_results, timeout=timeout):
        domain = normalize_domain(result.get("href") or result.get("url") or "")
        if not domain:
            continue
        blob = f"{result.get('title','')} {result.get('body','')} {domain}".lower()
        score = 0
        if any(tok in domain for tok in tokens):
            score -= 3
        if any(tok in blob for tok in tokens):
            score -= 1
        if tokens and score == 0:
            continue
        candidates.append((score, domain))
    if not candidates:
        return ""
    candidates.sort(key=lambda x: (x[0], x[1]))
    return candidates[0][1]


def role_query_for_type(business_type: str) -> str:
    key = normalize_key(business_type)
    for token, query in ROLE_QUERIES.items():
        if token in key:
            return query
    return ROLE_QUERIES["default"]


def parse_person_name(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s*[-|]\s*LinkedIn.*$", "", text, flags=re.IGNORECASE)
    for part in re.split(r"[|/]", cleaned):
        m = NAME_RE.search(part.strip())
        if m:
            return f"{m.group(1)} {m.group(2)}"
    return ""


def discover_decision_maker(name: str, business_type: str, max_results: int, timeout: int) -> str:
    role_query = role_query_for_type(business_type)
    query = f'site:linkedin.com/in/ {role_query} "{name}"'
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", name) if len(t) >= 4]
    for result in ddgs_search(query, max_results=max_results, timeout=timeout):
        href = (result.get("href") or result.get("url") or "").lower()
        if "linkedin.com/in/" not in href:
            continue
        blob = f"{result.get('title','')} {result.get('body','')}".lower()
        if tokens and not any(t in blob for t in tokens):
            continue
        person = parse_person_name(result.get("title") or "") or parse_person_name(result.get("body") or "")
        if person:
            return person
    return ""


def discover_external_profile_emails(
    name: str,
    domain: str,
    business_type: str,
    max_results: int,
    timeout: int,
) -> Contacts:
    contacts = Contacts()
    if not name:
        return contacts

    queries = [
        f'"{name}" "@{domain}"' if domain else f'"{name}" email',
        f'"{name}" "{business_type}" email',
        f'"{name}" (email OR contact) (LinkedIn OR RocketReach OR Apollo OR SignalHire OR Lusha)',
        f'site:rocketreach.co "{name}" email',
        f'site:linkedin.com/in/ "{name}" "{business_type}"',
    ]
    for query in queries:
        for result in ddgs_search(query, max_results=max_results, timeout=timeout):
            url = result.get("href") or result.get("url") or ""
            source_domain = normalize_domain(url) or (urlparse(url).netloc or "external").lower()
            blob = f"{result.get('title','')} {result.get('body','')} {url}"
            found = extract_contacts(blob)
            if not found.emails:
                continue
            for email in found.emails:
                email_domain = email.split("@", 1)[-1]
                if domain and email_domain != domain:
                    continue
                if source_domain in EXTERNAL_EMAIL_SOURCE_DOMAINS or (domain and email_domain == domain):
                    local = email.split("@", 1)[0]
                    if any(token in local for token in ("first", "last", "john", "jane", "example")):
                        continue
                    contacts.add_email(email, f"search:{source_domain}")
    return contacts


def generate_emails(person_name: str, domain: str) -> str:
    if not person_name or not domain:
        return ""
    tokens = re.findall(r"[A-Za-z'\-]+", person_name)
    if len(tokens) < 2:
        return ""
    first = re.sub(r"[^a-z]", "", tokens[0].lower())
    last = re.sub(r"[^a-z]", "", tokens[-1].lower())
    if not first or not last:
        return ""
    return " | ".join([f"{first}.{last}@{domain}", f"{first[0]}{last}@{domain}", f"{first}@{domain}"])


def fetch_html(session: requests.Session, url: str, timeout: int) -> str:
    try:
        r = session.get(url, headers=BROWSER_HEADERS, timeout=(5, timeout), allow_redirects=True)
        if r.status_code >= 400:
            return ""
        if "text/html" not in (r.headers.get("Content-Type") or "").lower() and "<html" not in r.text.lower():
            return ""
        return r.text or ""
    except Exception:
        return ""


def fetch_text_resource(session: requests.Session, url: str, timeout: int, max_bytes: int = 2_000_000) -> str:
    try:
        response = session.get(url, headers=BROWSER_HEADERS, timeout=(5, timeout), allow_redirects=True)
        if response.status_code >= 400:
            return ""
        content = response.content[:max_bytes]
        content_type = (response.headers.get("Content-Type") or "").lower()
        lower_url = url.lower().split("?", 1)[0]

        if lower_url.endswith(".pdf") or "application/pdf" in content_type:
            if PdfReader is None:
                return ""
            try:
                reader = PdfReader(io.BytesIO(content))
                return "\n".join((page.extract_text() or "") for page in reader.pages[:5])
            except Exception:
                return ""

        if lower_url.endswith(".txt") or "text/plain" in content_type or "xml" in content_type:
            return content.decode(response.encoding or "utf-8", errors="ignore")
    except Exception:
        return ""
    return ""


def domain_matches(url: str, domain: str) -> bool:
    host = (urlparse(url).netloc or "").lower().replace("www.", "")
    return host == domain or host.endswith("." + domain)


def priority_links(base_url: str, html: str, domain: str, max_pages: int) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select("a[href]"):
        link = urljoin(base_url, a.get("href") or "")
        if not link.startswith("http") or not domain_matches(link, domain):
            continue
        path = (urlparse(link).path or "").lower()
        score = 1
        if any(k in path for k in LIKELY_SUBPAGE_PATHS):
            score = 0
        links.append((score, link))
    links = sorted(set(links), key=lambda x: (x[0], x[1]))
    return [u for _, u in links[:max_pages]]


def discover_sitemap_and_robot_urls(session: requests.Session, domain: str, timeout: int, max_urls: int) -> List[str]:
    candidates = [
        f"https://{domain}/sitemap.xml",
        f"https://{domain}/sitemap_index.xml",
        f"https://{domain}/robots.txt",
    ]
    discovered = []
    for url in candidates:
        text = fetch_text_resource(session, url, timeout=timeout)
        if not text:
            continue
        for match in re.findall(r"https?://[^\s<>'\"]+", text):
            clean_url = html.unescape(match).strip()
            if domain_matches(clean_url, domain):
                path = urlparse(clean_url).path.lower()
                if any(k in path for k in LIKELY_SUBPAGE_PATHS) or path.endswith(DOCUMENT_EXTENSIONS):
                    discovered.append(clean_url)
        if url.endswith("robots.txt"):
            for sitemap in re.findall(r"(?im)^sitemap:\s*(\S+)", text):
                if domain_matches(sitemap, domain):
                    discovered.append(sitemap.strip())
    return sorted(set(discovered))[:max_urls]


def discover_document_urls(name: str, domain: str, max_results: int, timeout: int) -> List[str]:
    if not domain:
        return []
    queries = [
        f'site:{domain} filetype:pdf email',
        f'site:{domain} filetype:pdf "@{domain}"',
        f'"{name}" "@{domain}" filetype:pdf',
        f'site:{domain} (contact OR press OR media OR menu OR brochure) filetype:pdf',
    ]
    urls = []
    for query in queries:
        for result in ddgs_search(query, max_results=max_results, timeout=timeout):
            url = result.get("href") or result.get("url") or ""
            if url and domain_matches(url, domain):
                urls.append(url)
    return sorted(set(urls))[:max_results]


def seeded_subpage_urls(domain: str, max_pages: int) -> List[str]:
    urls = [f"https://{domain}", f"http://{domain}"]
    for path in LIKELY_SUBPAGE_PATHS:
        urls.append(f"https://{domain}/{path}")
    return urls[: max(max_pages + 4, 8)]


def scrape_public_contacts(
    domain: str,
    timeout: int,
    max_pages: int,
    name: str = "",
    deep_email_search: bool = False,
    search_timeout: int = 5,
    max_search_results: int = 3,
) -> Contacts:
    contacts = Contacts()
    if not domain:
        return contacts
    session = requests.Session()
    seeds = seeded_subpage_urls(domain, max_pages=max_pages)
    if deep_email_search:
        seeds.extend(discover_sitemap_and_robot_urls(session, domain, timeout=timeout, max_urls=max_pages * 2))
        seeds.extend(discover_document_urls(name, domain, max_results=max_search_results, timeout=search_timeout))
    visited = set()
    for seed in seeds:
        if seed in visited:
            continue
        visited.add(seed)
        if seed.lower().split("?", 1)[0].endswith(DOCUMENT_EXTENSIONS):
            text_resource = fetch_text_resource(session, seed, timeout=timeout)
            if not text_resource:
                continue
            found = extract_contacts(text_resource)
            merge_contacts(contacts, found, seed)
            continue

        html = fetch_html(session, seed, timeout=timeout)
        if not html:
            continue
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        found = extract_contacts(f"{html} {text}")
        merge_contacts(contacts, found, seed)

        soup = BeautifulSoup(html, "html.parser")
        for mailto in soup.select("a[href^='mailto:']"):
            email = (mailto.get("href") or "").replace("mailto:", "").split("?")[0]
            contacts.add_email(email, f"mailto:{seed}")
        for tel in soup.select("a[href^='tel:']"):
            contacts.add_phone((tel.get("href") or "").replace("tel:", ""))

        for link in priority_links(seed, html, domain, max_pages=max_pages):
            if link in visited:
                continue
            visited.add(link)
            if link.lower().split("?", 1)[0].endswith(DOCUMENT_EXTENSIONS):
                doc_text = fetch_text_resource(session, link, timeout=timeout)
                if doc_text:
                    merge_contacts(contacts, extract_contacts(doc_text), link)
                continue
            sub_html = fetch_html(session, link, timeout=timeout)
            if not sub_html:
                continue
            sub_text = BeautifulSoup(sub_html, "html.parser").get_text(" ", strip=True)
            sub_found = extract_contacts(f"{sub_html} {sub_text}")
            merge_contacts(contacts, sub_found, link)
    return contacts


def pick_emails(domain: str, emails: Iterable[str]) -> str:
    cleaned = sorted(set(clean_email(e) for e in emails if valid_email(clean_email(e))))
    same_domain = [e for e in cleaned if domain and e.endswith("@" + domain)]
    role = [e for e in same_domain if re.match(r"^(info|contact|hello|sales|booking|reservations|enquiry|inquiry|admin)@", e)]
    ordered = role + [e for e in same_domain if e not in role] + [e for e in cleaned if e not in same_domain]
    return " | ".join(ordered[:10])


def email_sources_summary(contacts: Contacts, max_items: int = 10) -> str:
    parts = []
    for email in sorted(contacts.emails)[:max_items]:
        sources = sorted(contacts.email_sources.get(email, []))[:3]
        if sources:
            parts.append(f"{email} <= {', '.join(sources)}")
        else:
            parts.append(email)
    return " | ".join(parts)


def pick_phone(phones: Iterable[str]) -> str:
    return sorted(set(phones))[0] if phones else ""


def enrich_target(
    target: Target,
    business_type: str,
    max_search_results: int,
    search_timeout: int,
    request_timeout: int,
    max_pages: int,
    domain_cache: Dict[str, str],
    contact_cache: Dict[str, Contacts],
    deep_email_search: bool = False,
) -> Dict[str, str]:
    key = hashlib.sha1(f"{target.name}|{business_type}".encode("utf-8")).hexdigest()
    domain = domain_cache.get(key)
    if domain is None:
        domain = normalize_domain(target.website) if target.website else ""
        if not domain:
            domain = discover_domain(
                target.name,
                business_type,
                max_results=max_search_results,
                timeout=search_timeout,
                address=target.address,
            )
        domain_cache[key] = domain

    decision_maker = discover_decision_maker(target.name, business_type, max_results=max_search_results, timeout=search_timeout)
    generated = generate_emails(decision_maker, domain)

    contacts = contact_cache.get(domain) if domain else Contacts()
    if domain and contacts is None:
        contacts = scrape_public_contacts(
            domain,
            timeout=request_timeout,
            max_pages=max_pages,
            name=target.name,
            deep_email_search=deep_email_search,
            search_timeout=search_timeout,
            max_search_results=max_search_results,
        )
        contact_cache[domain] = contacts
    if contacts is None:
        contacts = Contacts()
    osm_email = clean_email(target.email)
    if osm_email and valid_email(osm_email):
        contacts.add_email(osm_email, "osm")
    osm_phone = normalize_phone(target.phone)
    if osm_phone:
        contacts.add_phone(osm_phone)

    if deep_email_search:
        external_contacts = discover_external_profile_emails(
            target.name,
            domain,
            business_type,
            max_results=max(3, min(max_search_results, 8)),
            timeout=search_timeout,
        )
        for email, sources in external_contacts.email_sources.items():
            for source in sources:
                contacts.add_email(email, source)

    return {
        "Distance (km)": f"{target.distance_km:.3f}",
        "Business Name": target.name,
        "Business Type": business_type,
        "Address": target.address,
        "Domain": domain,
        "Decision Maker Name": decision_maker,
        "Generated Emails": generated,
        "Real Found Emails": pick_emails(domain, contacts.emails),
        "Public Emails": pick_emails(domain, contacts.emails),
        "Email Sources": email_sources_summary(contacts),
        "Phone Number": pick_phone(contacts.phones),
        "Latitude": f"{target.lat:.7f}",
        "Longitude": f"{target.lon:.7f}",
        "Source": target.source,
    }


def write_csv(path: str, rows: List[Dict[str, str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Free worldwide radial lead scraper")
    parser.add_argument(
        "--address",
        default="",
        help="Seed address, landmark, or coordinates. Add city/country for best results.",
    )
    parser.add_argument("--place", default="", help="Optional place/landmark/business name, e.g. Marina Bay Sands")
    parser.add_argument("--street", default="", help="Optional street address, e.g. 10 Bayfront Avenue")
    parser.add_argument("--city", default="", help="Optional city, e.g. Singapore")
    parser.add_argument("--region", default="", help="Optional state/region, e.g. NY or Jakarta Pusat")
    parser.add_argument("--postal-code", default="", help="Optional postal or ZIP code")
    parser.add_argument("--country", default="", help="Optional country, e.g. Singapore, Indonesia, USA")
    parser.add_argument("--coords", default="", help="Optional latitude,longitude. This is the most precise input.")
    parser.add_argument("--type", required=True, dest="business_type", help="Business type, e.g. hotel, dental clinic, cafe")
    parser.add_argument("--radius-km", type=float, default=DEFAULT_RADIUS_KM)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--output", default="", help="CSV output path")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--max-search-results", type=int, default=8)
    parser.add_argument(
        "--deep-email-search",
        action="store_true",
        help="Slower: searches external public profile/search-result pages for additional found emails.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_input = args.coords.strip() or args.address.strip() or build_structured_address(
        place=args.place,
        street=args.street,
        city=args.city,
        region=args.region,
        country=args.country,
        postal_code=args.postal_code,
    )
    if not seed_input:
        log("[FATAL] Enter --address, --coords, or structured fields like --street --city --country.")
        return

    output = args.output or f"leads_{slugify(args.business_type)}_{slugify(seed_input)[:32]}.csv"
    search_timeout = 5 if args.fast else 10
    request_timeout = 8 if args.fast else 16
    overpass_timeout = 18 if args.fast else 50
    max_pages = 2 if args.fast else 6
    workers = max(1, min(args.workers, 16))

    log(f"Business type: {args.business_type}")
    log(f"Radius km: {args.radius_km} | Limit: {args.limit} | Workers: {workers} | Fast: {args.fast}")

    try:
        targets = discover_targets(
            address=seed_input,
            business_type=args.business_type,
            radius_km=args.radius_km,
            limit=args.limit,
            timeout=overpass_timeout,
        )
    except RuntimeError as exc:
        log(f"[FATAL] {exc}")
        write_csv(output, [])
        log(f"Empty CSV written: {output}")
        return
    log(f"Targets discovered: {len(targets)}")
    if not targets:
        write_csv(output, [])
        log(f"No targets found. Empty CSV written: {output}")
        return

    domain_cache: Dict[str, str] = {}
    contact_cache: Dict[str, Contacts] = {}
    rows: List[Optional[Dict[str, str]]] = [None] * len(targets)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {
            executor.submit(
                enrich_target,
                target,
                args.business_type,
                args.max_search_results,
                search_timeout,
                request_timeout,
                max_pages,
                domain_cache,
                contact_cache,
                args.deep_email_search,
            ): idx
            for idx, target in enumerate(targets)
        }
        for completed, future in enumerate(as_completed(future_map), start=1):
            idx = future_map[future]
            target = targets[idx]
            try:
                rows[idx] = future.result()
            except Exception as exc:
                log(f"[ERROR] {target.name}: {type(exc).__name__}")
                rows[idx] = {
                    "Distance (km)": f"{target.distance_km:.3f}",
                    "Business Name": target.name,
                    "Business Type": args.business_type,
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
            log(f"[ENRICHED {completed}/{len(targets)}] {target.name}")

    final_rows = [r for r in rows if r is not None]
    write_csv(output, final_rows)
    log(f"Done. CSV written: {output}")


if __name__ == "__main__":
    main()
