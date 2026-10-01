from __future__ import annotations

from sqlalchemy import (
    Integer, String, Text, Date, DateTime, ForeignKey, Numeric, Index,
    UniqueConstraint, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, timezone

import uuid
from sqlalchemy.dialects.postgresql import UUID

from .db import Base

class Role(Base):
    __tablename__ = "roles"
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_name: Mapped[str | None] = mapped_column(String(100))
    access_level: Mapped[str | None] = mapped_column(String(50))

    users: Mapped[list["User"]] = relationship(back_populates="role_obj")

class User(Base):
    __tablename__ = "users"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[int | None] = mapped_column(ForeignKey("roles.role_id"))
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    name:  Mapped[str] = mapped_column(String(255), nullable=False)

    role_obj: Mapped[Role | None] = relationship(back_populates="users")

class Stage(Base):
    __tablename__ = "stages"
    stage_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Track(Base):
    __tablename__ = "tracks"
    track_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    track_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

class Country(Base):
    __tablename__ = "countries"
    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    region: Mapped[str | None] = mapped_column(String(120))

    __table_args__ = (
        CheckConstraint("code = upper(code)", name="ck_countries_code_upper"),
    )

    locations: Mapped[list["Location"]] = relationship(back_populates="country_obj")

class Location(Base):
    __tablename__ = "locations"

    location_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    country_code: Mapped[str | None] = mapped_column(
        ForeignKey("countries.code", ondelete="SET NULL"),
        type_=String(2),
        index=True,
    )

    state_region: Mapped[str | None] = mapped_column(String(120), index=True)
    city:         Mapped[str | None] = mapped_column(String(120), index=True)

    __table_args__ = (
        UniqueConstraint("country_code", "state_region", "city", name="uq_locations_triplet"),
        Index("ix_locations_triplet", "country_code", "state_region", "city"),
    )

    country_obj: Mapped["Country | None"] = relationship(back_populates="locations")
    companies:   Mapped[list["StartupCompany"]] = relationship(back_populates="location")


# CORE TABLE: STARTUP_COMPANIES

class StartupCompany(Base):
    __tablename__ = "startup_companies"
    # One row per startup
    company_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # FK: tracks.track_id
    track: Mapped[int | None] = mapped_column(ForeignKey("tracks.track_id"))

    # Normalized location link
    location_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("locations.location_id"), index=True
    )
    location: Mapped["Location | None"] = relationship(back_populates="companies")

    # Links / metadata
    switchpitch_link: Mapped[str | None] = mapped_column(String(512))
    domain_name: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    hubspot_link: Mapped[str | None] = mapped_column(String(512))
    short_description: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    total_raised: Mapped[Numeric | None] = mapped_column(Numeric(18, 2))
    founded: Mapped[int | None] = mapped_column(Integer)
    revenue_range: Mapped[str | None] = mapped_column(String(100))
    employees: Mapped[int | None] = mapped_column(Integer)
    linkedin: Mapped[str | None] = mapped_column(String(512))
    clients: Mapped[str | None] = mapped_column(Text)
    investors: Mapped[str | None] = mapped_column(Text)
    last_funding_date: Mapped[date | None] = mapped_column(Date)

    # ORM relationships
    track_obj: Mapped["Track | None"] = relationship()

    # One-to-many
    categories: Mapped[list["Category"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    client_rows: Mapped[list["Client"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    investor_rows: Mapped[list["Investor"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    feature_rows: Mapped[list["Feature"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    boards: Mapped[list["MondayBoard"]] = relationship(back_populates="company", cascade="all, delete-orphan")

Index("ix_startup_companies_track", StartupCompany.track)
Index("ix_startup_companies_domain", StartupCompany.domain_name)

class Category(Base):
    __tablename__ = "categories"
    category_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("startup_companies.company_id"), index=True)
    category_name: Mapped[str] = mapped_column(String(120), nullable=False)

    company: Mapped["StartupCompany"] = relationship(back_populates="categories")

    __table_args__ = (
        # Avoid duplicates
        UniqueConstraint("company_id", "category_name", name="uq_categories_company_name"),
    )


class Client(Base):
    __tablename__ = "clients"
    client_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("startup_companies.company_id"), index=True)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)

    company: Mapped["StartupCompany"] = relationship(back_populates="client_rows")

    __table_args__ = (
        UniqueConstraint("company_id", "client_name", name="uq_clients_company_name"),
    )


class Investor(Base):
    __tablename__ = "investors"
    investor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("startup_companies.company_id"), index=True)
    investor_name: Mapped[str] = mapped_column(String(200), nullable=False)

    company: Mapped["StartupCompany"] = relationship(back_populates="investor_rows")

    __table_args__ = (
        UniqueConstraint("company_id", "investor_name", name="uq_investors_company_name"),
    )


class Feature(Base):
    __tablename__ = "features"
    feature_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("startup_companies.company_id"), index=True)
    feature_name: Mapped[str] = mapped_column(Text, nullable=False)

    company: Mapped["StartupCompany"] = relationship(back_populates="feature_rows")

    __table_args__ = (
        UniqueConstraint("company_id", "feature_name", name="uq_features_company_name"),
    )


# MONDAY.COM BOARD TABLES
class MondayBoard(Base):
    __tablename__ = "monday_board"
    board_id:   Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("startup_companies.company_id"), index=True)

    board_name: Mapped[str | None] = mapped_column(String(200))
    switchpitch_link: Mapped[str | None] = mapped_column(String(512))
    domain_name: Mapped[str | None] = mapped_column(String(255))
    hubspot_link: Mapped[str | None] = mapped_column(String(512))
    track: Mapped[str | None] = mapped_column(String(120))

    company: Mapped["StartupCompany | None"] = relationship(back_populates="boards")
    board_rows: Mapped[list["BoardData"]] = relationship(back_populates="board", cascade="all, delete-orphan")


class BoardData(Base):
    __tablename__ = "board_data"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), index=True)
    board_id: Mapped[int | None] = mapped_column(ForeignKey("monday_board.board_id"), index=True)

    board_name: Mapped[str | None] = mapped_column(String(200))
    group_ids: Mapped[str | None] = mapped_column(Text)
    workspace_id: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    board: Mapped["MondayBoard | None"] = relationship(back_populates="board_rows")


class PartnerAuditLog(Base):
    __tablename__ = "partner_audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    row_count: Mapped[int | None] = mapped_column(Integer)
    duplicate_count: Mapped[int | None] = mapped_column(Integer)


class ProjectPartnerStartup(Base):
    __tablename__ = "project_partner_startups"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "stage", "startup_name",
            name="uq_project_partner_startup",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    startup_name: Mapped[str] = mapped_column(Text, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
