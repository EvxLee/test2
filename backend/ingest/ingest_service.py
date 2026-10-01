from __future__ import annotations
from typing import Optional, Iterable
from datetime import date
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Country, Location, Track, Stage, StartupCompany,
    Category, Client, Investor, Feature
)
from urllib.parse import urlparse

def first_present(row: dict, *keys):
    for k in keys:
        if k in row:
            v = row.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
    return None

def derive_domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    u = str(url).strip()
    if not u:
        return None
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    parsed = urlparse(u)
    host = parsed.netloc or parsed.path
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host if "." in host else None

def norm(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s or None

def norm_country_code(x: Optional[str]) -> Optional[str]:
    c = norm(x)
    if not c:
        return None
    return c.upper()[:2]

def as_int(x) -> Optional[int]:
    try:
        return int(str(x).strip())
    except Exception:
        return None

def as_date(x) -> Optional[date]:
    return None

def csvish_to_list(s: Optional[str]) -> list[str]:
    if not s:
        return []
    tmp = str(s).replace("|", ",").replace(";", ",")
    parts = [p.strip() for p in tmp.split(",")]
    return [p for p in parts if p]


def get_or_create_country(db: Session, code: Optional[str], name: Optional[str] = None, region: Optional[str] = None) -> Optional[Country]:
    code = norm_country_code(code)
    if not code:
        return None
    obj = db.execute(select(Country).where(Country.code == code)).scalar_one_or_none()
    if obj:
        return obj

    nm = norm(name) or code
    existing_by_name = db.execute(select(Country).where(Country.name == nm)).scalar_one_or_none()
    if existing_by_name and existing_by_name.code != code:
        nm = code
    obj = Country(code=code, name=nm, region=norm(region))
    db.add(obj)
    db.flush()
    return obj

def get_or_create_track(db: Session, track_name: Optional[str]) -> Optional[Track]:
    tn = norm(track_name)
    if not tn:
        return None
    obj = db.execute(select(Track).where(Track.track_name == tn)).scalar_one_or_none()
    if obj:
        return obj
    obj = Track(track_name=tn)
    db.add(obj)
    db.flush()
    return obj

def get_or_create_stage(db: Session, stage_name: Optional[str]) -> Optional[Stage]:
    sn = norm(stage_name)
    if not sn:
        return None
    obj = db.execute(select(Stage).where(Stage.stage_name == sn)).scalar_one_or_none()
    if obj:
        return obj
    obj = Stage(stage_name=sn)
    db.add(obj)
    db.flush()
    return obj

def get_or_create_location(db: Session, country_code: Optional[str], state_region: Optional[str], city: Optional[str]) -> Optional[Location]:
    cc = norm_country_code(country_code)
    st = norm(state_region)
    ct = norm(city)
    obj = db.execute(
        select(Location).where(
            Location.country_code == cc,
            Location.state_region == st,
            Location.city == ct,
        )
    ).scalar_one_or_none()
    if obj:
        return obj
    obj = Location(
        location_id=uuid.uuid4(),
        country_code=cc,
        state_region=st,
        city=ct,
    )
    db.add(obj)
    db.flush()
    return obj

def ensure_company_children(
    db: Session,
    company_id: int,
    categories: Iterable[str] = (),
    clients:    Iterable[str] = (),
    investors:  Iterable[str] = (),
    features:   Iterable[str] = (),
) -> None:
    for name in set(csvish_to_list(",".join(categories)) if isinstance(categories, list) else categories):
        n = norm(name)
        if not n:
            continue
        exists = db.execute(
            select(Category).where(Category.company_id == company_id, Category.category_name == n)
        ).scalar_one_or_none()
        if not exists:
            db.add(Category(company_id=company_id, category_name=n))

    for name in set(csvish_to_list(",".join(clients)) if isinstance(clients, list) else clients):
        n = norm(name)
        if not n:
            continue
        exists = db.execute(
            select(Client).where(Client.company_id == company_id, Client.client_name == n)
        ).scalar_one_or_none()
        if not exists:
            db.add(Client(company_id=company_id, client_name=n))

    for name in set(csvish_to_list(",".join(investors)) if isinstance(investors, list) else investors):
        n = norm(name)
        if not n:
            continue
        exists = db.execute(
            select(Investor).where(Investor.company_id == company_id, Investor.investor_name == n)
        ).scalar_one_or_none()
        if not exists:
            db.add(Investor(company_id=company_id, investor_name=n))

    for name in set(csvish_to_list(",".join(features)) if isinstance(features, list) else features):
        n = norm(name)
        if not n:
            continue
        exists = db.execute(
            select(Feature).where(Feature.company_id == company_id, Feature.feature_name == n)
        ).scalar_one_or_none()
        if not exists:
            db.add(Feature(company_id=company_id, feature_name=n))


EXPECTED_KEYS = {
    "Company Name", "Domain Name", "SwitchPitch Link", "Hubspot Link", "Track",
    "Website", "Short Description", "Description", "Stage", "Total Raised",
    "Founded", "Revenue Range", "Employees", "Min Employees", "Max Employees",
    "City", "State/Region", "Country", "Continent", "Categories", "LinkedIn",
    "Twitter", "Facebook", "Features", "Clients", "Investors", "Last Funding Date", "Highlights"
}

def upsert_company_from_row(db: Session, row: dict) -> StartupCompany:
    domain = norm(row.get("Domain Name"))
    if not domain:
        raise ValueError("Missing 'Domain Name' in row")

    track_obj  = get_or_create_track(db, row.get("Track"))
    stage_obj  = get_or_create_stage(db, row.get("Stage"))
    country    = get_or_create_country(db, row.get("Country"))
    location   = get_or_create_location(
        db,
        country_code=country.code if country else row.get("Country"),
        state_region=row.get("State/Region"),
        city=row.get("City"),
    )

    company = db.execute(
        select(StartupCompany).where(StartupCompany.domain_name == domain)
    ).scalar_one_or_none()

    def maybe_set(obj, attr, value):
        v = norm(value)
        if v:
            setattr(obj, attr, v)

    if company is None:
        company = StartupCompany(
            domain_name=domain,
            track=track_obj.track_id if track_obj else None,
            location_id=location.location_id if location else None,
            short_description=norm(row.get("Short Description")),
            description=norm(row.get("Description")),
            total_raised=None,  # TODO: parse if you want numeric
            founded=as_int(row.get("Founded")),
            revenue_range=norm(row.get("Revenue Range")),
            employees=as_int(row.get("Employees")),
            linkedin=norm(row.get("LinkedIn")),
            last_funding_date=as_date(row.get("Last Funding Date")),
            switchpitch_link=norm(row.get("SwitchPitch Link")),
            hubspot_link=norm(row.get("Hubspot Link")),
        )
        db.add(company)
        db.flush()
    else:
        if track_obj and company.track != track_obj.track_id:
            company.track = track_obj.track_id
        if location and company.location_id != location.location_id:
            company.location_id = location.location_id

        maybe_set(company, "short_description", row.get("Short Description"))
        maybe_set(company, "description",       row.get("Description"))
        maybe_set(company, "revenue_range",     row.get("Revenue Range"))
        maybe_set(company, "linkedin",          row.get("LinkedIn"))
        maybe_set(company, "switchpitch_link",  row.get("SwitchPitch Link"))
        maybe_set(company, "hubspot_link",      row.get("Hubspot Link"))

        f = as_int(row.get("Founded"))
        if f is not None:
            company.founded = f
        emp = as_int(row.get("Employees"))
        if emp is not None:
            company.employees = emp

    ensure_company_children(
        db,
        company.company_id,
        categories=csvish_to_list(row.get("Categories")),
        clients=csvish_to_list(row.get("Clients")),
        investors=csvish_to_list(row.get("Investors")),
        features=csvish_to_list(row.get("Features")),
    )

    return company
