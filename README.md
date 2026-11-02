# Oralytics

**Smarter Oral Health Screening Starts Here.** Oralytics is a synthetic oral-health screening and health-intelligence prototype. It demonstrates how a hypothetical biosensor display, deterministic demo signals, transparent workflow review, geographic facility discovery, and referrals could work together.

> **Prototype only:** no physical biosensor or biological analysis exists. All readings, reports, facilities, activity metrics, and locations are synthetic. Scores are not cancer probabilities, diagnoses, medical advice, or clinically validated results.

## Project layout

- `frontend/` — React 19, Vite, TypeScript, Tailwind CSS, React Router, Recharts, Leaflet, Lucide, React Hook Form, and Zod.
- `backend/` — FastAPI, Pydantic, SQLAlchemy, bcrypt, JWT, and Alembic migrations.
- `backend/app/services/cancer_simulation.py` — deterministic, versioned synthetic signal generator.
- `backend/sql/create_database.sql` — MySQL database creation statement.
- MySQL is required for backend operation. The local database schema remains named `biosentry` to preserve the existing project data and migration history.

## Windows setup (MySQL)

Required: Node.js 20+, Python 3.11+, and MySQL Server 8.0+. Start the MySQL80 service if it is stopped.

### 1. Create the database and least-privileged app user

Run the setup helper from an activated backend environment. It asks for the MySQL administrator password through a hidden terminal prompt, creates the `biosentry` schema, generates a random app-user password, and writes the connection string and JWT secret to the ignored local `backend\.env` file. No password needs to be placed in shell history or chat.

```powershell
cd D:\biosentry\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py scripts\init_mysql.py
```

The app account is limited to the existing schema. Keep `backend\.env` local and do not commit it.

### 2. Apply migrations and start the API

```powershell
py -m alembic upgrade head
uvicorn app.main:app --reload
```

The API health endpoint is `http://localhost:8000/api/health`; interactive OpenAPI documentation is `http://localhost:8000/docs`.

### Email verification (registration OTP)

Registration sends a six-digit one-time code through SMTP. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL` in the ignored `backend\.env` file. Use either STARTTLS (`SMTP_STARTTLS=true`, `SMTP_USE_SSL=false`) or implicit TLS (`SMTP_STARTTLS=false`, `SMTP_USE_SSL=true`) according to your mail provider. Restart the API after changing mail settings. Codes expire after 10 minutes, resend is rate-limited, and registration requires a verified, short-lived ticket.
## Frontend

Open a second PowerShell terminal. Do not open `index.html` directly; Vite must serve the TypeScript module entry point.

```powershell
cd D:\biosentry\frontend
Copy-Item .env.example .env.local
npm install
npm run dev
```

Open the exact URL printed by Vite (normally `http://localhost:5173/`). Set `VITE_API_URL` in `.env.local` if the backend uses another URL.

## API and persistence

- `GET /api/health`
- `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`
- `POST /api/v1/screenings/analyze` — validates consent and context, creates a persisted screening, signal readings, explanation, and rule version.
- `GET /api/v1/screenings` and `GET /api/v1/screenings/{record_code}/report` — retrieve the same stored report after refresh.
- `GET /api/v1/facilities`
- `GET /api/v1/referrals`, `POST /api/v1/referrals`, `PATCH /api/v1/referrals/{id}/status`
- `GET /api/v1/admin/users`, `GET /api/v1/admin/rules` — administrator-only.

Registration cannot grant administrator access. The API stores a one-way bcrypt password hash and issues a short-lived JWT. The frontend keeps the token in session storage and clears it on a 401 response.

The cancer demo produces stable synthetic indicator values and a 0–100 prototype signal score from the selected demo preset and pseudonymous inputs. The scenario ranges and `cancer-demo-2026.10.1` rule version are explicit. The signal score is only a reproducible UI/workflow value; it has no biologically meaningful or validated relationship to cancer. Missing age is returned as a data-quality warning.

## Checks

```powershell
cd D:\biosentry\frontend
npm run build

cd D:\biosentry\backend
py -m pytest
```

All test fixtures are synthetic. The browser dev server and API run in separate terminals.

## Common setup issues

- **Blank page from `file://`:** use `npm run dev` and open the Vite HTTP URL; browser modules do not load correctly from the file path.
- **`tsc` not found:** run `npm install` inside `frontend/` and retry `npm run build`.
- **MySQL access denied:** check the MySQL80 service and credentials, then update the ignored `backend\.env`; the project cannot create the schema without valid MySQL administrator privileges.
- **MySQL connection refused:** confirm the service is listening on port 3306 and `DATABASE_URL` points to `127.0.0.1`.
- **Alembic says database missing:** create `biosentry` before running `alembic upgrade head`.
- **CORS errors:** ensure backend `FRONTEND_ORIGINS` exactly matches the Vite origin.
