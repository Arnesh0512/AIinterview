from fastapi import FastAPI
from routes import auth, user
from fastapi.middleware.cors import CORSMiddleware
from utils.reader import Frontend

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[Frontend],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router)
app.include_router(user.router)