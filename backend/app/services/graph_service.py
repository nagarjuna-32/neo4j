import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

from backend.app.database import db_manager
from backend.app.models import (
    GraphNode,
    GraphEdge,
    GraphResponse,
    EvidenceRecord,
    AffectedComponent,
    ActivityEvent,
)

logger = logging.getLogger("devgraph.graph_service")


class InMemoryGraphStore:
    """High-fidelity in-memory graph repository matching Neo4j schema & traversal semantics."""

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self.activity_log: List[ActivityEvent] = []
        self.seed_defaults()

    def clear(self):
        self.nodes.clear()
        self.edges.clear()
        self.activity_log.clear()

    def add_node(self, node_id: str, label: str, labels: List[str], properties: Dict[str, Any]):
        props = properties.copy()
        props["id"] = node_id
        self.nodes[node_id] = {
            "id": node_id,
            "label": label,
            "labels": list(set([label] + labels)),
            "properties": props,
        }

    def add_edge(self, edge_id: str, source: str, target: str, rel_type: str, properties: Optional[Dict[str, Any]] = None):
        props = (properties or {}).copy()
        # Avoid duplicate edges
        for existing in self.edges:
            if existing["source"] == source and existing["target"] == target and existing["type"] == rel_type:
                existing["properties"].update(props)
                return
        self.edges.append({
            "id": edge_id,
            "source": source,
            "target": target,
            "type": rel_type,
            "properties": props,
        })

    def log_activity(self, event_type: str, title: str, entity_id: str, component: str, summary: str):
        event = ActivityEvent(
            id=f"ACT-{len(self.activity_log) + 1001}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            title=title,
            entity_id=entity_id,
            component=component,
            summary=summary,
        )
        self.activity_log.insert(0, event)

    def seed_defaults(self):
        self.clear()
        # 1. Project
        self.add_node("PRJ-SENTINEL", "Project", ["Project"], {
            "name": "Sentinel Demo App",
            "description": "Cloud-native distributed enterprise service mesh with identity and telemetry",
            "is_synthetic": True,
            "source": "Sentinel Synthetic Demo",
            "created_at": "2026-08-01T00:00:00Z",
        })

        # 2. Components
        components = [
            ("COMP-AUTH", "Authentication", "Core identity service, JWT signing, refresh token rotation, and auth middleware"),
            ("COMP-USERS", "Users API", "RESTful user profile management, tenant authorization, and client data endpoints"),
            ("COMP-ADMIN", "Admin Dashboard", "Internal operational management, user permission administration, and metrics"),
            ("COMP-NOTIF", "Notification Service", "Event-driven customer notification dispatch via WebHooks, SMTP, and push"),
        ]
        for cid, cname, cdesc in components:
            self.add_node(cid, "Component", ["Component"], {
                "name": cname,
                "description": cdesc,
                "project_id": "PRJ-SENTINEL",
                "is_synthetic": True,
            })
            self.add_edge(f"HAS_COMP_{cid}", "PRJ-SENTINEL", cid, "HAS_COMPONENT")

        # 3. Dependencies
        dependencies = [
            ("DEP-JWT", "PyJWT / python-jose", "2.9.0", "security-library"),
            ("DEP-FASTAPI", "FastAPI Framework", "0.115.0", "web-framework"),
            ("DEP-POSTGRES", "PostgreSQL Engine", "16.0", "relational-database"),
        ]
        for did, dname, dver, dtype in dependencies:
            self.add_node(did, "Dependency", ["Dependency"], {
                "name": dname,
                "version": dver,
                "type": dtype,
                "is_synthetic": True,
            })

        # Connect dependencies
        self.add_edge("REL-AUTH-JWT", "COMP-AUTH", "DEP-JWT", "DEPENDS_ON")
        self.add_edge("REL-AUTH-FASTAPI", "COMP-AUTH", "DEP-FASTAPI", "DEPENDS_ON")
        self.add_edge("REL-USERS-POSTGRES", "COMP-USERS", "DEP-POSTGRES", "DEPENDS_ON")
        self.add_edge("REL-USERS-AUTH", "COMP-USERS", "COMP-AUTH", "DEPENDS_ON")
        self.add_edge("REL-ADMIN-USERS", "COMP-ADMIN", "COMP-USERS", "DEPENDS_ON")
        self.add_edge("REL-NOTIF-USERS", "COMP-NOTIF", "COMP-USERS", "DEPENDS_ON")

        # 4. Files & Functions (Code-level call graph)
        self.add_node("FILE-AUTH-MW", "File", ["File"], {
            "path": "backend/app/middleware/auth.py",
            "language": "python",
            "project_id": "PRJ-SENTINEL",
            "is_synthetic": True,
        })
        self.add_edge("REL-PRJ-FILE-AUTH", "PRJ-SENTINEL", "FILE-AUTH-MW", "CONTAINS")
        self.add_edge("REL-COMP-FILE-AUTH", "COMP-AUTH", "FILE-AUTH-MW", "CONTAINS")

        self.add_node("FN-VERIFY-REFRESH", "Function", ["Function"], {
            "name": "verify_refresh_token",
            "signature": "verify_refresh_token(token: str) -> TokenPayload",
            "project_id": "PRJ-SENTINEL",
            "is_synthetic": True,
        })
        self.add_node("FN-JWT-DECODE", "Function", ["Function"], {
            "name": "jwt.decode",
            "signature": "jwt.decode(token: str, key: str, algorithms: list[str])",
            "project_id": "PRJ-SENTINEL",
            "is_synthetic": True,
        })
        self.add_edge("REL-FILE-FN-REFRESH", "FILE-AUTH-MW", "FN-VERIFY-REFRESH", "CONTAINS")
        self.add_edge("REL-FN-CALL-JWT", "FN-VERIFY-REFRESH", "FN-JWT-DECODE", "CALLS")

        # 5. Technical Decision DEC-101
        self.add_node("DEC-101", "Decision", ["Decision"], {
            "title": "Migrate session authentication to JWT",
            "description": "Replaced stateful server-side Redis sessions with stateless signed JWT bearer tokens for horizontal scalability and cross-service verification.",
            "reason": "Support authenticated mobile clients and stateless API access.",
            "author": "Lead Security Architect",
            "date": "2026-08-15",
            "status": "ACCEPTED",
            "source": "ADR-042: Stateless Auth Migration",
            "project_id": "PRJ-SENTINEL",
            "is_synthetic": True,
        })
        self.add_node("RSN-101", "Reason", ["Reason"], {
            "text": "Support authenticated mobile clients and stateless API access.",
            "is_synthetic": True,
        })
        self.add_edge("REL-DEC101-RSN", "DEC-101", "RSN-101", "JUSTIFIED_BY")
        self.add_edge("REL-AUTH-DEC101", "COMP-AUTH", "DEC-101", "AFFECTED_BY")

        # 6. Historical Bug BUG-101
        self.add_node("BUG-101", "Bug", ["Bug"], {
            "title": "Users API returns HTTP 401 after authentication refactor",
            "symptom": "Authenticated users receive unexpected 401 Unauthorized responses during legitimate session renewal.",
            "root_cause": "Refresh-token validation middleware was missing from the authentication route chain after the JWT refactor.",
            "resolution": "FIX-101 restores middleware registration and adds regression coverage.",
            "status": "RESOLVED",
            "affected_component": "Authentication",
            "project_id": "PRJ-SENTINEL",
            "created_at": "2026-08-20T14:32:00Z",
            "source": "Incident INC-4019",
            "is_synthetic": True,
        })
        self.add_edge("REL-AUTH-BUG101", "COMP-AUTH", "BUG-101", "HAS_BUG")
        self.add_edge("REL-BUG101-DEC101", "BUG-101", "DEC-101", "RELATED_TO")

        # 6. Fix FIX-101
        self.add_node("FIX-101", "Fix", ["Fix"], {
            "title": "Restore refresh-token middleware registration",
            "description": "Explicitly registered TokenValidationMiddleware before RouteDispatch in FastAPI lifespan and added token renewal handler.",
            "changed_component": "Authentication",
            "associated_incident": "BUG-101",
            "status": "VERIFIED",
            "is_synthetic": True,
        })
        self.add_edge("REL-BUG101-FIX101", "BUG-101", "FIX-101", "RESOLVED_BY")

        # 7. Test TEST-101
        self.add_node("TEST-101", "Test", ["Test"], {
            "title": "test_refresh_token_validation_and_auth_flow",
            "description": "Verifies refresh-token validation, expiry handling, and expected authentication behavior across Users API downstream paths.",
            "verification_status": "Regression test passed in the synthetic demo",
            "test_type": "REGRESSION",
            "is_synthetic": True,
        })
        self.add_edge("REL-FIX101-TEST101", "FIX-101", "TEST-101", "VERIFIED_BY")

        # 8. Pull Requests & Developers
        self.add_node("PR-101", "PullRequest", ["PullRequest"], {
            "title": "feat(auth): stateless JWT authentication architecture",
            "status": "MERGED",
            "merged_at": "2026-08-16T10:00:00Z",
            "is_synthetic": True,
        })
        self.add_node("PR-108", "PullRequest", ["PullRequest"], {
            "title": "fix(auth): restore refresh token validation middleware",
            "status": "MERGED",
            "merged_at": "2026-08-21T09:15:00Z",
            "is_synthetic": True,
        })
        self.add_node("DEV-ALICE", "Developer", ["Developer"], {
            "name": "Alice Chen (Principal Security Eng)",
            "email": "alice@sentinel.dev",
            "is_synthetic": True,
        })
        self.add_node("DEV-BOB", "Developer", ["Developer"], {
            "name": "Bob Ramirez (Senior Backend Eng)",
            "email": "bob@sentinel.dev",
            "is_synthetic": True,
        })
        self.add_edge("REL-DEC101-PR101", "DEC-101", "PR-101", "DECIDED_IN")
        self.add_edge("REL-BUG101-PR108", "BUG-101", "PR-108", "CHANGED_IN")
        self.add_edge("REL-BOB-PR101", "DEV-BOB", "PR-101", "AUTHORED")
        self.add_edge("REL-ALICE-PR108", "DEV-ALICE", "PR-108", "AUTHORED")

        # Seed activity history
        self.log_activity("SEED", "Seeded Demo Graph Baseline", "PRJ-SENTINEL", "All Components", "Initialized 4 components, 3 dependencies, DEC-101, BUG-101, FIX-101, and TEST-101")
        self.log_activity("FIX_VERIFIED", "Regression Test Passed", "TEST-101", "Authentication", "TEST-101 verified refresh-token validation under synthetic load")
        self.log_activity("INCIDENT_RESOLVED", "Bug BUG-101 Resolved", "BUG-101", "Authentication", "Incident INC-4019 resolved by FIX-101 with token middleware")
        self.log_activity("DECISION_LOGGED", "Architecture Decision DEC-101 Logged", "DEC-101", "Authentication", "Migrate session authentication to JWT for mobile and stateless API access")


