"""Create the local BioSentry MySQL schema and a dedicated application user."""
from getpass import getpass
from os import environ
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote_plus

import pymysql

host = environ.get("MYSQL_HOST", "127.0.0.1")
port = int(environ.get("MYSQL_PORT", "3306"))
admin = environ.get("MYSQL_ADMIN", "root")
print(f"Using MySQL at {host}:{port} as {admin}.")
admin_password = getpass("MySQL administrator password (input is hidden): ")
app_password = token_urlsafe(36)

connection = pymysql.connect(host=host, port=port, user=admin, password=admin_password,
                             charset="utf8mb4", autocommit=True)
try:
    with connection.cursor() as cursor:
        cursor.execute("CREATE DATABASE IF NOT EXISTS biosentry CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cursor.execute("SELECT COUNT(*) FROM mysql.user WHERE user=%s AND host='localhost'", ("biosentry_app",))
        user_exists = cursor.fetchone()[0] > 0
        if user_exists:
            cursor.execute("ALTER USER 'biosentry_app'@'localhost' IDENTIFIED BY %s", (app_password,))
        else:
            cursor.execute("CREATE USER 'biosentry_app'@'localhost' IDENTIFIED BY %s", (app_password,))
        cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES ON biosentry.* TO 'biosentry_app'@'localhost'")
finally:
    connection.close()

env_path = Path(__file__).resolve().parents[1] / ".env"
existing = {}
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            existing[key.strip()] = value.strip()
existing["DATABASE_URL"] = f"mysql+pymysql://biosentry_app:{quote_plus(app_password)}@{host}:{port}/biosentry?charset=utf8mb4"
existing.setdefault("JWT_SECRET", token_urlsafe(48))
existing.setdefault("JWT_ALGORITHM", "HS256")
existing.setdefault("ACCESS_TOKEN_MINUTES", "30")
existing.setdefault("FRONTEND_ORIGINS", "http://localhost:5173")
env_path.write_text("# Local BioSentry configuration; do not commit.\n" + "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n", encoding="utf-8")
print(f"Created/verified MySQL database 'biosentry' and local application user. Configuration saved to {env_path}.")
