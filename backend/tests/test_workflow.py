import os
import uuid

os.environ["DATABASE_URL"] = "sqlite:///./biosentry-test.db"

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

command.upgrade(Config("alembic.ini"), "head")
from app.main import app


def test_cancer_screening_persistence_auth_and_referral(monkeypatch):
    sent_codes = []
    monkeypatch.setattr("app.main.deliver_email_otp", lambda email, code: sent_codes.append((email, code)))
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["clinical_validation"] is False

        email = f"reviewer-{uuid.uuid4().hex[:10]}@example.com"
        requested = client.post("/api/v1/auth/email-otp/request", json={"email": email})
        assert requested.status_code == 200, requested.text
        assert sent_codes and sent_codes[0][0] == email
        code = sent_codes[0][1]
        assert len(code) == 6 and code.isdigit()
        wrong = client.post("/api/v1/auth/email-otp/verify", json={"email": email, "code": "000000" if code != "000000" else "000001"})
        assert wrong.status_code == 400
        verified = client.post("/api/v1/auth/email-otp/verify", json={"email": email, "code": code})
        assert verified.status_code == 200, verified.text

        registration = client.post("/api/v1/auth/register", json={
            "full_name": "Synthetic Reviewer",
            "email": email,
            "password": "synthetic-demo-password",
            "role": "Research/demo user",
            "consent": True,
            "email_verification_token": verified.json()["verification_token"],
        })
        assert registration.status_code == 201, registration.text
        token = registration.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        payload = {
            "sample_type": "blood",
            "panels": ["Cancer-associated biomarker exploration"],
            "scenario": "Balanced demo",
            "age": 54,
            "participant_code": f"TEST-{uuid.uuid4().hex[:8]}",
            "consent": True,
            "collected_at": "2026-10-16",
        }
        first = client.post("/api/v1/screenings/analyze", json=payload, headers=headers)
        assert first.status_code == 200, first.text
        result = first.json()
        assert result["is_simulated"] is True
        assert 0 <= result["assessment"]["signal_score"] <= 100
        assert result["assessment"]["rule_version"].startswith("cancer-demo-")
        assert result["readings"]

        second = client.post("/api/v1/screenings/analyze", json=payload, headers=headers)
        assert second.status_code == 200
        assert second.json()["assessment"]["signal_score"] == result["assessment"]["signal_score"]
        assert second.json()["readings"] == result["readings"]

        report_url = f"/api/v1/screenings/{result['record']['record_code']}/report"
        stored = client.get(report_url, headers=headers)
        assert stored.status_code == 200
        assert stored.json()["assessment"] == result["assessment"]
        assert stored.json()["readings"] == result["readings"]

        history = client.get("/api/v1/screenings", headers=headers)
        assert history.status_code == 200
        assert any(item["record"]["record_code"] == result["record"]["record_code"] for item in history.json())

        facilities = client.get("/api/v1/facilities")
        assert facilities.status_code == 200 and facilities.json()
        referral = client.post("/api/v1/referrals", headers=headers, json={
            "screening_id": result["record"]["id"],
            "facility_id": facilities.json()[0]["id"],
            "reason": "Synthetic follow-up navigation",
            "priority": "Pending review",
            "status": "Draft",
        })
        assert referral.status_code == 201, referral.text
        referral_id = referral.json()["id"]
        updated = client.patch(f"/api/v1/referrals/{referral_id}/status", headers=headers, json={"status": "Referred"})
        assert updated.status_code == 200
        assert updated.json()["status"] == "Referred"


def test_screening_rejects_invalid_sample_and_missing_consent():
    with TestClient(app) as client:
        base = {"sample_type":"not-a-sample", "panels":["Cancer demo"], "scenario":"Balanced demo", "participant_code":"TEST-INVALID", "consent":True, "collected_at":"2026-10-16"}
        assert client.post("/api/v1/screenings/analyze", json=base).status_code == 422
        base["sample_type"] = "saliva"
        base["consent"] = False
        assert client.post("/api/v1/screenings/analyze", json=base).status_code == 422
