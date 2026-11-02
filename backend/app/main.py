from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from secrets import randbelow, token_hex, token_urlsafe
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .database import Base, engine, get_db
from .models import AuditLog, BiomarkerReading, ConsentRecord, EmailOTPChallenge, Facility, Participant, Referral, RiskAssessment, RiskRuleSet, SampleRecord, ScreeningPanel, ScreeningRecord, User
from .schemas import AnalyzeIn, AssessmentOut, AuthOut, EmailOTPRequest, EmailOTPVerify, LoginIn, ReferralIn, ReferralStatusIn, RegisterIn, ScreeningOut, UserOut
from .security import PUBLIC_ROLES, current_user, hash_password, issue_token, optional_user, require_admin, verify_password
from .services.email_otp import EmailDeliveryError, deliver_email_otp
from .services.risk_engine import RULE_CONFIG, RULE_VERSION
from .services.cancer_simulation import RULE_VERSION as CANCER_RULE_VERSION, simulate as simulate_cancer

app = FastAPI(title="Oralytics API", version="0.1.0", description="Synthetic oral-health screening and health intelligence prototype API")
origins = [x.strip() for x in settings.frontend_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def initialize_demo_data():
    with Session(engine) as db:
        for code, name, samples in [
            ("oral-photo-review", "Oral photo review", ["photo"]),
        ]:
            if not db.scalar(select(ScreeningPanel).where(ScreeningPanel.code == code)):
                db.add(ScreeningPanel(code=code, name=name, sample_types=samples, is_simulated=True))
        if not db.scalar(select(RiskRuleSet).where(RiskRuleSet.version == RULE_VERSION)):
            db.add(RiskRuleSet(name="Synthetic workflow priority", version=RULE_VERSION, config=RULE_CONFIG, active=True))
        if not db.scalar(select(Facility).limit(1)):
            for name, kind, lat, lon in [
                ("Community Demo Centre", "Primary healthcare centre", 28.6139, 77.2090),
                ("North District Demo Hospital", "District hospital", 19.0760, 72.8777),
                ("Riverbend Primary Care", "Primary healthcare centre", 12.9716, 77.5946),
            ]:
                db.add(Facility(name=name, facility_type=kind, address="Synthetic demo location", latitude=lat, longitude=lon, is_simulated=True))
        db.commit()

@app.get("/health")
def health():
    return {"status": "ok", "environment": "synthetic demo", "clinical_validation": False}

app.add_api_route("/api/health", health, methods=["GET"], include_in_schema=False)

OTP_TTL = timedelta(minutes=10)
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
VERIFICATION_TICKET_TTL = timedelta(minutes=15)

def _now_utc():
    return datetime.now(timezone.utc)

def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def _otp_hash(email: str, code: str) -> str:
    material = f"oralytics-email-otp:{email}:{code}".encode()
    return hmac.new(settings.jwt_secret.encode(), material, hashlib.sha256).hexdigest()

def _ticket_hash(ticket: str) -> str:
    return hashlib.sha256(ticket.encode()).hexdigest()

@app.post("/api/v1/auth/email-otp/request")
def request_email_otp(data: EmailOTPRequest, db: Session = Depends(get_db)):
    email = str(data.email).strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")

    now = _now_utc()
    challenge = db.scalar(select(EmailOTPChallenge).where(EmailOTPChallenge.email == email).with_for_update())
    if challenge:
        last_sent = _aware(challenge.last_sent_at)
        remaining = OTP_RESEND_COOLDOWN_SECONDS - int((now - last_sent).total_seconds()) if last_sent else 0
        if remaining > 0:
            raise HTTPException(429, f"Wait {remaining} seconds before requesting another code.", headers={"Retry-After": str(remaining)})

    code = f"{randbelow(1_000_000):06d}"
    if challenge is None:
        challenge = EmailOTPChallenge(email=email, otp_hash=_otp_hash(email, code), expires_at=now + OTP_TTL,
                                      attempts=0, last_sent_at=now)
        db.add(challenge)
    else:
        challenge.otp_hash = _otp_hash(email, code)
        challenge.expires_at = now + OTP_TTL
        challenge.attempts = 0
        challenge.last_sent_at = now
        challenge.verified_at = None
        challenge.verification_ticket_hash = None
        challenge.ticket_expires_at = None
    db.commit()

    try:
        deliver_email_otp(email, code)
    except EmailDeliveryError as error:
        challenge.otp_hash = "0" * 64
        challenge.expires_at = now
        challenge.attempts = OTP_MAX_ATTEMPTS
        challenge.last_sent_at = now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
        db.commit()
        raise HTTPException(503, str(error)) from error

    return {"message": "Verification code sent.", "expires_in": int(OTP_TTL.total_seconds()),
            "retry_after": OTP_RESEND_COOLDOWN_SECONDS}

@app.post("/api/v1/auth/email-otp/verify")
def verify_email_otp(data: EmailOTPVerify, db: Session = Depends(get_db)):
    email = str(data.email).strip().lower()
    challenge = db.scalar(select(EmailOTPChallenge).where(EmailOTPChallenge.email == email).with_for_update())
    now = _now_utc()
    if challenge is None or challenge.attempts >= OTP_MAX_ATTEMPTS or _aware(challenge.expires_at) <= now:
        raise HTTPException(400, "The code is invalid or expired. Request a new code.")

    expected = _otp_hash(email, data.code)
    if not hmac.compare_digest(challenge.otp_hash, expected):
        challenge.attempts += 1
        if challenge.attempts >= OTP_MAX_ATTEMPTS:
            challenge.otp_hash = "0" * 64
            db.commit()
            raise HTTPException(429, "Too many incorrect codes. Request a new code.")
        db.commit()
        raise HTTPException(400, "That verification code is incorrect.")

    ticket = token_urlsafe(32)
    challenge.otp_hash = "0" * 64
    challenge.verified_at = now
    challenge.verification_ticket_hash = _ticket_hash(ticket)
    challenge.ticket_expires_at = now + VERIFICATION_TICKET_TTL
    db.commit()
    return {"verification_token": ticket, "expires_in": int(VERIFICATION_TICKET_TTL.total_seconds())}

def _consume_email_verification(db: Session, email: str, ticket: str) -> None:
    challenge = db.scalar(select(EmailOTPChallenge).where(EmailOTPChallenge.email == email).with_for_update())
    now = _now_utc()
    valid = (challenge is not None and challenge.verified_at is not None
             and challenge.verification_ticket_hash is not None
             and challenge.ticket_expires_at is not None
             and _aware(challenge.ticket_expires_at) > now
             and hmac.compare_digest(challenge.verification_ticket_hash, _ticket_hash(ticket)))
    if not valid:
        raise HTTPException(422, "Verify this email address before creating the account.")
    challenge.verification_ticket_hash = None
    challenge.ticket_expires_at = None
    challenge.verified_at = None

@app.post("/api/v1/auth/register", response_model=AuthOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if not data.consent:
        raise HTTPException(422, "Consent is required for the demo workspace")
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    _consume_email_verification(db, email, data.email_verification_token)
    user = User(full_name=data.full_name, email=email, phone=data.phone, password_hash=hash_password(data.password), role=data.role if data.role in PUBLIC_ROLES else "Research/demo user", email_verified=True)
    db.add(user); db.flush()
    db.add(AuditLog(actor_id=user.id, action="user.registered", object_type="user", object_id=str(user.id), details={"role": user.role}))
    db.commit(); db.refresh(user)
    return AuthOut(access_token=issue_token(user), user=user)

@app.post("/api/v1/auth/login", response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not user or not user.is_active or not user.email_verified or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return AuthOut(access_token=issue_token(user), user=user)

@app.get("/api/v1/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

@app.post("/api/v1/screenings/analyze")
def analyze(data: AnalyzeIn, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    if not data.consent:
        raise HTTPException(422, "Consent is required for a simulated screening record")
    if not data.consent:
        raise HTTPException(422, "Consent is required for a simulated screening record")
    assessment = simulate_cancer(sample_type=data.sample_type, panels=data.panels, scenario=data.scenario,
                                 participant_code=data.participant_code, age=data.age, collected_at=data.collected_at)
    code = "BS-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + token_hex(3).upper()
    participant = db.scalar(select(Participant).where(Participant.pseudonymous_code == data.participant_code))
    if not participant:
        participant = Participant(pseudonymous_code=data.participant_code, age=data.age, is_simulated=True, data_source="synthetic demo")
        db.add(participant); db.flush()
    db.add(ConsentRecord(participant_id=participant.id, consent_type="screening demo", granted=True, is_simulated=True))
    record = ScreeningRecord(record_code=code, created_by_id=user.id if user else None, participant_id=participant.id,
                             status="Pending review", scenario=data.scenario, selected_panels=data.panels,
                             collected_at=datetime.combine(data.collected_at, datetime.min.time(), tzinfo=timezone.utc),
                             is_simulated=True, data_source="synthetic demo")
    record.sample = SampleRecord(sample_type=data.sample_type, collection_quality="Recorded for simulation · not measured", is_simulated=True)
    record.assessments.append(RiskAssessment(category=assessment["category"], signal_score=assessment["signal_score"],
        explanation={"reasons": assessment["explanation"]}, missing_inputs=assessment["missing_inputs"],
        rule_version=assessment["rule_version"], is_simulated=True))
    for reading in assessment["readings"]:
        record.readings.append(BiomarkerReading(name=reading["name"], value=reading["value"], unit=reading["unit"],
            data_source="deterministic synthetic signal generator", is_simulated=True))
    db.add(record); db.flush()
    db.add(AuditLog(actor_id=user.id if user else None, action="screening.simulated", object_type="screening", object_id=code, details={"sample_type": data.sample_type, "panels": data.panels, "rule_version": RULE_VERSION}))
    db.commit(); db.refresh(record)
    return serialize_report(record)

def serialize_report(record: ScreeningRecord):
    assessment = record.assessments[0] if record.assessments else None
    return {"record": ScreeningOut.model_validate(record), "participant_code": record.participant.pseudonymous_code if record.participant else None, "selected_panels": record.selected_panels or [],
            "sample_type": record.sample.sample_type if record.sample else "unknown", "scenario": record.scenario,
            "readings": [{"name": r.name, "value": r.value, "unit": r.unit,
                          "explanation": "Deterministic synthetic display value; no biological or clinical meaning.",
                          "is_simulated": r.is_simulated} for r in record.readings],
            "assessment": {"category": assessment.category, "signal_score": assessment.signal_score,
                           "explanation": assessment.explanation.get("reasons", []),
                           "missing_inputs": assessment.missing_inputs, "rule_version": assessment.rule_version,
                           "is_simulated": True,
                           "disclaimer": "Prototype screening signal only. This is not a cancer probability, diagnosis, test result, or medical advice."} if assessment else None,
            "timestamp": record.created_at, "is_simulated": record.is_simulated}

@app.get("/api/v1/screenings/{record_code}/report")
def screening_report(record_code: str, db: Session = Depends(get_db), user: User | None = Depends(optional_user)):
    record = db.scalar(select(ScreeningRecord).where(ScreeningRecord.record_code == record_code, ScreeningRecord.is_simulated.is_(True)))
    if not record:
        raise HTTPException(404, "Screening report not found")
    return serialize_report(record)

@app.get("/api/v1/screenings")
def list_screenings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(ScreeningRecord).where(ScreeningRecord.is_simulated.is_(True)).order_by(ScreeningRecord.created_at.desc()).limit(200)
    return [serialize_report(record) for record in db.scalars(query)]

@app.get("/api/v1/risk-rules")
def risk_rules():
    return {"rule_version": RULE_VERSION, "configuration": RULE_CONFIG, "is_simulated": True}

@app.post("/api/v1/risk-assessment", response_model=AssessmentOut)
def risk_assessment(data: AnalyzeIn):
    if not data.consent:
        raise HTTPException(422, "Consent is required for a simulated assessment")
    result = simulate_cancer(sample_type=data.sample_type, panels=data.panels, scenario=data.scenario,
                             participant_code=data.participant_code, age=data.age, collected_at=data.collected_at)
    return result

@app.get("/api/v1/referrals")
def list_referrals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [{"id": r.id, "screening_id": r.screening_id, "facility_id": r.facility_id, "reason": r.reason,
             "priority": r.priority, "status": r.status, "status_history": r.status_history,
             "created_at": r.created_at, "updated_at": r.updated_at} for r in db.scalars(select(Referral).order_by(Referral.created_at.desc()).limit(200))]

@app.post("/api/v1/referrals", status_code=201)
def create_referral(data: ReferralIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    screening = db.get(ScreeningRecord, data.screening_id)
    if not screening or not screening.is_simulated:
        raise HTTPException(404, "Synthetic screening record not found")
    now = datetime.now(timezone.utc).isoformat()
    referral = Referral(screening_id=screening.id, facility_id=data.facility_id, reason=data.reason,
                        priority=data.priority, status=data.status,
                        status_history=[{"status": data.status, "at": now, "actor_id": user.id}])
    db.add(referral); db.flush()
    db.add(AuditLog(actor_id=user.id, action="referral.created", object_type="referral", object_id=str(referral.id), details={"status": data.status}))
    db.commit(); db.refresh(referral)
    return {"id": referral.id, "screening_id": referral.screening_id, "facility_id": referral.facility_id,
            "reason": referral.reason, "priority": referral.priority, "status": referral.status,
            "status_history": referral.status_history, "is_simulated": True}

@app.patch("/api/v1/referrals/{referral_id}/status")
def update_referral_status(referral_id: int, data: ReferralStatusIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    referral = db.get(Referral, referral_id)
    if not referral:
        raise HTTPException(404, "Referral not found")
    history = list(referral.status_history or [])
    history.append({"status": data.status, "at": datetime.now(timezone.utc).isoformat(), "actor_id": user.id})
    referral.status = data.status; referral.status_history = history
    db.add(AuditLog(actor_id=user.id, action="referral.status_changed", object_type="referral", object_id=str(referral.id), details={"status": data.status}))
    db.commit(); db.refresh(referral)
    return {"id": referral.id, "status": referral.status, "status_history": referral.status_history, "is_simulated": True}

@app.get("/api/v1/facilities")
def facilities(db: Session = Depends(get_db)):
    return [{"id": x.id, "name": x.name, "type": x.facility_type, "address": x.address, "latitude": x.latitude, "longitude": x.longitude, "data_source": x.data_source, "is_simulated": True} for x in db.scalars(select(Facility).where(Facility.is_simulated.is_(True)))]

@app.get("/api/v1/admin/users", response_model=list[UserOut])
def admin_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(User).order_by(User.created_at.desc())))

@app.get("/api/v1/admin/rules")
def admin_rules(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"version": x.version, "name": x.name, "active": x.active, "config": x.config, "created_at": x.created_at} for x in db.scalars(select(RiskRuleSet).order_by(RiskRuleSet.created_at.desc()))]
