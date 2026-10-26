from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check for hosting and monitoring.

    Public on purpose: it returns no data and touches nothing. This is the only
    endpoint exempt from the default-deny permission rule.
    """
    return {"status": "ok"}
