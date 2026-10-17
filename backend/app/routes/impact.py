from fastapi import APIRouter, HTTPException, status
from backend.app.models import ImpactRequest, ImpactResponse
from backend.app.services.impact_service import impact_service

router = APIRouter(tags=["Change Impact Analysis"])


@router.post("/impact", response_model=ImpactResponse)
def analyze_change_impact(request: ImpactRequest) -> ImpactResponse:
    """
    Perform dependency-aware downstream change impact analysis using graph traversal.
    Computes direct modifications, 1-hop and 2-hop consumers, historical regressions, and test suite.
    """
    try:
        if not request.changed_components:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one changed component must be specified for impact analysis.",
            )
        response = impact_service.evaluate_impact(request)
        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Change impact analysis failed: {str(exc)}",
        )
