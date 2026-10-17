// DevGraph Sentinel — Synthetic Demo Graph Seed
// Project: Sentinel Demo App (PRJ-SENTINEL)
// Fully idempotent seed script using MERGE

// 1. Create Project
MERGE (p:Project {id: 'PRJ-SENTINEL'})
SET p.name = 'Sentinel Demo App',
    p.description = 'Cloud-native distributed enterprise service mesh with identity and telemetry',
    p.is_synthetic = true,
    p.source = 'Sentinel Synthetic Demo',
    p.updated_at = datetime();

// 2. Create Components
MERGE (cAuth:Component {id: 'COMP-AUTH'})
SET cAuth.name = 'Authentication',
    cAuth.description = 'Core identity service, JWT signing, refresh token rotation, and auth middleware',
    cAuth.project_id = 'PRJ-SENTINEL',
    cAuth.is_synthetic = true;

MERGE (cUsers:Component {id: 'COMP-USERS'})
SET cUsers.name = 'Users API',
    cUsers.description = 'RESTful user profile management, tenant authorization, and client data endpoints',
    cUsers.project_id = 'PRJ-SENTINEL',
    cUsers.is_synthetic = true;

MERGE (cAdmin:Component {id: 'COMP-ADMIN'})
SET cAdmin.name = 'Admin Dashboard',
    cAdmin.description = 'Internal operational management, user permission administration, and metrics',
    cAdmin.project_id = 'PRJ-SENTINEL',
    cAdmin.is_synthetic = true;

MERGE (cNotif:Component {id: 'COMP-NOTIF'})
SET cNotif.name = 'Notification Service',
    cNotif.description = 'Event-driven customer notification dispatch via WebHooks, SMTP, and push',
    cNotif.project_id = 'PRJ-SENTINEL',
    cNotif.is_synthetic = true;

// 3. Connect Project to Components
MERGE (p)-[:HAS_COMPONENT]->(cAuth)
MERGE (p)-[:HAS_COMPONENT]->(cUsers)
MERGE (p)-[:HAS_COMPONENT]->(cAdmin)
MERGE (p)-[:HAS_COMPONENT]->(cNotif);

// 4. Create External Dependencies
MERGE (dJwt:Dependency {id: 'DEP-JWT'})
SET dJwt.name = 'PyJWT / python-jose',
    dJwt.version = '2.9.0',
    dJwt.type = 'security-library',
    dJwt.is_synthetic = true;

MERGE (dFastAPI:Dependency {id: 'DEP-FASTAPI'})
SET dFastAPI.name = 'FastAPI Framework',
    dFastAPI.version = '0.115.0',
    dFastAPI.type = 'web-framework',
    dFastAPI.is_synthetic = true;

MERGE (dPostgres:Dependency {id: 'DEP-POSTGRES'})
SET dPostgres.name = 'PostgreSQL Engine',
    dPostgres.version = '16.0',
    dPostgres.type = 'relational-database',
    dPostgres.is_synthetic = true;

// 5. Connect Component-to-Dependency & Component-to-Component
MERGE (cAuth)-[:DEPENDS_ON]->(dJwt)
MERGE (cAuth)-[:DEPENDS_ON]->(dFastAPI)
MERGE (cUsers)-[:DEPENDS_ON]->(dPostgres)
MERGE (cUsers)-[:DEPENDS_ON]->(cAuth)
MERGE (cAdmin)-[:DEPENDS_ON]->(cUsers)
MERGE (cNotif)-[:DEPENDS_ON]->(cUsers);

// 6. Create Technical Decision: DEC-101
MERGE (dec101:Decision {id: 'DEC-101'})
SET dec101.title = 'Migrate session authentication to JWT',
    dec101.description = 'Replaced stateful server-side Redis sessions with stateless signed JWT bearer tokens for horizontal scalability and cross-service verification.',
    dec101.reason = 'Support authenticated mobile clients and stateless API access.',
    dec101.author = 'Lead Security Architect',
    dec101.date = '2026-08-15',
    dec101.status = 'ACCEPTED',
    dec101.source = 'ADR-042: Stateless Auth Migration',
    dec101.project_id = 'PRJ-SENTINEL',
    dec101.is_synthetic = true;

