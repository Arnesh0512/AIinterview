# AIinterview Backend

FastAPI backend for AI-supported interview preparation and contests. It provides candidate and admin workflows for resume, GitHub, coding, and concept interviews, plus multi-round contests and leaderboards.

## Features

- Google sign-in and JWT authentication for candidates and admins
- Candidate profile registration and updates
- Resume upload and resume-based interview questions, answers, feedback, and progress
- GitHub repository interview sessions and progress
- Coding and concept practice sessions, retries, feedback, and progress comparisons
- Contest registration and resume, coding, concept, and HR rounds
- Admin contest management, round evaluation, and leaderboards
- Constants APIs for companies, topics, difficulties, languages, roles, skills, and tags
- MongoDB/GridFS storage for documents and contest media

## Stack

- Python 3.11, FastAPI, Uvicorn
- MongoDB and GridFS through PyMongo
- OpenAI API and Google ID-token validation
- PyMuPDF, Tesseract, Poppler, and `pdf2image` for PDF extraction/OCR
- `python-jose` for JWTs

## Project layout

```text
.
├── src/
│   ├── main.py          # FastAPI app and router registration
│   ├── routes/          # API endpoints
│   ├── schemas/         # Request schemas
│   ├── utils/           # Environment, database, and shared utilities
│   ├── verify/          # Google/JWT and entity validation
│   └── templates/       # Custom Swagger UI page
├── documentation/       # Project documentation
├── googleSign/          # Google sign-in sample frontend
├── requirements.txt
├── Dockerfile
└── render.yaml
```

## Configuration

Create a private `.env` file in the repository root for local development. `python-dotenv` loads these variables through `src/utils/reader.py`.

```env
connection_string=<mongodb-connection-uri>
GOOGLE_CLIENT_ID=<google-oauth-client-id>
JWT_SECRET=<long-random-secret>
JWT_ALGO=HS256
Frontend=http://localhost:5173
OPENAI_API_KEY=<openai-api-key>
GITHUB_API_KEY=<github-token>
```

Do not commit real credentials. The CORS origins are currently listed directly in `src/main.py`; changing `Frontend` in `.env` does not update that allowlist. Add the deployed frontend origin to the `origins` list in `src/main.py` when needed.

## Run locally

From the repository root, install dependencies, then start Uvicorn from `src` so the route imports and custom Swagger template resolve correctly:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Set-Location src
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open the custom API docs at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). The default OpenAPI schema is available at `/openapi.json`.

## API overview

All routes are relative to the API origin. Protected routes use `Authorization: Bearer <JWT>`.

| Prefix | Purpose |
| --- | --- |
| `/auth` | Exchange Google ID tokens for candidate or admin JWTs |
| `/candidate` | Candidate profile registration, updates, and profile retrieval |
| `/admin` | Admin profile and contest creation, evaluation, and results |
| `/resume` | Resume uploads, interview sessions, feedback, and progress |
| `/github` | Repository interview sessions, feedback, and progress |
| `/coding` | Coding practice questions, answers, retries, and progress |
| `/concept` | Concept practice questions, answers, retries, and progress |
| `/contest` | Contest discovery, registration, round submissions, and leaderboards |
| `/constants` | Shared selector values for frontend forms |
| `/dev` | Development token and voice helpers |

## Render deployment

The repository has a Dockerfile that installs the OS packages used for PDF/OCR and starts the application from `/app/src` using Render’s `PORT` variable. For the complete OCR runtime, deploy as a **Docker Web Service** with repository root `.` and Dockerfile path `./Dockerfile`.

The current `render.yaml` still configures Render’s native Python runtime with a root-level `uvicorn main:app` start command. That command cannot import the app because `main.py` is under `src`. If deploying through the Blueprint instead, update the service configuration to use Docker or set its Python start command to `cd src && uvicorn main:app --host 0.0.0.0 --port $PORT`.

Add these environment variables in Render’s service settings:

- `connection_string`
- `GOOGLE_CLIENT_ID`
- `JWT_SECRET`
- `JWT_ALGO` (usually `HS256`)
- `OPENAI_API_KEY`
- `GITHUB_API_KEY`
- `Frontend` (read by the app, but CORS is currently hard-coded in `src/main.py`)

## Security notes

- `/dev/generate-candidate-token` can create a candidate record and return a JWT using only an email query parameter. `/dev/generate-admin-token` can issue an admin JWT for an existing admin email. These routes do not require a Google ID token; disable or protect them before exposing a production deployment.
- Keep MongoDB, Google, JWT, OpenAI, and GitHub credentials in environment settings, not source control.
- Do not commit `.env`, local runtime files, or uploaded user media.
