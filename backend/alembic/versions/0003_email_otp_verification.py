"""Add email OTP challenges and verified-email account state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_email_otp_verification"
down_revision = "0002_cancer_demo_report"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "email_verified" not in user_columns:
        op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()))

    if "email_otp_challenges" not in inspect(bind).get_table_names():
        op.create_table(
            "email_otp_challenges",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=254), nullable=False),
            sa.Column("otp_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
            sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("verification_ticket_hash", sa.String(length=64), nullable=True),
            sa.Column("ticket_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_email_otp_challenges_email", "email_otp_challenges", ["email"], unique=True)


def downgrade():
    bind = op.get_bind()
    tables = inspect(bind).get_table_names()
    if "email_otp_challenges" in tables:
        op.drop_index("ix_email_otp_challenges_email", table_name="email_otp_challenges")
        op.drop_table("email_otp_challenges")
    columns = {column["name"] for column in inspect(bind).get_columns("users")}
    if "email_verified" in columns:
        op.drop_column("users", "email_verified")
