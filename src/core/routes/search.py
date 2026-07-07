from fastapi import APIRouter, Query

router = APIRouter(tags=["search"])


@router.get("/search")
async def search_memory(
    query: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=25),
) -> dict[str, object]:
    return {
        "query": query,
        "limit": limit,
        "results": [],
    }