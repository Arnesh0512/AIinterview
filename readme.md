# AI Interview Backend

This repository contains the backend for an AI-powered interview platform built with FastAPI and MongoDB.

It supports candidate and admin workflows for profile setup, resume-based interviews, GitHub interviews, coding practice, concept practice, contest participation, contest evaluation, and leaderboard generation.

## Project Description

The backend is designed to power an interview preparation and assessment platform where:

- candidates can sign in, build profiles, upload resumes, practice interviews, and participate in contests
- admins can create contests, evaluate candidate performance, inspect responses, and publish results
- AI is used to generate questions, evaluate answers, and create progress feedback across attempts

The project combines document processing, AI evaluation, session-based interview flows, and contest management in one backend service.

## Features

### Authentication

- Google sign-in for candidates
- Google sign-in for admins
- JWT-based authenticated API access

### Candidate Profile

- candidate registration
- candidate profile update
- candidate profile fetch

### Resume Interview Flow

- upload PDF resumes
- extract and summarize resume content
- generate resume-based interview questions
- save answers question-wise
- submit sessions
- generate feedback and scores
- reattempt sessions
- progress tracking and stored progress history

### GitHub Interview Flow

- fetch repositories from a GitHub profile
- save repository interview roots
- generate repository-based question sessions
- save answers and submit sessions
- feedback generation
- progress and history tracking

### Coding Practice Flow

- create coding sets using filters
- generate coding interview sessions
- save code answers with language
- submit sessions
- generate feedback and scores
- retry and progress comparison

### Concept Practice Flow

- create topic-based concept sets
- generate conceptual question sessions
- save and submit answers
- generate feedback
- compare progress across attempts

### Contest Flow

- view available contests
- register and unregister
- participate in resume, coding, concept, and HR rounds
- submit files, text answers, and audio answers
- view round leaderboards and final leaderboard

### Admin Contest Management

- create contests
- list contests
- inspect contest details
- generate round results
- generate final leaderboard
- inspect candidate submissions
- stream candidate resume and HR audio files
- delete contests and related data

### Constants API

- companies
- topics
- difficulties
- languages
- roles
- skills
- tags

These endpoints support frontend selectors and form options.

## Tech Stack

- Python
- FastAPI
- MongoDB
- GridFS
- OpenAI API
- Google Auth
- PyMuPDF
- pdf2image
- pytesseract
- faster-whisper
- whisper
- python-jose
- Uvicorn

## Environment Variables

Create a `.env` file in the backend root with:

```env
connection_string=your_mongodb_connection_string
GOOGLE_CLIENT_ID=your_google_client_id
JWT_SECRET=your_jwt_secret
JWT_ALGO=HS256
Frontend=http://localhost:5173
OPENAI_API_KEY=your_openai_api_key
GITHUB_API_KEY=your_github_api_key
```

## Setup

### 1. Create virtual environment

```powershell
cd C:\Users\Arnesh\Desktop\AIinterview
python -m venv AIinter
```

### 2. Activate virtual environment

```powershell
.\AIinter\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

## Run the Server

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

Custom docs page:

```text
http://127.0.0.1:8000/docs
```

## Important Notes

- MongoDB is used as the primary data store
- GridFS is used for resume and audio file storage
- OpenAI-backed evaluation and question generation are part of core workflows
- local frontend CORS ports are already configured in `main.py`

## GitHub Description

FastAPI + MongoDB backend for an AI interview platform with resume, GitHub, coding, concept, contest, and admin evaluation workflows.
