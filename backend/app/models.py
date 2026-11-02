from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now(): return datetime.now(timezone.utc)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now, nullable=False)

class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    facilities: Mapped[list["Facility"]] = relationship(back_populates="organization")

class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="Research/demo user", index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="1")

class EmailOTPChallenge(Base):
    __tablename__ = "email_otp_challenges"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    otp_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_ticket_hash: Mapped[str | None] = mapped_column(String(64))
    ticket_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class Facility(Base, TimestampMixin):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(180), index=True)
    facility_type: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(300), default="Demo address")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source: Mapped[str] = mapped_column(String(80), default="synthetic demo")
    organization: Mapped[Organization | None] = relationship(back_populates="facilities")

class Participant(Base, TimestampMixin):
    __tablename__ = "participants"
    id: Mapped[int] = mapped_column(primary_key=True)
    pseudonymous_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    age: Mapped[int | None] = mapped_column(Integer)
    sex_context: Mapped[str | None] = mapped_column(String(50))
    location_consented: Mapped[bool] = mapped_column(Boolean, default=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    data_source: Mapped[str] = mapped_column(String(80), default="synthetic demo")

class ConsentRecord(Base, TimestampMixin):
    __tablename__ = "consent_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    participant_id: Mapped[int] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    consent_type: Mapped[str] = mapped_column(String(50), default="screening demo")
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

class ScreeningPanel(Base, TimestampMixin):
    __tablename__ = "screening_panels"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    sample_types: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

class ScreeningRecord(Base, TimestampMixin):
    __tablename__ = "screening_records"
    __table_args__ = (Index("ix_screening_date_status", "collected_at", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    record_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    participant_id: Mapped[int | None] = mapped_column(ForeignKey("participants.id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    scenario: Mapped[str] = mapped_column(String(40), default="Balanced demo")
    selected_panels: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="Pending review", index=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_source: Mapped[str] = mapped_column(String(80), default="synthetic demo")
    participant: Mapped["Participant | None"] = relationship()
    sample: Mapped["SampleRecord | None"] = relationship(back_populates="screening", cascade="all, delete-orphan", uselist=False)
    readings: Mapped[list["BiomarkerReading"]] = relationship(back_populates="screening", cascade="all, delete-orphan")
    assessments: Mapped[list["RiskAssessment"]] = relationship(back_populates="screening", cascade="all, delete-orphan")
    referrals: Mapped[list["Referral"]] = relationship(back_populates="screening")

class SampleRecord(Base, TimestampMixin):
    __tablename__ = "sample_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screening_records.id", ondelete="CASCADE"), unique=True, index=True)
    sample_type: Mapped[str] = mapped_column(String(30))
    collection_quality: Mapped[str | None] = mapped_column(String(80))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    screening: Mapped[ScreeningRecord] = relationship(back_populates="sample")

class BiomarkerDefinition(Base, TimestampMixin):
    __tablename__ = "biomarker_definitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    default_unit: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text, default="")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

class BiomarkerReading(Base, TimestampMixin):
    __tablename__ = "biomarker_readings"
    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screening_records.id", ondelete="CASCADE"), index=True)
    definition_id: Mapped[int | None] = mapped_column(ForeignKey("biomarker_definitions.id"))
    name: Mapped[str] = mapped_column(String(120))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30))
    data_source: Mapped[str] = mapped_column(String(80), default="synthetic demo")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    screening: Mapped[ScreeningRecord] = relationship(back_populates="readings")

class RiskRuleSet(Base, TimestampMixin):
    __tablename__ = "risk_rule_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40), index=True)
    config: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

class RiskAssessment(Base, TimestampMixin):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screening_records.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(100))
    signal_score: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[dict] = mapped_column(JSON)
    missing_inputs: Mapped[list] = mapped_column(JSON, default=list)
    rule_version: Mapped[str] = mapped_column(String(40))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    screening: Mapped[ScreeningRecord] = relationship(back_populates="assessments")

class HealthcareFacility(Base, TimestampMixin):
    __tablename__ = "healthcare_facilities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    facility_type: Mapped[str] = mapped_column(String(80))
    address: Mapped[str] = mapped_column(String(300))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    contact_details: Mapped[str | None] = mapped_column(String(160))
    data_source: Mapped[str] = mapped_column(String(80), default="synthetic demo")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

class Referral(Base, TimestampMixin):
    __tablename__ = "referrals"
    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screening_records.id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("healthcare_facilities.id"))
    reason: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(30), default="Pending review")
    status: Mapped[str] = mapped_column(String(40), default="Draft", index=True)
    status_history: Mapped[list] = mapped_column(JSON, default=list)
    screening: Mapped[ScreeningRecord] = relationship(back_populates="referrals")

class FollowUp(Base, TimestampMixin):
    __tablename__ = "follow_ups"
    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screening_records.id", ondelete="CASCADE"), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40), default="Pending")
    notes: Mapped[str | None] = mapped_column(Text)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    object_type: Mapped[str] = mapped_column(String(100))
    object_id: Mapped[str | None] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
