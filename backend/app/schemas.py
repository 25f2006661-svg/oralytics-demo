from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

PUBLIC_ROLES = {"Research/demo user", "Healthcare worker", "Clinician or reviewer"}

class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    organization: str | None = Field(default=None, max_length=160)
    role: str = "Research/demo user"
    password: str = Field(min_length=10, max_length=72)
    consent: bool
    email_verification_token: str = Field(min_length=40, max_length=100)

    @field_validator("role")
    @classmethod
    def no_public_admin(cls, value: str) -> str:
        if value not in PUBLIC_ROLES:
            return "Research/demo user"
        return value

class EmailOTPRequest(BaseModel):
    email: EmailStr

class EmailOTPVerify(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    role: str

class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class AnalyzeIn(BaseModel):
    sample_type: str = Field(pattern="^photo$")
    panels: list[str] = Field(min_length=1, max_length=6)
    scenario: str = Field(default="Balanced demo", pattern="^(Balanced demo|Lower review demo|Higher review demo)$")
    case_type: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    participant_code: str = Field(min_length=1, max_length=80)
    consent: bool
    collected_at: date

class AssessmentOut(BaseModel):
    category: str
    signal_score: int
    explanation: list[str]
    missing_inputs: list[str]
    rule_version: str
    is_simulated: bool = True
    disclaimer: str

class ScreeningOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    record_code: str
    status: str
    is_simulated: bool
    data_source: str
    collected_at: datetime

class ReferralIn(BaseModel):
    screening_id: int
    facility_id: int | None = None
    reason: str = Field(min_length=3, max_length=1000)
    priority: str = Field(default="Pending review", pattern="^(Low priority|Moderate priority|High priority|Pending review)$")
    status: str = Field(default="Draft", pattern="^(Draft|Pending review|Referred|Appointment recorded|Follow-up completed|Cancelled)$")

class ReferralStatusIn(BaseModel):
    status: str = Field(pattern="^(Draft|Pending review|Referred|Appointment recorded|Follow-up completed|Cancelled)$")
