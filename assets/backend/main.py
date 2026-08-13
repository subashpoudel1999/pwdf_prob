from dotenv import load_dotenv
load_dotenv()  # loads backend/.env on local dev; no-op on Render

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(title="Wildcat x MHRI Fusion API", version="1.0.0")

# CORS for Flutter web/mobile
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://subashpoudel1999.github.io",  # GitHub Pages frontend
        "http://localhost:8080",  # local `flutter run -d chrome` dev
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "wildcat-api"}
