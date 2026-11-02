"""Add persisted cancer-demo scenario and reproducible signal score."""
from alembic import op
from sqlalchemy import Column, Integer, JSON, String, inspect

revision = "0002_cancer_demo_report"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    screening_columns = {column["name"] for column in inspector.get_columns("screening_records")}
    risk_column_info = inspector.get_columns("risk_assessments")
    risk_columns = {column["name"] for column in risk_column_info}
    if "scenario" not in screening_columns:
        op.add_column("screening_records", Column("scenario", String(40), nullable=False, server_default="Balanced demo"))
    if "selected_panels" not in screening_columns:
        op.add_column("screening_records", Column("selected_panels", JSON, nullable=False, server_default="[]"))
    if "signal_score" not in risk_columns:
        op.add_column("risk_assessments", Column("signal_score", Integer, nullable=False, server_default="0"))
    # A fresh database is created from the current models by 0001, where this
    # column is already String(100). Only upgrade older schemas that used 30.
    category_column = next((column for column in risk_column_info if column["name"] == "category"), None)
    category_length = getattr(category_column["type"], "length", None) if category_column else None
    if bind.dialect.name == "mysql" and category_length and category_length < 100:
        op.alter_column("risk_assessments", "category", existing_type=String(30), type_=String(100), existing_nullable=False)

def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    screening_columns = {column["name"] for column in inspector.get_columns("screening_records")}
    risk_columns = {column["name"] for column in inspector.get_columns("risk_assessments")}
    if "signal_score" in risk_columns: op.drop_column("risk_assessments", "signal_score")
    if "selected_panels" in screening_columns: op.drop_column("screening_records", "selected_panels")
    if "scenario" in screening_columns: op.drop_column("screening_records", "scenario")
    category_column = next((column for column in inspector.get_columns("risk_assessments") if column["name"] == "category"), None)
    category_length = getattr(category_column["type"], "length", None) if category_column else None
    if bind.dialect.name == "mysql" and category_length and category_length >= 100:
        op.alter_column("risk_assessments", "category", existing_type=String(100), type_=String(30), existing_nullable=False)
