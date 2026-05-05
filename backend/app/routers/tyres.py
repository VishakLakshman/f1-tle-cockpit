from fastapi import APIRouter, HTTPException, Query
from app.services import s3_service, redis_service
from app.models.schemas import TyreDegradationResponse

router = APIRouter()


@router.get("/degradation", response_model=TyreDegradationResponse)
async def tyre_degradation(
    year: int = Query(..., ge=2025, le=2026),
    gp: str = Query(..., description="Grand Prix name, e.g. 'Monaco'"),
):
    cache_key = f"tyres:{year}:{gp.replace(' ', '_')}"
    cached = redis_service.get_cached(cache_key)
    if cached:
        cached["cached"] = True
        return TyreDegradationResponse(**cached)

    try:
        data = s3_service.get_tyre_degradation(year, gp)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    redis_service.set_cached(cache_key, data)
    return TyreDegradationResponse(**data)