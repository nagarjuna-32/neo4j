import logging
from typing import List, Optional
from backend.app.models import ImpactRequest, ImpactResponse, AffectedComponent
from backend.app.services.graph_service import graph_service

logger = logging.getLogger("devgraph.impact_service")


class ImpactService:
    def evaluate_impact(self, request: ImpactRequest) -> ImpactResponse:
        """
        Evaluate downstream change impact using Neo4j graph traversal and transparent risk heuristics.
        """
        raw = graph_service.get_downstream_impact(
            project_id=request.project_id,
            changed_components=request.changed_components or [],
            changed_files=request.changed_files or [],
        )

        affected = [
            AffectedComponent(
                id=item["id"],
                name=item["name"],
                tier=item["tier"],
                reason=item["reason"],
                path=item["path"],
                status_label=item.get("status_label", "potential_impact"),
            )
            for item in raw["affected_components"]
        ]

        return ImpactResponse(
            project_id=raw["project_id"],
            directly_changed=raw["directly_changed"],
            unresolved_inputs=raw.get("unresolved_inputs", []),
            affected_components=affected,
            historical_risks=raw["historical_risks"],
            technical_decisions=raw.get("technical_decisions", []),
            suggested_tests=raw["suggested_tests"],
            graph_paths=raw["graph_paths"],
            heuristic_priority=raw["heuristic_priority"],
            priority_reasons=raw["priority_reasons"],
            explanations=raw["explanations"],
        )


impact_service = ImpactService()
