from fastapi import APIRouter, HTTPException, Query
from app.services import s3_service, redis_service
from app.models.schemas import QualifyingGhostResponse, SessionInfoResponse

router = APIRouter()


@router.get("/session-info", response_model=SessionInfoResponse)
async def session_info(
    year: int = Query(..., ge=2025, le=2025, description="Season year (2025 pre-processed)"),
    gp: str = Query(..., description="Grand Prix name, e.g. 'Monaco'"),
    session: str = Query("Q3", description="Session identifier: Q1, Q2, or Q3"),
):
    cache_key = redis_service.session_key(year, gp, session)
    cached = redis_service.get_cached(cache_key)
    if cached:
        return SessionInfoResponse(**cached)

    try:
        data = s3_service.get_session_info(year, gp, session)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    redis_service.set_cached(cache_key, data)
    return SessionInfoResponse(**data)


@router.get("/ghost", response_model=QualifyingGhostResponse)
async def ghost_lap(
    year: int = Query(..., ge=2025, le=2025),
    gp: str = Query(..., description="Grand Prix name, e.g. 'Monaco'"),
    session: str = Query("Q3", description="Q1, Q2, or Q3"),
    driver1: str = Query(..., description="Driver code, e.g. 'VER'"),
    driver2: str = Query(..., description="Driver code, e.g. 'LEC'"),
):
    cache_key = redis_service.cache_key(year, gp, session, driver1, driver2)
    cached = redis_service.get_cached(cache_key)
    if cached:
        cached["cached"] = True
        return QualifyingGhostResponse(**cached)

    try:
        data = s3_service.get_ghost_lap_data(year, gp, session, driver1, driver2)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    redis_service.set_cached(cache_key, data)
    return QualifyingGhostResponse(**data)