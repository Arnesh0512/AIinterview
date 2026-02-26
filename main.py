from fastapi import FastAPI
from routes import auth, user, resume, github, coding, cs, ranking
from fastapi.middleware.cors import CORSMiddleware
from utils.reader import Frontend
import os
import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(resume.router)
app.include_router(github.router)
app.include_router(coding.router)
app.include_router(cs.router)
app.include_router(ranking.router)