# Singleton fallback store
in_memory_store = InMemoryGraphStore()


class GraphService:
    def __init__(self):
        self.queries_dir = Path(__file__).resolve().parent.parent / "queries"

    def apply_schema(self) -> Dict[str, Any]:
        """Apply uniqueness constraints and indexes to Neo4j if connected."""
        if not db_manager.is_connected:
            return {"status": "skipped", "reason": "Neo4j is not connected; constraints simulated in local memory"}

        schema_file = self.queries_dir / "schema.cypher"
        if not schema_file.exists():
            return {"status": "error", "message": "schema.cypher not found"}

        with open(schema_file, "r", encoding="utf-8") as f:
            content = f.read()

        statements = [stmt.strip() for stmt in content.split(";") if stmt.strip() and not stmt.strip().startswith("//")]
        executed = 0
        for stmt in statements:
            try:
                db_manager.run_query(stmt)
                executed += 1
            except Exception as e:
                logger.warning(f"Error applying schema statement: {e}")

        return {"status": "success", "statements_executed": executed}

    def seed_data(self) -> Dict[str, Any]:
        """Seed demo data using idempotent MERGE Cypher or reset in-memory store."""
        # Always seed in-memory store as baseline
        in_memory_store.seed_defaults()

        if db_manager.is_connected:
            try:
                self.apply_schema()
                seed_file = self.queries_dir / "seed.cypher"
                if seed_file.exists():
                    with open(seed_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    statements = [stmt.strip() for stmt in content.split(";") if stmt.strip() and not stmt.strip().startswith("//")]
                    for stmt in statements:
                        db_manager.run_query(stmt)
                    logger.info("Successfully seeded data into live Neo4j database.")
                    return {
                        "status": "success",
                        "database": "Neo4j AuraDB / Live Instance",
                        "project_id": "PRJ-SENTINEL",
                        "message": "Demo project 'Sentinel Demo App' seeded idempotently via MERGE Cypher.",
                        "node_count": self.get_node_count("PRJ-SENTINEL"),
                        "edge_count": self.get_edge_count("PRJ-SENTINEL"),
                    }
            except Exception as e:
                logger.error(f"Failed to seed live Neo4j: {e}")
                return {
                    "status": "warning",
                    "database": "In-Memory Graph Engine (Neo4j seed error)",
                    "project_id": "PRJ-SENTINEL",
                    "error": str(e),
                    "message": "Seeded synthetic demo data into in-memory store as fallback.",
                    "node_count": len(in_memory_store.nodes),
                    "edge_count": len(in_memory_store.edges),
                }

        return {
            "status": "success",
            "database": "In-Memory Graph Engine (Neo4j Offline)",
            "project_id": "PRJ-SENTINEL",
            "message": "Demo project 'Sentinel Demo App' seeded successfully into in-memory graph repository.",
            "node_count": len(in_memory_store.nodes),
            "edge_count": len(in_memory_store.edges),
        }

    def get_node_count(self, project_id: str) -> int:
        if db_manager.is_connected:
            try:
                records = db_manager.run_query(
                    """
                    MATCH (n)
                    WHERE n.project_id = $project_id OR n.id = $project_id OR (n:Dependency) OR (n:Test) OR (n:Fix)
                    RETURN count(n) AS cnt
                    """,
                    {"project_id": project_id},
                )
                if records:
                    return records[0].get("cnt", 0)
            except Exception:
                pass
        return len(in_memory_store.nodes)

    def get_edge_count(self, project_id: str) -> int:
        if db_manager.is_connected:
            try:
                records = db_manager.run_query(
                    """
                    MATCH (n)-[r]->(m)
                    RETURN count(r) AS cnt
                    """
                )
                if records:
                    return records[0].get("cnt", 0)
            except Exception:
                pass
        return len(in_memory_store.edges)

    def get_projects(self) -> List[Dict[str, Any]]:
        if db_manager.is_connected:
            try:
                records = db_manager.run_query(
                    """
                    MATCH (p:Project)
                    OPTIONAL MATCH (p)-[:HAS_COMPONENT]->(c:Component)
                    RETURN p.id AS id, p.name AS name, p.description AS description, 
                           coalesce(p.is_synthetic, true) AS is_synthetic, count(c) AS component_count
                    """
                )
                if records:
                    return records
            except Exception as e:
                logger.warning(f"Error querying projects from Neo4j: {e}")

        # Fallback
        p = in_memory_store.nodes.get("PRJ-SENTINEL")
        if p:
            return [{
                "id": p["id"],
                "name": p["properties"].get("name", "Sentinel Demo App"),
                "description": p["properties"].get("description", ""),
                "is_synthetic": True,
                "component_count": 4,
            }]
        return []

    def get_graph(self, project_id: str = "PRJ-SENTINEL") -> GraphResponse:
        """Return nodes and relationships formatted for Cytoscape.js visualization."""
        if db_manager.is_connected:
            try:
                query = """
                MATCH (n)
                WHERE n.project_id = $project_id 
                   OR n.id = $project_id 
                   OR (n:Dependency) 
                   OR (n:Test) 
                   OR (n:Fix) 
                   OR (n:Reason)
                   OR (n:File)
                   OR (n:Function)
                   OR (n:PullRequest)
                   OR (n:Developer)
                OPTIONAL MATCH (n)-[r]->(m)
                RETURN n, labels(n) AS n_labels, r, type(r) AS r_type, m, labels(m) AS m_labels
                """
                records = db_manager.run_query(query, {"project_id": project_id})
                nodes_map: Dict[str, GraphNode] = {}
                edges_list: List[GraphEdge] = []
                seen_edges: Set[str] = set()

                for rec in records:
                    n = rec.get("n")
                    if n:
                        nid = n.get("id") or str(n.id)
                        labels = rec.get("n_labels", ["Node"])
                        primary_label = labels[0] if labels else "Node"
                        if nid not in nodes_map:
                            nodes_map[nid] = GraphNode(
                                id=nid,
                                label=primary_label,
                                labels=labels,
                                properties=dict(n),
                            )

                    m = rec.get("m")
                    r = rec.get("r")
                    if m and r:
                        mid = m.get("id") or str(m.id)
                        m_labels = rec.get("m_labels", ["Node"])
                        m_primary = m_labels[0] if m_labels else "Node"
                        if mid not in nodes_map:
                            nodes_map[mid] = GraphNode(
                                id=mid,
                                label=m_primary,
                                labels=m_labels,
                                properties=dict(m),
                            )
                        
                        r_type = rec.get("r_type", "RELATED_TO")
                        edge_id = f"{nid}_{r_type}_{mid}"
                        if edge_id not in seen_edges:
                            seen_edges.add(edge_id)
                            edges_list.append(GraphEdge(
                                id=edge_id,
                                source=nid,
                                target=mid,
                                type=r_type,
                                properties=dict(r) if hasattr(r, "__iter__") else {},
                            ))

                stats = {
                    "total_nodes": len(nodes_map),
                    "total_edges": len(edges_list),
                    "decisions": sum(1 for n in nodes_map.values() if n.label == "Decision"),
                    "bugs": sum(1 for n in nodes_map.values() if n.label == "Bug"),
                    "components": sum(1 for n in nodes_map.values() if n.label == "Component"),
                }
                return GraphResponse(
                    project_id=project_id,
                    nodes=list(nodes_map.values()),
                    edges=edges_list,
                    stats=stats,
                )
            except Exception as e:
                logger.warning(f"Error fetching live graph from Neo4j: {e}. Falling back to in-memory.")

        # In-memory graph response
        nodes = [
            GraphNode(
                id=n["id"],
                label=n["label"],
                labels=n["labels"],
                properties=n["properties"],
            )
            for n in in_memory_store.nodes.values()
        ]
        edges = [
            GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=e["type"],
                properties=e["properties"],
            )
            for e in in_memory_store.edges
        ]
        stats = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "decisions": sum(1 for n in nodes if n.label == "Decision"),
            "bugs": sum(1 for n in nodes if n.label == "Bug"),
            "components": sum(1 for n in nodes if n.label == "Component"),
        }
        return GraphResponse(
            project_id=project_id,
            nodes=nodes,
            edges=edges,
            stats=stats,
        )

    def add_memory_decision(
        self,
        project_id: str,
        title: str,
        affected_component: str,
        description: str,
        reason: Optional[str] = None,
        dependency: Optional[str] = None,
        author: Optional[str] = "Engineering Team",
        source: Optional[str] = "Manual Input",
    ) -> Tuple[str, List[str]]:
        """Store technical decision in Neo4j and/or in-memory store."""
        # Generate stable ID
        existing_decisions = [
            nid for nid, n in in_memory_store.nodes.items() if n["label"] == "Decision"
        ]
        dec_num = 100 + len(existing_decisions) + 1
        decision_id = f"DEC-{dec_num}"
        reason_id = f"RSN-{dec_num}"

        # Resolve or find affected component ID
        comp_id = self._resolve_component_id(affected_component)

        # 1. Update in-memory store
        dec_props = {
            "title": title,
            "description": description or reason or "",
            "reason": reason or "",
            "author": author or "Engineering Team",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "status": "ACCEPTED",
            "source": source or "Manual Memory Input",
            "project_id": project_id,
            "is_synthetic": True,
        }
        in_memory_store.add_node(decision_id, "Decision", ["Decision"], dec_props)
        connected_paths = [f"({comp_id})-[:AFFECTED_BY]->({decision_id})"]

        if comp_id in in_memory_store.nodes:
            in_memory_store.add_edge(f"REL_{comp_id}_{decision_id}", comp_id, decision_id, "AFFECTED_BY")

        if reason:
            in_memory_store.add_node(reason_id, "Reason", ["Reason"], {"text": reason, "is_synthetic": True})
            in_memory_store.add_edge(f"REL_{decision_id}_{reason_id}", decision_id, reason_id, "JUSTIFIED_BY")
            connected_paths.append(f"({decision_id})-[:JUSTIFIED_BY]->({reason_id})")

        if dependency:
            dep_id = f"DEP-{dependency.upper().replace(' ', '_')}"
            if dep_id not in in_memory_store.nodes:
                in_memory_store.add_node(dep_id, "Dependency", ["Dependency"], {
                    "name": dependency,
                    "type": "library",
                    "is_synthetic": True,
                })
            in_memory_store.add_edge(f"REL_{comp_id}_{dep_id}", comp_id, dep_id, "DEPENDS_ON")
            connected_paths.append(f"({comp_id})-[:DEPENDS_ON]->({dep_id})")

        in_memory_store.log_activity(
            "DECISION_ADDED",
            f"Decision {decision_id}: {title}",
            decision_id,
            affected_component,
            reason or description or "Technical architectural decision captured.",
        )

        # 2. Update Neo4j if connected
        if db_manager.is_connected:
            try:
                cypher = """
                MERGE (c:Component {name: $comp_name})
                ON CREATE SET c.id = $comp_id, c.project_id = $project_id, c.is_synthetic = true
                MERGE (d:Decision {id: $decision_id})
                SET d.title = $title,
                    d.description = $description,
                    d.reason = $reason,
                    d.author = $author,
                    d.date = $date,
                    d.status = 'ACCEPTED',
                    d.source = $source,
                    d.project_id = $project_id,
                    d.is_synthetic = true
                MERGE (c)-[:AFFECTED_BY]->(d)
                """
                params = {
                    "comp_name": affected_component,
                    "comp_id": comp_id,
                    "decision_id": decision_id,
                    "title": title,
                    "description": description or reason or "",
                    "reason": reason or "",
                    "author": author or "Engineering Team",
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "source": source or "Manual Memory Input",
                    "project_id": project_id,
                }
                db_manager.run_query(cypher, params)

                if reason:
                    db_manager.run_query(
                        """
                        MERGE (d:Decision {id: $decision_id})
                        MERGE (r:Reason {id: $reason_id})
                        SET r.text = $reason, r.is_synthetic = true
                        MERGE (d)-[:JUSTIFIED_BY]->(r)
                        """,
                        {"decision_id": decision_id, "reason_id": reason_id, "reason": reason},
                    )
            except Exception as e:
                logger.error(f"Error persisting decision to Neo4j: {e}")

        return decision_id, connected_paths

    def add_memory_bug(
        self,
        project_id: str,
        title: str,
        affected_component: str,
        symptom: str,
        root_cause: Optional[str] = None,
        resolution: Optional[str] = None,
        status: Optional[str] = "RESOLVED",
        verification: Optional[str] = None,
        source: Optional[str] = "Manual Input",
    ) -> Tuple[str, List[str]]:
        """Store historical or active bug in Neo4j and/or in-memory store."""
        existing_bugs = [
            nid for nid, n in in_memory_store.nodes.items() if n["label"] == "Bug"
        ]
        bug_num = 100 + len(existing_bugs) + 1
        bug_id = f"BUG-{bug_num}"
        fix_id = f"FIX-{bug_num}"
        test_id = f"TEST-{bug_num}"

        comp_id = self._resolve_component_id(affected_component)

        # 1. Update in-memory store
        bug_props = {
            "title": title,
            "symptom": symptom,
            "root_cause": root_cause or "",
            "resolution": resolution or "",
            "status": status or "RESOLVED",
            "affected_component": affected_component,
            "source": source or "Manual Memory Input",
            "project_id": project_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_synthetic": True,
        }
        in_memory_store.add_node(bug_id, "Bug", ["Bug"], bug_props)
        connected_paths = [f"({comp_id})-[:HAS_BUG]->({bug_id})"]

        if comp_id in in_memory_store.nodes:
            in_memory_store.add_edge(f"REL_{comp_id}_{bug_id}", comp_id, bug_id, "HAS_BUG")

        if resolution or root_cause:
            fix_props = {
                "title": f"Fix for {bug_id}: {title}",
                "description": resolution or root_cause or "Automated fix remediation",
                "changed_component": affected_component,
                "associated_incident": bug_id,
                "status": "VERIFIED" if verification else "PROPOSED",
                "is_synthetic": True,
            }
            in_memory_store.add_node(fix_id, "Fix", ["Fix"], fix_props)
            in_memory_store.add_edge(f"REL_{bug_id}_{fix_id}", bug_id, fix_id, "RESOLVED_BY")
            connected_paths.append(f"({bug_id})-[:RESOLVED_BY]->({fix_id})")

            if verification:
                test_props = {
                    "title": f"test_regression_{bug_id.lower()}",
                    "description": verification,
                    "verification_status": verification,
                    "test_type": "REGRESSION",
                    "is_synthetic": True,
                }
                in_memory_store.add_node(test_id, "Test", ["Test"], test_props)
                in_memory_store.add_edge(f"REL_{fix_id}_{test_id}", fix_id, test_id, "VERIFIED_BY")
                connected_paths.append(f"({fix_id})-[:VERIFIED_BY]->({test_id})")

        in_memory_store.log_activity(
            "BUG_LOGGED",
            f"Bug {bug_id}: {title}",
            bug_id,
            affected_component,
            symptom or "Bug recorded with root cause and remediation details.",
        )

        # 2. Update Neo4j if connected
        if db_manager.is_connected:
            try:
                cypher = """
                MERGE (c:Component {name: $comp_name})
                ON CREATE SET c.id = $comp_id, c.project_id = $project_id, c.is_synthetic = true
                MERGE (b:Bug {id: $bug_id})
                SET b.title = $title,
                    b.symptom = $symptom,
                    b.root_cause = $root_cause,
                    b.resolution = $resolution,
                    b.status = $status,
                    b.affected_component = $comp_name,
                    b.project_id = $project_id,
                    b.created_at = datetime(),
                    b.source = $source,
                    b.is_synthetic = true
                MERGE (c)-[:HAS_BUG]->(b)
                """
                params = {
                    "comp_name": affected_component,
                    "comp_id": comp_id,
                    "bug_id": bug_id,
                    "title": title,
                    "symptom": symptom,
                    "root_cause": root_cause or "",
                    "resolution": resolution or "",
                    "status": status or "RESOLVED",
                    "source": source or "Manual Memory Input",
                    "project_id": project_id,
                }
                db_manager.run_query(cypher, params)

                if resolution or root_cause:
                    db_manager.run_query(
                        """
                        MERGE (b:Bug {id: $bug_id})
                        MERGE (f:Fix {id: $fix_id})
                        SET f.title = $fix_title,
                            f.description = $fix_desc,
                            f.changed_component = $comp_name,
                            f.associated_incident = $bug_id,
                            f.status = $fix_status,
                            f.is_synthetic = true
                        MERGE (b)-[:RESOLVED_BY]->(f)
                        """,
                        {
                            "bug_id": bug_id,
                            "fix_id": fix_id,
                            "fix_title": f"Fix for {bug_id}: {title}",
                            "fix_desc": resolution or root_cause or "",
                            "comp_name": affected_component,
                            "fix_status": "VERIFIED" if verification else "PROPOSED",
                        },
                    )
                    if verification:
                        db_manager.run_query(
                            """
                            MERGE (f:Fix {id: $fix_id})
                            MERGE (t:Test {id: $test_id})
                            SET t.title = $test_title,
                                t.description = $test_desc,
                                t.verification_status = $verification,
                                t.test_type = 'REGRESSION',
                                t.is_synthetic = true
                            MERGE (f)-[:VERIFIED_BY]->(t)
                            """,
                            {
                                "fix_id": fix_id,
                                "test_id": test_id,
                                "test_title": f"test_regression_{bug_id.lower()}",
                                "test_desc": verification,
                                "verification": verification,
                            },
                        )
            except Exception as e:
                logger.error(f"Error persisting bug to Neo4j: {e}")

        return bug_id, connected_paths

    def retrieve_context_for_analysis(
        self, project_id: str, question: str, target_component: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Traverse the graph to extract grounded historical evidence:
        - Relevant components based on keywords in question or target_component
        - Connected technical decisions, reasons, and pull requests
        - Historical bugs, symptoms, root causes, fixes, and regression tests
        - Upstream and downstream dependencies
        - Exact graph path chains for citations
        """
        detected_comp = target_component
        if not detected_comp:
            detected_comp = self._detect_component_from_text(question)

        comp_id = self._resolve_component_id(detected_comp) if detected_comp else "COMP-AUTH"
        comp_name = detected_comp or "Authentication"

        # Evidence packages
        evidence_records: List[EvidenceRecord] = []
        evidence_paths: List[str] = []
        decisions: List[Dict[str, Any]] = []
        bugs: List[Dict[str, Any]] = []
        dependencies: List[Dict[str, Any]] = []
        tests: List[Dict[str, Any]] = []

        # If live Neo4j is connected, run deep traversal Cypher
        if db_manager.is_connected:
            try:
                cypher = """
                MATCH (c:Component)
                WHERE c.id = $comp_id OR toLower(c.name) = toLower($comp_name) OR $comp_name IN [c.name]
                OPTIONAL MATCH (c)-[:AFFECTED_BY]->(d:Decision)
                OPTIONAL MATCH (d)-[:JUSTIFIED_BY]->(r:Reason)
                OPTIONAL MATCH (c)-[:HAS_BUG]->(b:Bug)
                OPTIONAL MATCH (b)-[:RESOLVED_BY]->(f:Fix)
                OPTIONAL MATCH (f)-[:VERIFIED_BY]->(t:Test)
                OPTIONAL MATCH (c)-[:DEPENDS_ON]->(dep:Dependency)
                RETURN c, collect(DISTINCT d) AS decisions, collect(DISTINCT r) AS reasons,
                       collect(DISTINCT b) AS bugs, collect(DISTINCT f) AS fixes,
                       collect(DISTINCT t) AS tests, collect(DISTINCT dep) AS deps
                """
                res = db_manager.run_query(cypher, {"comp_id": comp_id, "comp_name": comp_name})
                if res and res[0].get("c"):
                    row = res[0]
                    # Process Neo4j records into structured evidence
                    for d in row.get("decisions", []):
                        if d and d.get("id"):
                            decisions.append(dict(d))
                            evidence_records.append(EvidenceRecord(
                                id=d.get("id"),
                                type="Decision",
                                title=d.get("title", "Technical Decision"),
                                details=dict(d),
                                relation="AFFECTED_BY",
                            ))
                            evidence_paths.append(f"({comp_name})-[:AFFECTED_BY]->({d.get('id')}:Decision: '{d.get('title')}')")

                    for b in row.get("bugs", []):
                        if b and b.get("id"):
                            bugs.append(dict(b))
                            evidence_records.append(EvidenceRecord(
                                id=b.get("id"),
                                type="Bug",
                                title=b.get("title", "Historical Bug"),
                                details=dict(b),
                                relation="HAS_BUG",
                            ))
                            evidence_paths.append(f"({comp_name})-[:HAS_BUG]->({b.get('id')}:Bug: '{b.get('title')}')")

                    for t in row.get("tests", []):
                        if t and t.get("id"):
                            tests.append(dict(t))
                            evidence_records.append(EvidenceRecord(
                                id=t.get("id"),
                                type="Test",
                                title=t.get("title", "Regression Test"),
                                details=dict(t),
                                relation="VERIFIED_BY",
                            ))

                    for dep in row.get("deps", []):
                        if dep and dep.get("id"):
                            dependencies.append(dict(dep))

                    return {
                        "project_id": project_id,
                        "detected_component": comp_name,
                        "component_id": comp_id,
                        "decisions": decisions,
                        "bugs": bugs,
                        "dependencies": dependencies,
                        "tests": tests,
                        "evidence_records": [e.model_dump() for e in evidence_records],
                        "evidence_paths": evidence_paths,
                    }
            except Exception as e:
                logger.warning(f"Error querying Neo4j for context: {e}. Falling back to in-memory traversal.")

        # In-memory graph traversal fallback
        comp_node = in_memory_store.nodes.get(comp_id)
        if not comp_node:
            for nid, node in in_memory_store.nodes.items():
                if node["label"] == "Component" and node["properties"].get("name", "").lower() == comp_name.lower():
                    comp_id = nid
                    comp_node = node
                    break

        if comp_node:
            # 1. Decisions affecting this component
            for edge in in_memory_store.edges:
                if edge["source"] == comp_id and edge["type"] == "AFFECTED_BY":
                    dec_node = in_memory_store.nodes.get(edge["target"])
                    if dec_node:
                        dec_props = dec_node["properties"]
                        decisions.append(dec_props)
                        evidence_records.append(EvidenceRecord(
                            id=dec_node["id"],
                            type="Decision",
                            title=dec_props.get("title", "Technical Decision"),
                            details=dec_props,
                            relation="AFFECTED_BY",
                        ))
                        # Find reasons
                        for r_edge in in_memory_store.edges:
                            if r_edge["source"] == dec_node["id"] and r_edge["type"] == "JUSTIFIED_BY":
                                r_node = in_memory_store.nodes.get(r_edge["target"])
                                if r_node:
                                    evidence_paths.append(
                                        f"({comp_name})-[:AFFECTED_BY]->({dec_node['id']}:Decision)-[:JUSTIFIED_BY]->({r_node['id']}:Reason: '{r_node['properties'].get('text')}')"
                                    )
                                    break
                        else:
                            evidence_paths.append(f"({comp_name})-[:AFFECTED_BY]->({dec_node['id']}:Decision: '{dec_props.get('title')}')")

                # 2. Bugs on this component
                if edge["source"] == comp_id and edge["type"] == "HAS_BUG":
                    bug_node = in_memory_store.nodes.get(edge["target"])
                    if bug_node:
                        b_props = bug_node["properties"]
                        bugs.append(b_props)
                        evidence_records.append(EvidenceRecord(
                            id=bug_node["id"],
                            type="Bug",
                            title=b_props.get("title", "Historical Incident"),
                            details=b_props,
                            relation="HAS_BUG",
                        ))
                        # Trace to fix and test
                        fix_found = None
                        test_found = None
                        for f_edge in in_memory_store.edges:
                            if f_edge["source"] == bug_node["id"] and f_edge["type"] == "RESOLVED_BY":
                                fix_node = in_memory_store.nodes.get(f_edge["target"])
                                if fix_node:
                                    fix_found = fix_node
                                    for t_edge in in_memory_store.edges:
                                        if t_edge["source"] == fix_node["id"] and t_edge["type"] == "VERIFIED_BY":
                                            test_found = in_memory_store.nodes.get(t_edge["target"])
                                            break

                        if fix_found and test_found:
                            tests.append(test_found["properties"])
                            evidence_paths.append(
                                f"({comp_name})-[:HAS_BUG]->({bug_node['id']}:Bug)-[:RESOLVED_BY]->({fix_found['id']}:Fix)-[:VERIFIED_BY]->({test_found['id']}:Test: '{test_found['properties'].get('title')}')"
                            )
                        elif fix_found:
                            evidence_paths.append(
                                f"({comp_name})-[:HAS_BUG]->({bug_node['id']}:Bug)-[:RESOLVED_BY]->({fix_found['id']}:Fix)"
                            )
                        else:
                            evidence_paths.append(f"({comp_name})-[:HAS_BUG]->({bug_node['id']}:Bug)")

                # 3. Dependencies
                if edge["source"] == comp_id and edge["type"] == "DEPENDS_ON":
                    target_node = in_memory_store.nodes.get(edge["target"])
                    if target_node:
                        dependencies.append(target_node["properties"])

        # Also check connected component relationships (e.g. Users API -> Authentication)
        for edge in in_memory_store.edges:
            if edge["type"] == "DEPENDS_ON":
                source_comp = in_memory_store.nodes.get(edge["source"])
                target_comp = in_memory_store.nodes.get(edge["target"])
                if source_comp and target_comp and source_comp["label"] == "Component" and target_comp["label"] == "Component":
                    if comp_id in [source_comp["id"], target_comp["id"]]:
                        evidence_paths.append(
                            f"({source_comp['properties'].get('name')})-[:DEPENDS_ON]->({target_comp['properties'].get('name')})"
                        )

        return {
            "project_id": project_id,
            "detected_component": comp_name,
            "component_id": comp_id,
            "decisions": decisions,
            "bugs": bugs,
            "dependencies": dependencies,
            "tests": tests,
            "evidence_records": [e.model_dump() for e in evidence_records],
            "evidence_paths": list(set(evidence_paths)),
        }

    def get_downstream_impact(
        self,
        project_id: str,
        changed_components: Optional[List[str]] = None,
        changed_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Traverse the graph downstream:
        If component X changes, any component that DEPENDS_ON X (directly or transitively) is affected!
        Also resolves modified file paths to components, and handles unknown components gracefully.
        """
        changed_components = changed_components or []
        changed_files = changed_files or []

        # Resolve files to components
        all_comp_inputs = list(changed_components)
        for fp in changed_files:
            resolved_from_fp = self._resolve_component_from_file_path(fp)
            if resolved_from_fp and resolved_from_fp not in all_comp_inputs:
                all_comp_inputs.append(resolved_from_fp)

        # Distinguish known cataloged components from unknown/unresolved inputs
        known_components: List[str] = []
        unresolved_inputs: List[str] = []

        for c in all_comp_inputs:
            cid = self._resolve_component_id(c)
            cname = self._resolve_component_name(c)
            # Check if component exists in knowledge graph
            if cid in in_memory_store.nodes or any(
                n["label"] == "Component" and n["properties"].get("name", "").lower() == c.lower()
                for n in in_memory_store.nodes.values()
            ):
                if cname not in known_components:
                    known_components.append(cname)
            else:
                unresolved_inputs.append(c)

        directly_changed_ids = [self._resolve_component_id(c) for c in known_components]
        directly_changed_names = [self._resolve_component_name(c) for c in known_components]

        affected_components: List[AffectedComponent] = []
        historical_risks: List[Dict[str, Any]] = []
        technical_decisions: List[Dict[str, Any]] = []
        suggested_tests: List[Dict[str, Any]] = []
        graph_paths: List[List[str]] = []
        seen_affected: Set[str] = set()

        # Mark directly changed components
        for cid, cname in zip(directly_changed_ids, directly_changed_names):
            affected_components.append(AffectedComponent(
                id=cid,
                name=cname,
                tier="direct",
                reason=f"Directly modified component under review ({cname})",
                path=[cname],
                status_label="potential_impact",
            ))
            seen_affected.add(cid)
            seen_affected.add(cname)

        # Handle unresolved / unknown inputs gracefully without crashing
        for unk in unresolved_inputs:
            affected_components.append(AffectedComponent(
                id=f"UNKNOWN-{unk.upper().replace(' ', '_')}",
                name=unk,
                tier="unresolved",
                reason=f"Component '{unk}' not cataloged in knowledge graph; no downstream dependency paths available",
                path=[unk],
                status_label="unresolved",
            ))

        # BFS downstream traversal: find components that depend on directly changed components
        # Edge direction in graph: (Consumer)-[:DEPENDS_ON]->(Provider)
        current_tier_ids = set(directly_changed_ids)
        current_tier_names = set(directly_changed_names)
        depth = 1

        while (current_tier_ids or current_tier_names) and depth <= 3:
            next_tier_ids = set()
            for edge in in_memory_store.edges:
                if edge["type"] == "DEPENDS_ON":
                    target_id = edge["target"]
                    source_id = edge["source"]
                    source_node = in_memory_store.nodes.get(source_id)

                    if target_id in current_tier_ids and source_node and source_node["label"] == "Component":
                        if source_id not in seen_affected:
                            seen_affected.add(source_id)
                            next_tier_ids.add(source_id)
                            source_name = source_node["properties"].get("name", source_id)
                            target_node = in_memory_store.nodes.get(target_id)
                            target_name = target_node["properties"].get("name", target_id) if target_node else target_id

                            tier_label = f"downstream_{depth}" if depth <= 2 else "transitive"
                            affected_components.append(AffectedComponent(
                                id=source_id,
                                name=source_name,
                                tier=tier_label,  # type: ignore
                                reason=f"Consumes '{target_name}' via DEPENDS_ON relationship (Depth {depth})",
                                path=[target_name, source_name],
                                status_label="potential_impact",
                            ))
                            graph_paths.append([target_name, "DEPENDS_ON", source_name])
            current_tier_ids = next_tier_ids
            depth += 1

        # Retrieve historical risks, technical decisions, and regression tests for affected components
        seen_bugs = set()
        seen_decisions = set()
        seen_tests = set()

        for aff in affected_components:
            cid = aff.id
            cname = aff.name

            # Check bugs and fixes
            for edge in in_memory_store.edges:
                if edge["source"] == cid and edge["type"] == "HAS_BUG":
                    bug_node = in_memory_store.nodes.get(edge["target"])
                    if bug_node and bug_node["id"] not in seen_bugs:
                        seen_bugs.add(bug_node["id"])
                        b_props = bug_node["properties"]
                        historical_risks.append({
                            "component": cname,
                            "bug_id": bug_node["id"],
                            "title": b_props.get("title"),
                            "symptom": b_props.get("symptom"),
                            "root_cause": b_props.get("root_cause"),
                            "status": b_props.get("status"),
                        })
                        # Check associated tests
                        for f_edge in in_memory_store.edges:
                            if f_edge["source"] == bug_node["id"] and f_edge["type"] == "RESOLVED_BY":
                                fix_id = f_edge["target"]
                                for t_edge in in_memory_store.edges:
                                    if t_edge["source"] == fix_id and t_edge["type"] == "VERIFIED_BY":
                                        test_node = in_memory_store.nodes.get(t_edge["target"])
                                        if test_node and test_node["id"] not in seen_tests:
                                            seen_tests.add(test_node["id"])
                                            t_props = test_node["properties"]
                                            suggested_tests.append({
                                                "test_id": test_node["id"],
                                                "title": t_props.get("title"),
                                                "target_component": cname,
                                                "description": t_props.get("description"),
                                                "verification_status": t_props.get("verification_status"),
                                                "associated_bug": bug_node["id"],
                                            })

                # Check technical decisions
                if edge["source"] == cid and edge["type"] == "AFFECTED_BY":
                    dec_node = in_memory_store.nodes.get(edge["target"])
                    if dec_node and dec_node["id"] not in seen_decisions:
                        seen_decisions.add(dec_node["id"])
                        d_props = dec_node["properties"]
                        technical_decisions.append({
                            "decision_id": dec_node["id"],
                            "title": d_props.get("title"),
                            "reason": d_props.get("reason"),
                            "author": d_props.get("author"),
                            "status": d_props.get("status"),
                            "affected_component": cname,
                        })

        # Heuristic Priority Evaluation (Deterministic rules without invented probabilities)
        priority_reasons: List[str] = []
        has_historical_bugs = len(historical_risks) > 0
        downstream_count = len([a for a in affected_components if a.tier != "direct" and a.tier != "unresolved"])

        if has_historical_bugs and downstream_count > 0:
            heuristic_priority = "HIGH"
            priority_reasons.append("Historical regression incidents recorded on affected components (e.g. BUG-101).")
            priority_reasons.append(f"{downstream_count} downstream consumer component(s) potentially impacted.")
        elif downstream_count > 1 or has_historical_bugs:
            heuristic_priority = "MEDIUM"
            if downstream_count > 1:
                priority_reasons.append(f"Multiple downstream services ({downstream_count}) depend on modified modules.")
            if has_historical_bugs:
                priority_reasons.append("Historical bug recorded on directly changed module.")
        else:
            heuristic_priority = "LOW"
            priority_reasons.append("Isolated change with limited or zero downstream propagation.")

        explanations = [
            f"Evaluated {len(known_components)} recognized component(s) and {len(unresolved_inputs)} uncataloged input(s).",
            f"Downstream dependency traversal identified {downstream_count} potential indirect consumer(s).",
            f"Retrieved {len(historical_risks)} historical incident(s), {len(technical_decisions)} architectural decision(s), and {len(suggested_tests)} regression test recommendation(s).",
        ]

        return {
            "project_id": project_id,
            "directly_changed": directly_changed_names,
            "unresolved_inputs": unresolved_inputs,
            "affected_components": [a.model_dump() for a in affected_components],
            "historical_risks": historical_risks,
            "technical_decisions": technical_decisions,
            "suggested_tests": suggested_tests,
            "graph_paths": graph_paths,
            "heuristic_priority": heuristic_priority,
            "priority_reasons": priority_reasons,
            "explanations": explanations,
        }

    def get_recent_activity(self, project_id: str = "PRJ-SENTINEL", limit: int = 10) -> List[ActivityEvent]:
        return in_memory_store.activity_log[:limit]

    def _resolve_component_id(self, comp_name_or_id: str) -> str:
        clean = comp_name_or_id.strip()
        if clean.startswith("COMP-"):
            return clean
        mapping = {
            "authentication": "COMP-AUTH",
            "auth": "COMP-AUTH",
            "users api": "COMP-USERS",
            "users": "COMP-USERS",
            "admin dashboard": "COMP-ADMIN",
            "admin": "COMP-ADMIN",
            "notification service": "COMP-NOTIF",
            "notification": "COMP-NOTIF",
            "notifications": "COMP-NOTIF",
        }
        return mapping.get(clean.lower(), f"COMP-{clean.upper().replace(' ', '_')}")

    def _resolve_component_name(self, comp_name_or_id: str) -> str:
        clean = comp_name_or_id.strip()
        rev_mapping = {
            "COMP-AUTH": "Authentication",
            "COMP-USERS": "Users API",
            "COMP-ADMIN": "Admin Dashboard",
            "COMP-NOTIF": "Notification Service",
        }
        if clean in rev_mapping:
            return rev_mapping[clean]
        if clean in in_memory_store.nodes:
            return in_memory_store.nodes[clean]["properties"].get("name", clean)
        return clean

    def _detect_component_from_text(self, text: str) -> Optional[str]:
        lower = text.lower()
        if "auth" in lower or "jwt" in lower or "token" in lower or "login" in lower:
            return "Authentication"
        if "user" in lower or "profile" in lower:
            return "Users API"
        if "admin" in lower or "dashboard" in lower:
            return "Admin Dashboard"
        if "notification" in lower or "email" in lower or "webhook" in lower:
            return "Notification Service"
        return None

    def _resolve_component_from_file_path(self, file_path: str) -> Optional[str]:
        clean = file_path.strip().lower()
        if "auth" in clean or "jwt" in clean or "token" in clean or "login" in clean:
            return "Authentication"
        if "user" in clean or "profile" in clean or "account" in clean:
            return "Users API"
        if "admin" in clean or "dashboard" in clean or "metric" in clean:
            return "Admin Dashboard"
        if "notif" in clean or "email" in clean or "webhook" in clean:
            return "Notification Service"
        return None


graph_service = GraphService()
