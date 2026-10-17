// CodeBrain AI — Contextual Graph Evidence Retrieval Query
// Parameters:
//   $project_id: STRING (e.g. 'PRJ-SENTINEL')
//   $component_name: STRING (e.g. 'Authentication')
//   $component_id: STRING (e.g. 'COMP-AUTH')

MATCH (c:Component)
WHERE (c.id = $component_id OR toLower(c.name) = toLower($component_name))
  AND (c.project_id = $project_id OR $project_id IS NULL)

// 1. Technical Decisions affecting component
OPTIONAL MATCH dec_path = (c)-[r_dec:AFFECTED_BY]->(d:Decision)
WHERE d.project_id = $project_id OR d.project_id IS NULL
OPTIONAL MATCH (d)-[r_rsn:JUSTIFIED_BY]->(r:Reason)

// 2. Historical Incidents & Bugs
OPTIONAL MATCH bug_path = (c)-[r_bug:HAS_BUG]->(b:Bug)
WHERE b.project_id = $project_id OR b.project_id IS NULL
OPTIONAL MATCH (b)-[r_fix:RESOLVED_BY]->(f:Fix)
OPTIONAL MATCH (f)-[r_test:VERIFIED_BY]->(t:Test)

// 3. Component Dependencies
OPTIONAL MATCH (c)-[r_dep:DEPENDS_ON]->(dep:Dependency)

// 4. Source Files & Functions
OPTIONAL MATCH (c)-[r_file:CONTAINS]->(file:File)
WHERE file.project_id = $project_id OR file.project_id IS NULL
OPTIONAL MATCH (file)-[r_fn:CONTAINS]->(fn:Function)
WHERE fn.project_id = $project_id OR fn.project_id IS NULL

RETURN c,
       collect(DISTINCT d) AS decisions,
       collect(DISTINCT r) AS reasons,
       collect(DISTINCT b) AS bugs,
       collect(DISTINCT f) AS fixes,
       collect(DISTINCT t) AS tests,
       collect(DISTINCT dep) AS dependencies,
       collect(DISTINCT file) AS files,
       collect(DISTINCT fn) AS functions;
