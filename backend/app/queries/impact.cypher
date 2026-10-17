// DevGraph Sentinel — Bounded Downstream Dependency Traversal Query
// Parameters:
//   $project_id: STRING (e.g. 'PRJ-SENTINEL')
//   $component_ids: LIST<STRING> (e.g. ['COMP-AUTH'])
//   $component_names: LIST<STRING> (e.g. ['Authentication'])

// Match directly modified components
MATCH (root:Component)
WHERE (root.id IN $component_ids OR root.name IN $component_names)
  AND (root.project_id = $project_id OR $project_id IS NULL)

// Traverse downstream consumers that depend on the modified root component (bounded 1 to 4 hops)
OPTIONAL MATCH path = (downstream:Component)-[:DEPENDS_ON*1..4]->(root)
WHERE downstream.project_id = $project_id OR downstream.project_id IS NULL

// Retrieve documented historical regressions on affected components
OPTIONAL MATCH (affected:Component)-[:HAS_BUG]->(b:Bug)
WHERE affected IN [root, downstream] AND (b.project_id = $project_id OR b.project_id IS NULL)
OPTIONAL MATCH (b)-[:RESOLVED_BY]->(f:Fix)-[:VERIFIED_BY]->(t:Test)

RETURN root,
       downstream,
       length(path) AS depth,
       [node IN nodes(path) | node.name] AS path_names,
       b AS bug,
       f AS fix,
       t AS test;
