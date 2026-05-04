import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from dotenv import load_dotenv
from app.routers import qualifying, tyres, strategy

load_dotenv()

app = FastAPI(
    title="F1 Telemetry API",
    description="Backend for F1 Telemetry Dashboard — Qualifying Ghost Module",
    version="1.0.0",
    # API Gateway injects a stage prefix (e.g. /prod) — tell FastAPI about it
    root_path=os.getenv("API_ROOT_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(qualifying.router, prefix="/api/qualifying", tags=["Qualifying"])
app.include_router(tyres.router, prefix="/api/tyres", tags=["Tyres"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["Strategy"])


@app.get("/health")
async def health():
    return {"status": "ok"}


# Mangum adapts the ASGI app for AWS Lambda + API Gateway (HTTP API or REST API)
# lifespan="off" avoids startup/shutdown event issues in Lambda's stateless model
handler = Mangum(app, lifespan="off")
