from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# --- Health & Diagnostics ---
class HealthResponse(BaseModel):
    api_status: str = "healthy"
    neo4j_status: str
    neo4j_connected: bool
    ai_status: str
    ai_configured: bool
    ai_model: str
    storage_backend: str
    version: str
    diagnostics: List[str] = []


# --- Graph Data Representation ---
class GraphNode(BaseModel):
    id: str
    label: str
    labels: List[str] = []
    properties: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}


class GraphResponse(BaseModel):
    project_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, int] = {}


class ProjectSummary(BaseModel):
    id: str
    name: str
    description: str
    is_synthetic: bool = True
    node_count: int = 0
    edge_count: int = 0


# --- Project Memory Capture ---
class MemoryCaptureRequest(BaseModel):
    memory_type: Literal["decision", "bug"] = Field(
        ..., description="'decision' or 'bug'"
    )
    project_id: str = Field(default="PRJ-SENTINEL", description="Target project ID")
    title: str = Field(..., min_length=3, max_length=250)
    affected_component: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(default="", max_length=2000)

    # Decision-specific fields
    reason: Optional[str] = Field(default=None, max_length=1000)
    dependency: Optional[str] = Field(default=None, max_length=100)
    author: Optional[str] = Field(default="Engineering Team", max_length=150)

    # Bug-specific fields
    symptom: Optional[str] = Field(default=None, max_length=1000)
    root_cause: Optional[str] = Field(default=None, max_length=1000)
    resolution: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(default="RESOLVED", max_length=50)
    verification: Optional[str] = Field(default=None, max_length=1000)

    source: Optional[str] = Field(default="Manual Input", max_length=200)


class MemoryCaptureResponse(BaseModel):
    success: bool
    message: str
    entity_id: str
    entity_type: str
    connected_paths: List[str] = []


# --- Contextual Debugging Analysis ---
class AnalyzeRequest(BaseModel):
    project_id: str = Field(default="PRJ-SENTINEL")
    question: str = Field(..., min_length=5, max_length=1000)
    component: Optional[str] = Field(default=None, max_length=150)


class EvidenceRecord(BaseModel):
    id: str
    type: str
    title: str
    details: Dict[str, Any]
    relation: str


class AnalyzeResponse(BaseModel):
    question: str
    answer: str
    assessment: str
    relevant_evidence: List[EvidenceRecord] = []
    evidence_paths: List[str] = []
    connected_decisions: List[str] = []
    historical_bugs: List[str] = []
    potential_root_causes: List[str] = []
    suggested_checks: List[str] = []
    suggested_tests: List[str] = []
    evidence_limitations: str
    confidence_explanation: str
    source: str
    project_id: str
    detected_component: Optional[str] = None


# --- Change Impact Analysis ---
class ImpactRequest(BaseModel):
    project_id: str = Field(default="PRJ-SENTINEL", description="Project ID")
    changed_components: Optional[List[str]] = Field(
        default=[], description="List of component names or IDs"
    )
    changed_files: Optional[List[str]] = Field(
        default=[], description="List of modified file paths"
    )


class AffectedComponent(BaseModel):
    id: str
    name: str
    tier: Literal["direct", "downstream_1", "downstream_2", "transitive", "unresolved"]
    reason: str
    path: List[str]
    status_label: str = "potential_impact"


class ImpactResponse(BaseModel):
    project_id: str
    directly_changed: List[str]
    unresolved_inputs: List[str] = []
    affected_components: List[AffectedComponent]
    historical_risks: List[Dict[str, Any]] = []
    technical_decisions: List[Dict[str, Any]] = []
    suggested_tests: List[Dict[str, Any]] = []
    graph_paths: List[List[str]] = []
    heuristic_priority: Literal["HIGH", "MEDIUM", "LOW"]
    priority_reasons: List[str] = []
    explanations: List[str] = []
    disclaimer: str = (
        "All downstream findings represent potential impacts based on graph topology. "
        "Review priorities are heuristic-based and must be validated through code inspection and regression testing."
    )


# --- Activity Log ---
class ActivityEvent(BaseModel):
    id: str
    timestamp: str
    event_type: str
    title: str
    entity_id: str
    component: str
    summary: str


# --- Context-Aware AI Chat Assistant ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Natural-language question or prompt")
    conversation_id: Optional[str] = Field(default=None, max_length=100, description="Optional conversation session ID")
    project_id: str = Field(default="PRJ-SENTINEL", max_length=100, description="Active project ID")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Previous conversation turns for context preservation")


class ChatEvidence(BaseModel):
    id: str
    type: str  # e.g. "Component", "Decision", "Bug", "Fix", "Test", "Dependency", "File", "Function"
    title: str
    description: Optional[str] = ""
    related_to: Optional[str] = None
    source: Literal["Project Memory", "General Engineering Guidance", "Hypothesis"] = "Project Memory"
    properties: Optional[Dict[str, Any]] = {}


class ChatResponse(BaseModel):
    answer: str
    intent: Literal["direct_info", "debugging", "code_question", "project_info", "general"]
    conversation_id: str
    project_id: str
    evidence: List[ChatEvidence] = []
    suggested_actions: List[str] = []
    follow_up_questions: List[str] = []
    ai_provider: str
    model_used: Optional[str] = None

