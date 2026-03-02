from fastapi import FastAPI
from routes import auth, candidate, concept, resume, github, coding, ranking, dev
from fastapi.middleware.cors import CORSMiddleware
from utils.reader import Frontend
import os
import certifi



os.environ["SSL_CERT_FILE"] = certifi.where()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Frontend],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


app.include_router(dev.router)
app.include_router(auth.router)
app.include_router(candidate.router)
app.include_router(resume.router)
app.include_router(github.router)
app.include_router(coding.router)
app.include_router(concept.router)
app.include_router(ranking.router)
