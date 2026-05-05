import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from dotenv import load_dotenv
from app.routers import qualifying, tyres, strategy
from app.services.rate_limiter import is_rate_limited, RATE_LIMIT, WINDOW_S

load_dotenv()

app = FastAPI(
    title="F1 Telemetry API",
    description="Backend for F1 Telemetry Dashboard",
    version="1.0.0",
    root_path=os.getenv("API_ROOT_PATH", ""),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for health checks
    if request.url.path == "/health":
        return await call_next(request)

    # Resolve client IP — API Gateway forwards the real IP in
    # X-Forwarded-For; fall back to direct connection address
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    client_ip = forwarded_for.split(",")[0].strip() or request.client.host

    limited, used, retry_after = is_rate_limited(client_ip)

    if limited:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Rate limit exceeded. Max {RATE_LIMIT} requests per {WINDOW_S}s.",
                "retry_after_seconds": retry_after,
            },
            headers={
                "Retry-After":              str(retry_after),
                "X-RateLimit-Limit":        str(RATE_LIMIT),
                "X-RateLimit-Window":       str(WINDOW_S),
                "X-RateLimit-Remaining":    "0",
            },
        )

    response = await call_next(request)

    # Attach rate limit headers to every response so the frontend can read them
    response.headers["X-RateLimit-Limit"]     = str(RATE_LIMIT)
    response.headers["X-RateLimit-Window"]    = str(WINDOW_S)
    response.headers["X-RateLimit-Remaining"] = str(max(0, RATE_LIMIT - used))
    return response


app.include_router(qualifying.router, prefix="/api/qualifying", tags=["Qualifying"])
app.include_router(tyres.router,      prefix="/api/tyres",      tags=["Tyres"])
app.include_router(strategy.router,   prefix="/api/strategy",   tags=["Strategy"])


@app.get("/health")
async def health():
    return {"status": "ok"}


handler = Mangum(app, lifespan="off")