MERGE (rsn101:Reason {id: 'RSN-101'})
SET rsn101.text = 'Support authenticated mobile clients and stateless API access.',
    rsn101.is_synthetic = true;

MERGE (dec101)-[:JUSTIFIED_BY]->(rsn101);
MERGE (cAuth)-[:AFFECTED_BY]->(dec101);

// 7. Create Historical Bug: BUG-101
MERGE (bug101:Bug {id: 'BUG-101'})
SET bug101.title = 'Users API returns HTTP 401 after authentication refactor',
    bug101.symptom = 'Authenticated users receive unexpected 401 Unauthorized responses during legitimate session renewal.',
    bug101.root_cause = 'Refresh-token validation middleware was missing from the authentication route chain after the JWT refactor.',
    bug101.resolution = 'FIX-101 restores middleware registration and adds regression coverage.',
    bug101.status = 'RESOLVED',
    bug101.affected_component = 'Authentication',
    bug101.project_id = 'PRJ-SENTINEL',
    bug101.created_at = '2026-08-20T14:32:00Z',
    bug101.source = 'Incident INC-4019',
    bug101.is_synthetic = true;

MERGE (cAuth)-[:HAS_BUG]->(bug101);
MERGE (bug101)-[:RELATED_TO]->(dec101);

// 8. Create Fix: FIX-101
MERGE (fix101:Fix {id: 'FIX-101'})
SET fix101.title = 'Restore refresh-token middleware registration',
    fix101.description = 'Explicitly registered TokenValidationMiddleware before RouteDispatch in FastAPI lifespan and added token renewal handler.',
    fix101.changed_component = 'Authentication',
    fix101.associated_incident = 'BUG-101',
    fix101.status = 'VERIFIED',
    fix101.is_synthetic = true;

MERGE (bug101)-[:RESOLVED_BY]->(fix101);

// 9. Create Regression Test: TEST-101
MERGE (test101:Test {id: 'TEST-101'})
SET test101.title = 'test_refresh_token_validation_and_auth_flow',
    test101.description = 'Verifies refresh-token validation, expiry handling, and expected authentication behavior across Users API downstream paths.',
    test101.verification_status = 'Regression test passed in the synthetic demo',
    test101.test_type = 'REGRESSION',
    test101.is_synthetic = true;

MERGE (fix101)-[:VERIFIED_BY]->(test101);

// 10. Pull Requests & Developers
MERGE (pr101:PullRequest {id: 'PR-101'})
SET pr101.title = 'feat(auth): stateless JWT authentication architecture',
    pr101.status = 'MERGED',
    pr101.merged_at = '2026-08-16T10:00:00Z',
    pr101.is_synthetic = true;

MERGE (pr108:PullRequest {id: 'PR-108'})
SET pr108.title = 'fix(auth): restore refresh token validation middleware',
    pr108.status = 'MERGED',
    pr108.merged_at = '2026-08-21T09:15:00Z',
    pr108.is_synthetic = true;

MERGE (devBob:Developer {id: 'DEV-BOB'})
SET devBob.name = 'Bob Ramirez (Senior Backend Eng)',
    devBob.email = 'bob@sentinel.dev',
    devBob.is_synthetic = true;

MERGE (devAlice:Developer {id: 'DEV-ALICE'})
SET devAlice.name = 'Alice Chen (Principal Security Eng)',
    devAlice.email = 'alice@sentinel.dev',
    devAlice.is_synthetic = true;

MERGE (dec101)-[:DECIDED_IN]->(pr101);
MERGE (bug101)-[:CHANGED_IN]->(pr108);
MERGE (devBob)-[:AUTHORED]->(pr101);
MERGE (devAlice)-[:AUTHORED]->(pr108);
