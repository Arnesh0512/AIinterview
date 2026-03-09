from fastapi import FastAPI
from routes import auth,admin, candidate, concept, resume, github, coding, ranking, dev, constants, contest
from fastapi.middleware.cors import CORSMiddleware
from utils.reader import Frontend
import os
import certifi
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path



os.environ["SSL_CERT_FILE"] = certifi.where()


app = FastAPI(docs_url=None)



@app.get("/docs", include_in_schema=False)
async def custom_swagger():
    html_path = Path("templates/swagger.html")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))







app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
app.include_router(constants.router)
app.include_router(admin.router)
app.include_router(contest.router)