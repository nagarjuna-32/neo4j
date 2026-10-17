// DevGraph Sentinel — Neo4j Schema Constraints and Indexes
// Version: 2.0.0 (Phase 2 Knowledge Graph)
// Enforce uniqueness constraints across all 11 core entity types

CREATE CONSTRAINT project_id_unique IF NOT EXISTS
FOR (p:Project) REQUIRE p.id IS UNIQUE;

CREATE CONSTRAINT component_id_unique IF NOT EXISTS
FOR (c:Component) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT dependency_id_unique IF NOT EXISTS
FOR (dep:Dependency) REQUIRE dep.id IS UNIQUE;

CREATE CONSTRAINT decision_id_unique IF NOT EXISTS
FOR (d:Decision) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT reason_id_unique IF NOT EXISTS
FOR (r:Reason) REQUIRE r.id IS UNIQUE;

CREATE CONSTRAINT bug_id_unique IF NOT EXISTS
FOR (b:Bug) REQUIRE b.id IS UNIQUE;

CREATE CONSTRAINT fix_id_unique IF NOT EXISTS
FOR (f:Fix) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT test_id_unique IF NOT EXISTS
FOR (t:Test) REQUIRE t.id IS UNIQUE;

CREATE CONSTRAINT file_id_unique IF NOT EXISTS
FOR (f:File) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT function_id_unique IF NOT EXISTS
FOR (fn:Function) REQUIRE fn.id IS UNIQUE;

CREATE CONSTRAINT pull_request_id_unique IF NOT EXISTS
FOR (pr:PullRequest) REQUIRE pr.id IS UNIQUE;

CREATE CONSTRAINT developer_id_unique IF NOT EXISTS
FOR (dev:Developer) REQUIRE dev.id IS UNIQUE;

// Performance Indexes for Project Scoping and Filter Lookups
CREATE INDEX project_component_idx IF NOT EXISTS
FOR (c:Component) ON (c.project_id);

CREATE INDEX project_decision_idx IF NOT EXISTS
FOR (d:Decision) ON (d.project_id);

CREATE INDEX project_bug_idx IF NOT EXISTS
FOR (b:Bug) ON (b.project_id);

CREATE INDEX project_file_idx IF NOT EXISTS
FOR (f:File) ON (f.project_id);

CREATE INDEX project_fn_idx IF NOT EXISTS
FOR (fn:Function) ON (fn.project_id);

CREATE INDEX bug_status_idx IF NOT EXISTS
FOR (b:Bug) ON (b.status);
