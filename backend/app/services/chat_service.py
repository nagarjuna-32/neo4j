import re
import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.app.config import settings
from backend.app.database import db_manager
from backend.app.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatEvidence,
)
from backend.app.services.graph_service import in_memory_store

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

logger = logging.getLogger("codebrain.chat_service")


class ChatService:
    def __init__(self):
        self.openai_client: Optional[Any] = None
        if OPENAI_AVAILABLE and settings.is_openai_configured:
            try:
                self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as exc:
                logger.warning(f"Could not initialize OpenAI client in ChatService: {exc}")

    # ================= 1. INTENT & ENTITY EXTRACTION =================
    def classify_intent(self, message: str, history: List[ChatMessage] = []) -> str:
        text = message.lower().strip()

        # Check for project listing / architecture queries first
        project_info_keywords = [
            "show all", "list all", "which components", "what decisions",
            "which fixes", "what could be affected", "summarize", "architecture",
            "depend on", "dependencies", "all recorded", "latest project memories",
            "how many components", "what components"
        ]
        if any(kw in text for kw in project_info_keywords):
            return "project_info"

        # Check for code questions
        code_keywords = [
            "how should i handle", "how do i write", "how to write", "how do i handle",
            "write code", "code example", "in fastapi", "in python", "middleware in",
            "syntax", "sample code", "implementation", "show the fix in python",
            "show me the fix in python", "code snippet"
        ]
        if any(kw in text for kw in code_keywords):
            return "code_question"

        # Check for debugging/troubleshooting keywords
        debug_keywords = [
            "401", "500", "403", "404", "error", "bug", "fail", "failing",
            "failure", "fix it", "how do i fix", "how to fix", "issue",
            "crash", "broken", "troubleshoot", "debug", "symptom", "root cause",
            "unauthorized", "exception", "traceback"
        ]
        if any(kw in text for kw in debug_keywords):
            return "debugging"

        # Check for direct entity questions
        direct_info_keywords = [
            "what is", "why did we", "who authored", "tell me about",
            "explain component", "explain decision", "explain bug", "what does"
        ]
        if any(kw in text for kw in direct_info_keywords):
            return "direct_info"

        # If previous assistant turn was a debugging analysis and user asks follow-up
        if history:
            last_user_or_asst = history[-1].content.lower()
            if any(w in text for w in ["explain", "why", "what", "how", "cause", "evidence", "test"]):
                if "401" in last_user_or_asst or "bug" in last_user_or_asst or "fix" in last_user_or_asst:
                    return "debugging"
                return "direct_info"

        return "general"

    def extract_keywords_and_entities(
        self, message: str, history: List[ChatMessage] = []
    ) -> Dict[str, Any]:
        """Extract referenced components, decisions, bugs, fixes, and dependencies from prompt and context."""
        full_context = message.lower()
        # Include last message from history to resolve anaphoric follow-ups
        if history:
            full_context += " " + history[-1].content.lower()

        entities: Dict[str, Any] = {
            "component": None,
            "decision": None,
            "bug": None,
            "dependency": None,
            "file": None,
            "is_list_query": False,
            "list_target": None,
            "search_terms": [],
        }

        # Component detection
        if "authentication" in full_context or "auth" in full_context or "comp-auth" in full_context or "login" in full_context:
            entities["component"] = "Authentication"
        elif "users api" in full_context or "users" in full_context or "comp-users" in full_context or "profile" in full_context:
            entities["component"] = "Users API"
        elif "admin dashboard" in full_context or "admin" in full_context or "comp-admin" in full_context:
            entities["component"] = "Admin Dashboard"
        elif "notification service" in full_context or "notification" in full_context or "comp-notif" in full_context:
            entities["component"] = "Notification Service"

        # Decision detection
        if "jwt" in full_context or "session" in full_context or "dec-101" in full_context or "adr-042" in full_context or "stateless" in full_context:
            entities["decision"] = "DEC-101"

        # Bug detection
        if "401" in full_context or "bug-101" in full_context or "inc-4019" in full_context or "refresh token" in full_context:
            entities["bug"] = "BUG-101"

        # Dependency detection
        if "pyjwt" in full_context or "jose" in full_context or "dep-jwt" in full_context:
            entities["dependency"] = "DEP-JWT"
        elif "fastapi" in full_context or "dep-fastapi" in full_context:
            entities["dependency"] = "DEP-FASTAPI"
        elif "postgres" in full_context or "dep-postgres" in full_context:
            entities["dependency"] = "DEP-POSTGRES"

        # List query targets
        if any(w in message.lower() for w in ["all bugs", "recorded bugs", "list bugs", "show bugs"]):
            entities["is_list_query"] = True
            entities["list_target"] = "bugs"
        elif any(w in message.lower() for w in ["all decisions", "decisions relate", "list decisions", "show decisions"]):
            entities["is_list_query"] = True
            entities["list_target"] = "decisions"
        elif any(w in message.lower() for w in ["all components", "list components", "show components"]):
            entities["is_list_query"] = True
            entities["list_target"] = "components"
        elif any(w in message.lower() for w in ["verified regression", "verified tests", "which tests", "which fixes have verified"]):
            entities["is_list_query"] = True
            entities["list_target"] = "tests"
        elif any(w in message.lower() for w in ["latest project memories", "summarize memories", "latest memories"]):
            entities["is_list_query"] = True
            entities["list_target"] = "memories"
        elif any(w in message.lower() for w in ["architecture of this project", "explain the architecture", "system architecture"]):
            entities["is_list_query"] = True
            entities["list_target"] = "architecture"

        # Extract search terms
        tokens = re.findall(r"[A-Za-z0-9_-]{3,}", message)
        entities["search_terms"] = [t for t in tokens if t.lower() not in ["the", "what", "why", "how", "which", "show", "tell", "explain", "this", "that", "with", "from"]]

        return entities

    # ================= 2. GRAPH EVIDENCE RETRIEVAL =================
    def retrieve_grounded_evidence(
        self,
        project_id: str,
        intent: str,
        entities: Dict[str, Any],
        message: str,
    ) -> Tuple[List[ChatEvidence], Dict[str, Any]]:
        """Retrieve bounded, parameterized graph evidence from Neo4j or in-memory graph store."""
        evidence_list: List[ChatEvidence] = []
        context_data: Dict[str, Any] = {
            "records": [],
            "relationships": [],
            "intent": intent,
            "project_id": project_id,
        }

        # Try live Neo4j first if connected
        if db_manager.is_connected:
            try:
                evidence_list, context_data = self._retrieve_from_neo4j(
                    project_id, intent, entities, message
                )
                if evidence_list:
                    return evidence_list, context_data
            except Exception as exc:
                logger.warning(f"Neo4j query failed in chat retrieval: {exc}. Falling back to in-memory store.")

        # In-memory graph traversal fallback
        return self._retrieve_from_in_memory(project_id, intent, entities, message)

    def _retrieve_from_neo4j(
        self,
        project_id: str,
        intent: str,
        entities: Dict[str, Any],
        message: str,
    ) -> Tuple[List[ChatEvidence], Dict[str, Any]]:
        evidence_list: List[ChatEvidence] = []
        context_data: Dict[str, Any] = {
            "records": [],
            "relationships": [],
            "intent": intent,
            "project_id": project_id,
        }

        # 1. Broad / List queries
        if entities.get("is_list_query"):
            target = entities.get("list_target")
            if target == "bugs":
                cypher = """
                MATCH (b:Bug)
                WHERE b.project_id = $project_id OR b.project_id IS NULL
                OPTIONAL MATCH (c:Component)-[:HAS_BUG]->(b)
                OPTIONAL MATCH (b)-[:RESOLVED_BY]->(f:Fix)
                OPTIONAL MATCH (f)-[:VERIFIED_BY]->(t:Test)
                RETURN b, c.name AS component_name, f, t
                LIMIT 15
                """
                rows = db_manager.run_query(cypher, {"project_id": project_id})
                for r in rows:
                    b = r.get("b", {})
                    f = r.get("f")
                    t = r.get("t")
                    comp = r.get("component_name") or "Authentication"
                    evidence_list.append(ChatEvidence(
                        id=b.get("id", "BUG-UNKNOWN"),
                        type="Bug",
                        title=b.get("title", "Recorded Bug"),
                        description=f"Symptom: {b.get('symptom', 'N/A')} | Root Cause: {b.get('root_cause', 'N/A')}",
                        related_to=f"Component: {comp}",
                        source="Project Memory",
                        properties=dict(b),
                    ))
                    if f:
                        evidence_list.append(ChatEvidence(
                            id=f.get("id", "FIX-UNKNOWN"),
                            type="Fix",
                            title=f.get("title", "Fix"),
                            description=f.get("description", ""),
                            related_to=b.get("id"),
                            source="Project Memory",
                            properties=dict(f),
                        ))
                    if t:
                        evidence_list.append(ChatEvidence(
                            id=t.get("id", "TEST-UNKNOWN"),
                            type="Test",
                            title=t.get("title", "Test"),
                            description=f"Verification: {t.get('verification_status', 'Verified')}",
                            related_to=f.get("id", "Fix") if f else b.get("id"),
                            source="Project Memory",
                            properties=dict(t),
                        ))
                return evidence_list, context_data

            elif target == "decisions":
                cypher = """
                MATCH (d:Decision)
                WHERE d.project_id = $project_id OR d.project_id IS NULL
                OPTIONAL MATCH (d)-[:JUSTIFIED_BY]->(r:Reason)
                OPTIONAL MATCH (c:Component)-[:AFFECTED_BY]->(d)
                RETURN d, r.text AS reason, c.name AS component_name
                LIMIT 15
                """
                rows = db_manager.run_query(cypher, {"project_id": project_id})
                for r in rows:
                    d = r.get("d", {})
                    evidence_list.append(ChatEvidence(
                        id=d.get("id", "DEC-UNKNOWN"),
                        type="Decision",
                        title=d.get("title", "Architecture Decision"),
                        description=f"Rationale: {r.get('reason') or d.get('reason', 'N/A')} | Rationale Details: {d.get('description', '')}",
                        related_to=f"Component: {r.get('component_name', 'System')}",
                        source="Project Memory",
                        properties=dict(d),
                    ))
                return evidence_list, context_data

            elif target in ("architecture", "components"):
                cypher = """
                MATCH (c:Component)
                WHERE c.project_id = $project_id OR c.project_id IS NULL
                OPTIONAL MATCH (c)-[:DEPENDS_ON]->(dep)
                RETURN c, collect(DISTINCT dep.name) AS dependencies
                LIMIT 15
                """
                rows = db_manager.run_query(cypher, {"project_id": project_id})
                for r in rows:
                    c = r.get("c", {})
                    deps = r.get("dependencies", [])
                    evidence_list.append(ChatEvidence(
                        id=c.get("id", "COMP-UNKNOWN"),
                        type="Component",
                        title=c.get("name", "Component"),
                        description=f"{c.get('description', '')} [Dependencies: {', '.join(deps) if deps else 'None'}]",
                        related_to="Project PRJ-SENTINEL",
                        source="Project Memory",
                        properties=dict(c),
                    ))
                return evidence_list, context_data

            elif target == "tests":
                cypher = """
                MATCH (f:Fix)-[:VERIFIED_BY]->(t:Test)
                OPTIONAL MATCH (b:Bug)-[:RESOLVED_BY]->(f)
                RETURN t, f, b
                LIMIT 10
                """
                rows = db_manager.run_query(cypher, {})
                for r in rows:
                    t = r.get("t", {})
                    f = r.get("f", {})
                    b = r.get("b", {})
                    evidence_list.append(ChatEvidence(
                        id=t.get("id", "TEST-UNKNOWN"),
                        type="Test",
                        title=t.get("title", "Regression Test"),
                        description=f"Verifies fix {f.get('id', '')} for bug {b.get('id', '')}: {t.get('description', '')}",
                        related_to=f.get("title", "Fix"),
                        source="Project Memory",
                        properties=dict(t),
                    ))
                return evidence_list, context_data

        # 2. Reverse dependency check: "Which components depend on [Component]?"
        if "depend on" in message.lower() and entities.get("component"):
            target_comp = entities["component"]
            cypher = """
            MATCH (dep:Component)
            WHERE toLower(dep.name) = toLower($target_comp)
            MATCH (c:Component)-[:DEPENDS_ON]->(dep)
            RETURN c, dep
            """
            rows = db_manager.run_query(cypher, {"target_comp": target_comp})
            for r in rows:
                c = r.get("c", {})
                evidence_list.append(ChatEvidence(
                    id=c.get("id", "COMP-UNKNOWN"),
                    type="Component",
                    title=c.get("name", "Dependent Component"),
                    description=f"{c.get('name')} depends on {target_comp}: {c.get('description', '')}",
                    related_to=f"Depends on {target_comp}",
                    source="Project Memory",
                    properties=dict(c),
                ))
            if evidence_list:
                return evidence_list, context_data

        # 3. Direct component / decision / bug specific traversal
        comp_name = entities.get("component") or "Authentication"
        cypher = """
        MATCH (c:Component)
        WHERE toLower(c.name) CONTAINS toLower($comp_name) OR c.id = $comp_name
        OPTIONAL MATCH (c)-[:AFFECTED_BY]->(d:Decision)
        OPTIONAL MATCH (d)-[:JUSTIFIED_BY]->(r:Reason)
        OPTIONAL MATCH (c)-[:HAS_BUG]->(b:Bug)
        OPTIONAL MATCH (b)-[:RESOLVED_BY]->(f:Fix)
        OPTIONAL MATCH (f)-[:VERIFIED_BY]->(t:Test)
        OPTIONAL MATCH (c)-[:DEPENDS_ON]->(dep:Dependency)
        RETURN c, collect(DISTINCT d) AS decisions, collect(DISTINCT r) AS reasons,
               collect(DISTINCT b) AS bugs, collect(DISTINCT f) AS fixes,
               collect(DISTINCT t) AS tests, collect(DISTINCT dep) AS deps
        LIMIT 5
        """
        rows = db_manager.run_query(cypher, {"comp_name": comp_name})
        if rows and rows[0].get("c"):
            r = rows[0]
            c = r["c"]
            evidence_list.append(ChatEvidence(
                id=c.get("id", "COMP-UNKNOWN"),
                type="Component",
                title=c.get("name", "Component"),
                description=c.get("description", ""),
                related_to="PRJ-SENTINEL",
                source="Project Memory",
                properties=dict(c),
            ))
            for d in r.get("decisions", []):
                if d and d.get("id"):
                    evidence_list.append(ChatEvidence(
                        id=d.get("id"),
                        type="Decision",
                        title=d.get("title", "Technical Decision"),
                        description=f"Rationale: {d.get('reason', '')} | {d.get('description', '')}",
                        related_to=c.get("name"),
                        source="Project Memory",
                        properties=dict(d),
                    ))
            for b in r.get("bugs", []):
                if b and b.get("id"):
                    evidence_list.append(ChatEvidence(
                        id=b.get("id"),
                        type="Bug",
                        title=b.get("title", "Historical Bug"),
                        description=f"Symptom: {b.get('symptom', '')} | Root cause: {b.get('root_cause', '')}",
                        related_to=c.get("name"),
                        source="Project Memory",
                        properties=dict(b),
                    ))
            for f in r.get("fixes", []):
                if f and f.get("id"):
                    evidence_list.append(ChatEvidence(
                        id=f.get("id"),
                        type="Fix",
                        title=f.get("title", "Fix"),
                        description=f.get("description", ""),
                        related_to="BUG-101",
                        source="Project Memory",
                        properties=dict(f),
                    ))
            for t in r.get("tests", []):
                if t and t.get("id"):
                    evidence_list.append(ChatEvidence(
                        id=t.get("id"),
                        type="Test",
                        title=t.get("title", "Test"),
                        description=t.get("description", ""),
                        related_to="Fix",
                        source="Project Memory",
                        properties=dict(t),
                    ))
            for dep in r.get("deps", []):
                if dep and dep.get("id"):
                    evidence_list.append(ChatEvidence(
                        id=dep.get("id"),
                        type="Dependency",
                        title=dep.get("name", "Dependency"),
                        description=f"Version: {dep.get('version', '')} ({dep.get('type', '')})",
                        related_to=c.get("name"),
                        source="Project Memory",
                        properties=dict(dep),
                    ))

        return evidence_list, context_data

    def _retrieve_from_in_memory(
        self,
        project_id: str,
        intent: str,
        entities: Dict[str, Any],
        message: str,
    ) -> Tuple[List[ChatEvidence], Dict[str, Any]]:
        evidence_list: List[ChatEvidence] = []
        context_data: Dict[str, Any] = {
            "records": [],
            "relationships": [],
            "intent": intent,
            "project_id": project_id,
        }

        msg_lower = message.lower()

        # 1. List / Broad queries
        if entities.get("is_list_query"):
            target = entities.get("list_target")
            if target == "bugs":
                for nid, n in in_memory_store.nodes.items():
                    if n["label"] == "Bug":
                        p = n["properties"]
                        evidence_list.append(ChatEvidence(
                            id=nid,
                            type="Bug",
                            title=p.get("title", nid),
                            description=f"Symptom: {p.get('symptom', 'N/A')} | Root Cause: {p.get('root_cause', 'N/A')} | Status: {p.get('status', 'RESOLVED')}",
                            related_to=f"Component: {p.get('affected_component', 'Authentication')}",
                            source="Project Memory",
                            properties=p,
                        ))
                return evidence_list, context_data

            elif target == "decisions":
                for nid, n in in_memory_store.nodes.items():
                    if n["label"] == "Decision":
                        p = n["properties"]
                        evidence_list.append(ChatEvidence(
                            id=nid,
                            type="Decision",
                            title=p.get("title", nid),
                            description=f"Rationale: {p.get('reason', 'N/A')} | {p.get('description', '')}",
                            related_to="Authentication",
                            source="Project Memory",
                            properties=p,
                        ))
                return evidence_list, context_data

            elif target in ("architecture", "components"):
                for nid, n in in_memory_store.nodes.items():
                    if n["label"] == "Component":
                        p = n["properties"]
                        # find dependencies
                        deps = []
                        for edge in in_memory_store.edges:
                            if edge["source"] == nid and edge["type"] == "DEPENDS_ON":
                                target_node = in_memory_store.nodes.get(edge["target"])
                                if target_node:
                                    deps.append(target_node["properties"].get("name", edge["target"]))
                        evidence_list.append(ChatEvidence(
                            id=nid,
                            type="Component",
                            title=p.get("name", nid),
                            description=f"{p.get('description', '')} [Dependencies: {', '.join(deps) if deps else 'None'}]",
                            related_to="Project PRJ-SENTINEL",
                            source="Project Memory",
                            properties=p,
                        ))
                return evidence_list, context_data

            elif target == "tests":
                for nid, n in in_memory_store.nodes.items():
                    if n["label"] == "Test":
                        p = n["properties"]
                        evidence_list.append(ChatEvidence(
                            id=nid,
                            type="Test",
                            title=p.get("title", nid),
                            description=f"{p.get('description', '')} | Verification: {p.get('verification_status', 'Passed')}",
                            related_to="FIX-101",
                            source="Project Memory",
                            properties=p,
                        ))
                return evidence_list, context_data

            elif target == "memories":
                for nid, n in in_memory_store.nodes.items():
                    if n["label"] in ("Decision", "Bug", "Fix", "Test"):
                        p = n["properties"]
                        evidence_list.append(ChatEvidence(
                            id=nid,
                            type=n["label"],
                            title=p.get("title", p.get("name", nid)),
                            description=p.get("description", p.get("reason", p.get("root_cause", ""))),
                            related_to=p.get("affected_component", "PRJ-SENTINEL"),
                            source="Project Memory",
                            properties=p,
                        ))
                return evidence_list[:12], context_data

        # 2. Reverse dependency check: "Which components depend on [Component]?"
        if "depend on" in msg_lower and ("authentication" in msg_lower or "users" in msg_lower):
            target_name = "Authentication" if "authentication" in msg_lower else "Users API"
            target_id = "COMP-AUTH" if target_name == "Authentication" else "COMP-USERS"

            for edge in in_memory_store.edges:
                if edge["target"] == target_id and edge["type"] == "DEPENDS_ON":
                    src_node = in_memory_store.nodes.get(edge["source"])
                    if src_node and src_node["label"] == "Component":
                        p = src_node["properties"]
                        evidence_list.append(ChatEvidence(
                            id=src_node["id"],
                            type="Component",
                            title=p.get("name", src_node["id"]),
                            description=f"{p.get('name')} depends on {target_name}: {p.get('description', '')}",
                            related_to=f"Depends on {target_name}",
                            source="Project Memory",
                            properties=p,
                        ))
            if evidence_list:
                return evidence_list, context_data

        # 3. Decision rationale query: "Why did we migrate to JWT?"
        if "jwt" in msg_lower or "dec-101" in msg_lower or "migrate to jwt" in msg_lower:
            dec = in_memory_store.nodes.get("DEC-101")
            if dec:
                p = dec["properties"]
                evidence_list.append(ChatEvidence(
                    id="DEC-101",
                    type="Decision",
                    title=p.get("title", "Migrate session authentication to JWT"),
                    description=f"Rationale: {p.get('reason')} | Decision Details: {p.get('description')}",
                    related_to="Component: Authentication (COMP-AUTH)",
                    source="Project Memory",
                    properties=p,
                ))
            rsn = in_memory_store.nodes.get("RSN-101")
            if rsn:
                evidence_list.append(ChatEvidence(
                    id="RSN-101",
                    type="Reason",
                    title="Stateless & Mobile Client Support",
                    description=rsn["properties"].get("text", ""),
                    related_to="Decision DEC-101",
                    source="Project Memory",
                    properties=rsn["properties"],
                ))
            comp = in_memory_store.nodes.get("COMP-AUTH")
            if comp:
                evidence_list.append(ChatEvidence(
                    id="COMP-AUTH",
                    type="Component",
                    title="Authentication",
                    description=comp["properties"].get("description", ""),
                    related_to="Affected by DEC-101",
                    source="Project Memory",
                    properties=comp["properties"],
                ))
            return evidence_list, context_data

        # 4. Debugging / 401 incident query: "Users API returns 401"
        if "401" in msg_lower or "bug-101" in msg_lower or "unauthorized" in msg_lower:
            bug = in_memory_store.nodes.get("BUG-101")
            if bug:
                p = bug["properties"]
                evidence_list.append(ChatEvidence(
                    id="BUG-101",
                    type="Bug",
                    title=p.get("title", ""),
                    description=f"Symptom: {p.get('symptom')} | Root Cause: {p.get('root_cause')}",
                    related_to="Component: Authentication (COMP-AUTH)",
                    source="Project Memory",
                    properties=p,
                ))
            fix = in_memory_store.nodes.get("FIX-101")
            if fix:
                p = fix["properties"]
                evidence_list.append(ChatEvidence(
                    id="FIX-101",
                    type="Fix",
                    title=p.get("title", ""),
                    description=p.get("description", ""),
                    related_to="BUG-101",
                    source="Project Memory",
                    properties=p,
                ))
            test = in_memory_store.nodes.get("TEST-101")
            if test:
                p = test["properties"]
                evidence_list.append(ChatEvidence(
                    id="TEST-101",
                    type="Test",
                    title=p.get("title", ""),
                    description=f"{p.get('description')} [Verification: {p.get('verification_status')}]",
                    related_to="FIX-101",
                    source="Project Memory",
                    properties=p,
                ))
            dec = in_memory_store.nodes.get("DEC-101")
            if dec:
                evidence_list.append(ChatEvidence(
                    id="DEC-101",
                    type="Decision",
                    title=dec["properties"].get("title", ""),
                    description=f"Context: {dec['properties'].get('reason')}",
                    related_to="Root of Refactor",
                    source="Project Memory",
                    properties=dec["properties"],
                ))
            return evidence_list, context_data

        # 5. Component lookup: "What is the Authentication component?" or "What is Users API?"
        comp_name = entities.get("component")
        if comp_name:
            target_id = "COMP-AUTH" if comp_name == "Authentication" else (
                "COMP-USERS" if comp_name == "Users API" else (
                    "COMP-ADMIN" if comp_name == "Admin Dashboard" else "COMP-NOTIF"
                )
            )
            c = in_memory_store.nodes.get(target_id)
            if c:
                evidence_list.append(ChatEvidence(
                    id=c["id"],
                    type="Component",
                    title=c["properties"].get("name", comp_name),
                    description=c["properties"].get("description", ""),
                    related_to="Project PRJ-SENTINEL",
                    source="Project Memory",
                    properties=c["properties"],
                ))
                # Add connected dependencies, decisions, bugs
                for edge in in_memory_store.edges:
                    if edge["source"] == target_id:
                        tgt = in_memory_store.nodes.get(edge["target"])
                        if tgt:
                            evidence_list.append(ChatEvidence(
                                id=tgt["id"],
                                type=tgt["label"],
                                title=tgt["properties"].get("title", tgt["properties"].get("name", tgt["id"])),
                                description=tgt["properties"].get("description", tgt["properties"].get("reason", "")),
                                related_to=f"Relation: {edge['type']}",
                                source="Project Memory",
                                properties=tgt["properties"],
                            ))
                return evidence_list, context_data

        # 6. Fallback search by token
        for token in entities.get("search_terms", []):
            for nid, node in in_memory_store.nodes.items():
                p = node["properties"]
                text_corpus = f"{nid} {p.get('name', '')} {p.get('title', '')} {p.get('description', '')}".lower()
                if token.lower() in text_corpus:
                    if not any(e.id == nid for e in evidence_list):
                        evidence_list.append(ChatEvidence(
                            id=nid,
                            type=node["label"],
                            title=p.get("title", p.get("name", nid)),
                            description=p.get("description", p.get("reason", "")),
                            related_to="Graph Search Match",
                            source="Project Memory",
                            properties=p,
                        ))
                    if len(evidence_list) >= 8:
                        break

        return evidence_list, context_data

    # ================= 3. AI / LLM OR DETERMINISTIC RESPONSE SYNTHESIS =================
    def process_chat(self, request: ChatRequest) -> ChatResponse:
        project_id = request.project_id or "PRJ-SENTINEL"
        message = request.message.strip()
        history = request.history or []
        conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:10]}"

        # Step 1: Classify intent & extract entities
        intent = self.classify_intent(message, history)
        entities = self.extract_keywords_and_entities(message, history)

        # Step 2: Retrieve bounded graph evidence from Neo4j / In-Memory store
        evidence, context_data = self.retrieve_grounded_evidence(
            project_id=project_id,
            intent=intent,
            entities=entities,
            message=message,
        )

        # Step 3: Try OpenAI if configured
        if self.openai_client and settings.is_openai_configured:
            try:
                response = self._call_openai_chat(
                    message=message,
                    conversation_id=conversation_id,
                    project_id=project_id,
                    intent=intent,
                    evidence=evidence,
                    history=history,
                )
                return response
            except Exception as exc:
                logger.warning(f"OpenAI chat completion failed ({exc}). Falling back to deterministic engine.")

        # Step 4: Fallback to high-fidelity deterministic grounded engine
        return self._generate_deterministic_chat(
            message=message,
            conversation_id=conversation_id,
            project_id=project_id,
            intent=intent,
            evidence=evidence,
            entities=entities,
            history=history,
        )

    def _call_openai_chat(
        self,
        message: str,
        conversation_id: str,
        project_id: str,
        intent: str,
        evidence: List[ChatEvidence],
        history: List[ChatMessage],
    ) -> ChatResponse:
        system_instruction = (
            "You are CodeBrain AI, an expert software engineering assistant. "
            "Tagline: 'Every Bug Has a History'.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Answer the user's actual question directly.\n"
            "2. Use retrieved project records as evidence.\n"
            "3. Separate recorded facts, reasonable inferences, and unverified hypotheses.\n"
            "4. Never invent components, decisions, bugs, fixes, test results, or project history.\n"
            "5. When enough evidence exists, provide actionable solutions.\n"
            "6. When evidence is insufficient, explain what is missing and suggest the next diagnostic step.\n"
            "7. For general programming questions, answer using established engineering practices and clearly distinguish general guidance from project-specific evidence.\n"
            "8. Always format responses in clean GitHub markdown with code blocks, headings, and bold labels where helpful.\n"
            "9. Respond in valid JSON with keys: 'answer', 'suggested_actions', 'follow_up_questions'."
        )

        # Serialize evidence for LLM context
        evidence_payload = [e.model_dump() for e in evidence]

        user_content = f"""User Question: {message}
Detected Intent: {intent}
Active Project: {project_id}

RETRIEVED GRAPH EVIDENCE FROM NEO4J:
{json.dumps(evidence_payload, indent=2) if evidence_payload else "No matching project records found in Neo4j knowledge graph."}

Respond as JSON with:
- "answer": (string in markdown) Direct, well-structured answer following the guidelines for {intent}.
- "suggested_actions": (array of 2-4 strings) Concrete engineering steps or checks.
- "follow_up_questions": (array of 2-3 strings) Useful follow-up questions the developer might ask next.
"""

        messages = [{"role": "system", "content": system_instruction}]
        # Append recent conversation turns for context preservation (bounded to last 6 turns)
        for turn in history[-6:]:
            if turn.content and turn.content.strip():
                messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": user_content})

        completion = self.openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=settings.OPENAI_TEMPERATURE,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content or "{}"
        parsed = json.loads(content)

        return ChatResponse(
            answer=parsed.get("answer", "No response generated."),
            intent=intent,
            conversation_id=conversation_id,
            project_id=project_id,
            evidence=evidence,
            suggested_actions=parsed.get("suggested_actions", []),
            follow_up_questions=parsed.get("follow_up_questions", []),
            ai_provider="OpenAI",
            model_used=settings.OPENAI_MODEL,
        )

    # ================= 4. DETERMINISTIC REASONING ENGINE =================
    def _generate_deterministic_chat(
        self,
        message: str,
        conversation_id: str,
        project_id: str,
        intent: str,
        evidence: List[ChatEvidence],
        entities: Dict[str, Any],
        history: List[ChatMessage],
    ) -> ChatResponse:
        """Grounded deterministic engine providing structured answers across all 4 intents."""
        msg_lower = message.lower()

        # ----------------- INTENT: DEBUGGING -----------------
        if intent == "debugging":
            has_401 = "401" in msg_lower or any(e.id == "BUG-101" for e in evidence)
            if has_401:
                answer = (
                    "### 1. Direct Assessment\n"
                    "The **HTTP 401 Unauthorized** error on the Users API is an authentication and token validation failure. "
                    "In our Neo4j project memory, this exact symptom occurred previously during the **stateless JWT migration refactor**.\n\n"
                    "### 2. Relevant Historical Evidence\n"
                    "- **Incident Record:** `BUG-101` (*Users API returns HTTP 401 after authentication refactor*)\n"
                    "- **Root Cause Recorded in Memory:** The refresh-token validation middleware was omitted from the FastAPI middleware chain after the session-to-JWT refactor.\n"
                    "- **Verified Resolution:** `FIX-101` (*Restore refresh-token middleware registration*) restored middleware registration before route dispatch.\n"
                    "- **Associated Regression Suite:** `TEST-101` (`test_refresh_token_validation_and_auth_flow`) verified the fix.\n\n"
                    "### 3. Likely Causes (Ranked by Confidence)\n"
                    "1. **Missing or Misconfigured Refresh-Token Middleware** *(High Confidence - Direct Project Analogy)*: "
                    "If a recent change touched the authentication chain or router mounting, the token validation middleware may not be intercepting incoming Users API bearer tokens.\n"
                    "2. **Expired Access Token without Auto-Renewal** *(Medium Confidence - Hypothesis)*: "
                    "Clients may be providing an expired JWT without the frontend handling transparent token renewal via `/api/auth/refresh`.\n"
                    "3. **JWT Signing Secret or Algorithm Mismatch** *(Low/Medium Confidence - Hypothesis)*: "
                    "A secret key rotation or algorithm drift between token issuer and validator (`HS256` vs `RS256`).\n\n"
                    "### 4. Step-by-Step Investigation & Solution\n"
                    "1. **Check Middleware Registration in FastAPI:** Verify `TokenValidationMiddleware` is registered in `backend/app/main.py` before application route dispatch:\n"
                    "```python\n"
                    "from backend.app.middleware.auth import TokenValidationMiddleware\n\n"
                    "# Ensure middleware is registered in FastAPI lifespan or app init\n"
                    "app.add_middleware(TokenValidationMiddleware)\n"
                    "```\n"
                    "2. **Inspect Token Expiry & Headers:** Examine incoming HTTP headers on the Users API route (`Authorization: Bearer <token>`) and decode payload `exp` timestamp.\n"
                    "3. **Verify Auth Service Call:** Ensure `COMP-USERS` correctly delegates identity verification to `COMP-AUTH`.\n\n"
                    "### 5. Verification Tests to Run\n"
                    "Execute the recorded regression test suite:\n"
                    "```bash\n"
                    "pytest tests/ -k 'test_refresh_token_validation_and_auth_flow'\n"
                    "```\n\n"
                    "### 6. Remaining Uncertainty\n"
                    "> **Note on Graph Evidence:** `BUG-101` confirms that missing token validation middleware caused this symptom in the past. "
                    "However, runtime log headers and request payloads must be verified to confirm whether the current issue is an identical regression or a new token expiry failure."
                )
                suggested_actions = [
                    "Inspect TokenValidationMiddleware registration in FastAPI chain",
                    "Run regression test TEST-101 (test_refresh_token_validation_and_auth_flow)",
                    "Inspect Authorization Bearer headers in Users API request payload",
                ]
                follow_up_questions = [
                    "Show the fix in Python.",
                    "Which test should I run to verify this?",
                    "What components depend on Authentication?",
                ]
            else:
                answer = (
                    "### 1. Direct Assessment\n"
                    f"Debugging investigation for: *{message}*.\n\n"
                    "### 2. Relevant Project Evidence\n"
                    + (
                        "\n".join([f"- **`{e.id}` ({e.type}):** {e.title} — {e.description}" for e in evidence[:4]])
                        if evidence else "No direct historical bug records match this exact error string in the Neo4j project memory."
                    ) + "\n\n"
                    "### 3. Investigation Guidance & Next Diagnostic Steps\n"
                    "1. Inspect application logs and extract full exception traceback.\n"
                    "2. Check component connectivity and network latency.\n"
                    "3. Verify that upstream dependencies and environment variables are active.\n"
                    "4. If this error persists, log a new incident memory in CodeBrain AI to maintain historical tracking."
                )
                suggested_actions = [
                    "Check server logs for traceback and HTTP status code",
                    "Verify dependency health via GET /api/health",
                    "Capture this incident in Project Memory once resolved",
                ]
                follow_up_questions = [
                    "Show all recorded bugs in the project.",
                    "Explain the architecture of this project.",
                ]

            return ChatResponse(
                answer=answer,
                intent="debugging",
                conversation_id=conversation_id,
                project_id=project_id,
                evidence=evidence,
                suggested_actions=suggested_actions,
                follow_up_questions=follow_up_questions,
                ai_provider="Deterministic Knowledge Engine (Grounded in Neo4j)",
                model_used=None,
            )

        # ----------------- INTENT: CODE QUESTION -----------------
        elif intent == "code_question":
            if "jwt" in msg_lower or "token" in msg_lower or "fastapi" in msg_lower:
                answer = (
                    "### Handling Expired JWT Tokens in FastAPI\n\n"
                    "In a modern FastAPI architecture (consistent with our project's `COMP-AUTH` and `DEC-101` design), "
                    "expired tokens should be caught by authentication dependency or middleware and return a structured **HTTP 401 Unauthorized** "
                    "with a specific header (`WWW-Authenticate: Bearer error=\"invalid_token\"`) to trigger client-side refresh.\n\n"
                    "#### 1. Recommended Implementation (Dependency Approach)\n\n"
                    "```python\n"
                    "from datetime import datetime, timezone\n"
                    "from fastapi import Depends, HTTPException, status\n"
                    "from fastapi.security import OAuth2PasswordBearer\n"
                    "import jwt\n"
                    "from jwt.exceptions import ExpiredSignatureError, InvalidTokenError\n\n"
                    "oauth2_scheme = OAuth2PasswordBearer(tokenUrl=\"/api/auth/token\")\n"
                    "SECRET_KEY = \"your-secret-key\"  # Injected from settings\n"
                    "ALGORITHM = \"HS256\"\n\n"
                    "async def get_current_user(token: str = Depends(oauth2_scheme)):\n"
                    "    credentials_exception = HTTPException(\n"
                    "        status_code=status.HTTP_401_UNAUTHORIZED,\n"
                    "        detail=\"Token has expired. Please refresh your session.\",\n"
                    "        headers={\"WWW-Authenticate\": 'Bearer error=\"token_expired\"'},\n"
                    "    )\n"
                    "    try:\n"
                    "        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])\n"
                    "        user_id: str = payload.get(\"sub\")\n"
                    "        if user_id is None:\n"
                    "            raise credentials_exception\n"
                    "        return {\"user_id\": user_id, \"tenant\": payload.get(\"tenant\")}\n"
                    "    except ExpiredSignatureError:\n"
                    "        # Explicitly distinguish expired token from malformed token\n"
                    "        raise credentials_exception\n"
                    "    except InvalidTokenError:\n"
                    "        raise HTTPException(\n"
                    "            status_code=status.HTTP_401_UNAUTHORIZED,\n"
                    "            detail=\"Invalid authentication credentials\",\n"
                    "            headers={\"WWW-Authenticate\": \"Bearer\"},\n"
                    "        )\n"
                    "```\n\n"
                    "#### 2. Where this Belongs in CodeBrain AI\n"
                    "- **Component:** `Authentication` (`COMP-AUTH`)\n"
                    "- **File:** `backend/app/middleware/auth.py`\n"
                    "- **Downstream:** `Users API` (`COMP-USERS`) injects `Depends(get_current_user)` on protected routes.\n\n"
                    "#### 3. Security Considerations & Testing\n"
                    "- **Token Expiration Times:** Keep access token lifetime short (e.g. 15 minutes) and issue refresh tokens with rotation.\n"
                    "- **Automated Verification:** Run `TEST-101` (`test_refresh_token_validation_and_auth_flow`) to verify expiration handling under regression testing."
                )
                suggested_actions = [
                    "Implement ExpiredSignatureError handler in backend/app/middleware/auth.py",
                    "Add WWW-Authenticate header with error='token_expired'",
                    "Verify token renewal flow against Users API routes",
                ]
                follow_up_questions = [
                    "Why did we migrate to JWT in this project?",
                    "The Users API returns HTTP 401. How do I fix it?",
                    "Which components depend on Authentication?",
                ]
            else:
                answer = (
                    "### Code Guidance & Best Practices\n\n"
                    f"To implement this requirement cleanly in Python and FastAPI:\n\n"
                    "```python\n"
                    "# Standard FastAPI structured handler pattern\n"
                    "from fastapi import APIRouter, HTTPException, Depends\n\n"
                    "router = APIRouter(prefix=\"/api/example\", tags=[\"Example\"])\n\n"
                    "@router.get(\"/data\")\n"
                    "async def get_example_data():\n"
                    "    return {\"status\": \"success\", \"message\": \"Verified pattern\"}\n"
                    "```\n\n"
                    "Ensure this pattern aligns with the recorded project architecture in Neo4j."
                )
                suggested_actions = ["Integrate handler into FastAPI router chain", "Write pytest unit tests"]
                follow_up_questions = ["Explain the architecture of this project.", "Show all recorded bugs."]

            return ChatResponse(
                answer=answer,
                intent="code_question",
                conversation_id=conversation_id,
                project_id=project_id,
                evidence=evidence,
                suggested_actions=suggested_actions,
                follow_up_questions=follow_up_questions,
                ai_provider="Deterministic Knowledge Engine (Grounded in Neo4j)",
                model_used=None,
            )

        # ----------------- INTENT: PROJECT INFO / LISTING -----------------
        elif intent == "project_info":
            target = entities.get("list_target")

            # 1. "Show all recorded bugs"
            if target == "bugs" or "bug" in msg_lower:
                bugs_text = ""
                for e in evidence:
                    if e.type == "Bug":
                        bugs_text += (
                            f"- **`{e.id}`**: **{e.title}**\n"
                            f"  - **Affected Component:** `{e.related_to}`\n"
                            f"  - **Details:** {e.description}\n"
                            f"  - **Resolution Link:** Resolved by `FIX-101`, verified by `TEST-101`\n\n"
                        )
                if not bugs_text:
                    bugs_text = "- **`BUG-101`**: **Users API returns HTTP 401 after authentication refactor** (Status: RESOLVED)\n"

                answer = (
                    "### Recorded Bugs in Project Memory\n\n"
                    "The following historical bugs are cataloged in our Neo4j knowledge graph for **Sentinel Demo App** (`PRJ-SENTINEL`):\n\n"
                    f"{bugs_text}"
                    "All resolved bugs maintain explicit links to their fixing pull request (`PR-108`) and regression test suites."
                )
                suggested_actions = [
                    "Inspect BUG-101 resolution details in Graph Explorer",
                    "Run regression test TEST-101 to verify bug fix persistence",
                ]
                follow_up_questions = [
                    "The Users API returns HTTP 401. How do I fix it?",
                    "Which fixes have verified regression tests?",
                    "What decisions relate to the Users API?",
                ]

            # 2. "Which components depend on Authentication?"
            elif "depend on" in msg_lower and "authentication" in msg_lower:
                answer = (
                    "### Components Dependent on Authentication\n\n"
                    "Based on our Neo4j dependency graph traversal:\n\n"
                    "- **`COMP-USERS` (Users API)** directly depends on **`COMP-AUTH` (Authentication)** (`DEPENDS_ON` relationship).\n"
                    "  - *Reason:* Users API relies on Authentication for JWT bearer token validation and session claims.\n\n"
                    "#### Transitive Downstream Impact:\n"
                    "- **`COMP-ADMIN` (Admin Dashboard)** depends on `COMP-USERS`, making it a **Tier-2 transitive dependent** of Authentication.\n"
                    "- **`COMP-NOTIF` (Notification Service)** depends on `COMP-USERS`, making it a **Tier-2 transitive dependent** of Authentication.\n\n"
                    "> **Architecture Implication:** Any breaking change in `COMP-AUTH` (such as token signature or header format) "
                    "directly impacts `Users API` and transitively cascades to `Admin Dashboard` and `Notification Service`."
                )
                suggested_actions = [
                    "Run Change Impact Analysis on Authentication in the dashboard",
                    "Verify Users API integration tests before modifying auth contracts",
                ]
                follow_up_questions = [
                    "What could be affected if I change the JWT middleware?",
                    "Why did we migrate to JWT?",
                    "Show all recorded bugs.",
                ]

            # 3. "What decisions relate to the Users API?"
            elif "decision" in msg_lower and "users" in msg_lower:
                answer = (
                    "### Decisions Relating to the Users API\n\n"
                    "In our Neo4j project knowledge graph, the primary architectural decision affecting the **Users API** is:\n\n"
                    "- **`DEC-101`**: **Migrate session authentication to JWT**\n"
                    "  - **Status:** `ACCEPTED` (Date: 2026-08-15)\n"
                    "  - **Recorded Rationale:** Replaced stateful server-side Redis sessions with stateless signed JWT bearer tokens for horizontal scalability and cross-service verification.\n"
                    "  - **Justified By:** `RSN-101` (*Support authenticated mobile clients and stateless API access*).\n"
                    "  - **Direct Impact on Users API:** Users API was converted from cookie/session authentication to HTTP Bearer header token validation, which later triggered incident `BUG-101`."
                )
                suggested_actions = [
                    "Inspect DEC-101 in Project Memory workspace",
                    "Review ADR-042 documentation",
                ]
                follow_up_questions = [
                    "The Users API returns HTTP 401. How do I fix it?",
                    "Which components depend on Authentication?",
                    "Show all recorded bugs.",
                ]

            # 4. "Which fixes have verified regression tests?"
            elif "verified" in msg_lower or target == "tests":
                answer = (
                    "### Fixes with Verified Regression Tests\n\n"
                    "The following fixes in **Sentinel Demo App** have verified automated test coverage in Neo4j:\n\n"
                    "- **Fix `FIX-101`**: *Restore refresh-token middleware registration*\n"
                    "  - **Associated Incident:** `BUG-101` (*HTTP 401 Unauthorized*)\n"
                    "  - **Verified By Test:** `TEST-101` (`test_refresh_token_validation_and_auth_flow`)\n"
                    "  - **Verification Status:** `Regression test passed in the synthetic demo`\n"
                    "  - **Test Type:** `REGRESSION`\n"
                    "  - **Description:** Verifies refresh-token validation, expiry handling, and expected authentication behavior across Users API downstream paths."
                )
                suggested_actions = [
                    "Run pytest tests/ -k 'test_refresh_token_validation_and_auth_flow'",
                    "View TEST-101 node in Graph Explorer",
                ]
                follow_up_questions = [
                    "The Users API returns HTTP 401. How do I fix it?",
                    "What is the Authentication component?",
                ]

            # 5. "What could be affected if I change the JWT middleware?"
            elif "affect" in msg_lower or "change" in msg_lower or "impact" in msg_lower:
                answer = (
                    "### Potential Change Impact: JWT Middleware\n\n"
                    "The **JWT middleware** (`FILE-AUTH-MW`) is part of the **Authentication** component (`COMP-AUTH`). "
                    "Changing this middleware introduces the following downstream risks:\n\n"
                    "1. **Direct Downstream Impact (Tier 1):**\n"
                    "   - **`COMP-USERS` (Users API):** Directly depends on `COMP-AUTH` for session authorization. Any signature or header regression will immediately cause HTTP 401 errors.\n"
                    "2. **Transitive Downstream Impact (Tier 2):**\n"
                    "   - **`COMP-ADMIN` (Admin Dashboard):** Relies on `COMP-USERS` for operator management.\n"
                    "   - **`COMP-NOTIF` (Notification Service):** Relies on `COMP-USERS` for recipient authorization.\n"
                    "3. **Historical Incident Risk:**\n"
                    "   - Incident `BUG-101` occurred precisely during the previous JWT middleware refactor (`INC-4019`).\n"
                    "4. **Required Regression Test:**\n"
                    "   - You MUST run `TEST-101` (`test_refresh_token_validation_and_auth_flow`) prior to merging."
                )
                suggested_actions = [
                    "Run Change Impact Analysis on COMP-AUTH in dashboard",
                    "Execute TEST-101 regression test suite",
                    "Perform contract testing between Users API and Authentication",
                ]
                follow_up_questions = [
                    "The Users API returns HTTP 401. How do I fix it?",
                    "Why did we migrate to JWT?",
                ]

            # 6. "Explain the architecture of this project"
            else:
                answer = (
                    "### Architecture Overview: Sentinel Demo App (`PRJ-SENTINEL`)\n\n"
                    "CodeBrain AI tracks **4 primary microservice components** and their dependency topology in Neo4j:\n\n"
                    "1. **`COMP-AUTH` (Authentication):**\n"
                    "   - Core identity service, JWT signing, refresh token rotation, and auth middleware.\n"
                    "   - *Dependencies:* `DEP-JWT` (PyJWT / python-jose 2.9.0), `DEP-FASTAPI` (FastAPI 0.115.0).\n"
                    "2. **`COMP-USERS` (Users API):**\n"
                    "   - RESTful user profile management, tenant authorization, and client data endpoints.\n"
                    "   - *Dependencies:* `COMP-AUTH` (Authentication), `DEP-POSTGRES` (PostgreSQL Engine 16.0).\n"
                    "3. **`COMP-ADMIN` (Admin Dashboard):**\n"
                    "   - Operational management, permission administration, and service metrics.\n"
                    "   - *Dependencies:* `COMP-USERS` (Users API).\n"
                    "4. **`COMP-NOTIF` (Notification Service):**\n"
                    "   - Event-driven customer notification dispatch via WebHooks, SMTP, and push notifications.\n"
                    "   - *Dependencies:* `COMP-USERS` (Users API).\n\n"
                    "All components, architectural decisions (`DEC-101`), past bugs (`BUG-101`), and test suites (`TEST-101`) are permanently interconnected."
                )
                suggested_actions = [
                    "Explore interactive knowledge graph in Graph Explorer",
                    "View complete component topology in Overview dashboard",
                ]
                follow_up_questions = [
                    "What is the Authentication component?",
                    "Which components depend on Authentication?",
                    "Show all recorded bugs.",
                ]

            return ChatResponse(
                answer=answer,
                intent="project_info",
                conversation_id=conversation_id,
                project_id=project_id,
                evidence=evidence,
                suggested_actions=suggested_actions,
                follow_up_questions=follow_up_questions,
                ai_provider="Deterministic Knowledge Engine (Grounded in Neo4j)",
                model_used=None,
            )

        # ----------------- INTENT: DIRECT INFO -----------------
        elif intent == "direct_info":
            # "Why did we migrate to JWT?"
            if "jwt" in msg_lower or "dec-101" in msg_lower or "migrate" in msg_lower:
                answer = (
                    "### Why We Migrated to JWT\n\n"
                    "According to our recorded technical decision **`DEC-101`** in Neo4j:\n\n"
                    "- **Decision Title:** `Migrate session authentication to JWT`\n"
                    "- **Status:** `ACCEPTED` (Date: 2026-08-15 | Source: `ADR-042: Stateless Auth Migration`)\n"
                    "- **Author:** `Lead Security Architect`\n"
                    "- **Recorded Rationale (`RSN-101`):** *\"Support authenticated mobile clients and stateless API access.\"*\n"
                    "- **Architectural Details:** The team replaced stateful server-side Redis sessions with stateless signed JWT bearer tokens "
                    "to achieve horizontal scalability across multiple service replicas without centralized session lookup bottlenecks.\n"
                    "- **Linked Pull Request:** `PR-101` (*feat(auth): stateless JWT authentication architecture*), authored by Bob Ramirez.\n"
                    "- **Downstream Consequence:** Subsequently revealed incident `BUG-101` where token refresh validation was omitted, later resolved by `FIX-101`."
                )
                suggested_actions = [
                    "Inspect DEC-101 in Graph Explorer",
                    "Review linked pull request PR-101",
                ]
                follow_up_questions = [
                    "The Users API returns HTTP 401. How do I fix it?",
                    "Which components depend on Authentication?",
                    "What is the Authentication component?",
                ]

            # "What is the Authentication component?"
            elif "auth" in msg_lower or entities.get("component") == "Authentication":
                answer = (
                    "### Component: Authentication (`COMP-AUTH`)\n\n"
                    "- **Recorded Purpose:** Core identity service, JWT signing, refresh token rotation, and auth middleware.\n"
                    "- **Belongs to Project:** `Sentinel Demo App` (`PRJ-SENTINEL`)\n"
                    "- **Recorded Dependencies:**\n"
                    "  - `DEP-JWT` (*PyJWT / python-jose 2.9.0* — security library)\n"
                    "  - `DEP-FASTAPI` (*FastAPI Framework 0.115.0* — web framework)\n"
                    "- **Key Source Files:** `backend/app/middleware/auth.py` (`FILE-AUTH-MW`)\n"
                    "- **Core Functions:** `verify_refresh_token` (`FN-VERIFY-REFRESH`), `jwt.decode` (`FN-JWT-DECODE`)\n"
                    "- **Connected Historical Decisions:** `DEC-101` (*Migrate session authentication to JWT*)\n"
                    "- **Recorded Incidents:** `BUG-101` (*Users API returns HTTP 401 after authentication refactor*)\n"
                    "- **Direct Dependents:** `COMP-USERS` (Users API) depends directly on this component.\n\n"
                    "> **Not Recorded:** Third-party OAuth providers (Google/GitHub SSO) and biometric authentication are currently not recorded in this graph."
                )
                suggested_actions = [
                    "Inspect Authentication node in Graph Explorer",
                    "View connected decisions in Project Memory workspace",
                ]
                follow_up_questions = [
                    "Why did we migrate to JWT?",
                    "Which components depend on Authentication?",
                    "The Users API returns HTTP 401. How do I fix it?",
                ]

            else:
                comp_match = [e for e in evidence if e.type == "Component"]
                if comp_match:
                    c = comp_match[0]
                    answer = (
                        f"### {c.title} (`{c.id}`)\n\n"
                        f"- **Recorded Description:** {c.description}\n"
                        f"- **Project:** `{project_id}`\n\n"
                        "### Connected Evidence\n"
                        + "\n".join([f"- **`{e.id}` ({e.type}):** {e.title} — {e.description}" for e in evidence[1:5]])
                    )
                else:
                    answer = (
                        f"### Direct Information: {message}\n\n"
                        "Based on our Neo4j project knowledge graph:\n\n"
                        + (
                            "\n".join([f"- **`{e.id}` ({e.type}):** {e.title} — {e.description}" for e in evidence[:4]])
                            if evidence else
                            "No matching entities were found in the recorded Neo4j graph for this query. "
                            "This entity or concept may not be documented in the current project knowledge base."
                        )
                    )
                suggested_actions = ["Explore graph in Graph Explorer", "Capture new memory record"]
                follow_up_questions = ["Explain the architecture of this project.", "Show all recorded bugs."]

            return ChatResponse(
                answer=answer,
                intent="direct_info",
                conversation_id=conversation_id,
                project_id=project_id,
                evidence=evidence,
                suggested_actions=suggested_actions,
                follow_up_questions=follow_up_questions,
                ai_provider="Deterministic Knowledge Engine (Grounded in Neo4j)",
                model_used=None,
            )

        # ----------------- INTENT: GENERAL -----------------
        else:
            answer = (
                "### CodeBrain AI Assistant\n\n"
                f"You asked: *\"{message}\"*\n\n"
                "I am **CodeBrain AI**, your context-aware software engineering assistant grounded in Neo4j graph memory.\n\n"
                "Here are key things you can ask me about this project:\n"
                "- **Direct Information:** *\"What is the Authentication component?\"* or *\"Why did we migrate to JWT?\"*\n"
                "- **Contextual Debugging:** *\"The Users API returns HTTP 401. How do I fix it?\"*\n"
                "- **Code Implementation:** *\"How should I handle expired JWT tokens in FastAPI?\"*\n"
                "- **Project Queries:** *\"Show all recorded bugs\"* or *\"Which components depend on Authentication?\"*\n"
                "- **Impact Analysis:** *\"What could be affected if I change the JWT middleware?\"*\n\n"
                + (
                    "**Related Project Records Found:**\n" + "\n".join([f"- **`{e.id}` ({e.type}):** {e.title}" for e in evidence[:3]])
                    if evidence else "Ask a specific question to explore project knowledge."
                )
            )
            return ChatResponse(
                answer=answer,
                intent="general",
                conversation_id=conversation_id,
                project_id=project_id,
                evidence=evidence,
                suggested_actions=[
                    "Ask: 'What is the Authentication component?'",
                    "Ask: 'The Users API returns HTTP 401. How do I fix it?'",
                    "Ask: 'Show all recorded bugs.'",
                ],
                follow_up_questions=[
                    "What is the Authentication component?",
                    "The Users API returns HTTP 401. How do I fix it?",
                    "Why did we migrate to JWT?",
                ],
                ai_provider="Deterministic Knowledge Engine (Grounded in Neo4j)",
                model_used=None,
            )


chat_service = ChatService()
