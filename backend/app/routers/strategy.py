from fastapi import APIRouter, HTTPException, Query
from app.services import s3_service, redis_service
from app.models.schemas import RaceStrategyResponse

router = APIRouter()


@router.get("/race", response_model=RaceStrategyResponse)
async def race_strategy(
    year: int = Query(..., ge=2025, le=2025),
    gp: str = Query(..., description="Grand Prix name, e.g. 'Monaco'"),
):
    cache_key = f"strategy:{year}:{gp.replace(' ', '_')}"
    cached = redis_service.get_cached(cache_key)
    if cached:
        cached["cached"] = True
        return RaceStrategyResponse(**cached)

    try:
        data = s3_service.get_race_strategy(year, gp)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    redis_service.set_cached(cache_key, data)
    return RaceStrategyResponse(**data)