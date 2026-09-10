"""Schema-4 project drafts; execution evidence requires a later explicit schema."""

SCHEMA_V4_ADDITIONS = """
CREATE TABLE workflow_receipts (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  operation_id TEXT NOT NULL CHECK(length(operation_id)=36),
  action TEXT NOT NULL CHECK(action IN ('workflow.state_upgraded','draft.saved','draft.archived','draft.restored')),
  action_version INTEGER NOT NULL CHECK(action_version=1),
  actor_id TEXT NOT NULL, actor_authority TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  request_json TEXT NOT NULL CHECK(length(CAST(request_json AS BLOB))<=65536),
  result_json TEXT NOT NULL CHECK(length(CAST(result_json AS BLOB))<=65536),
  PRIMARY KEY(project_id,operation_id)
);
CREATE TABLE workflow_proposals (
  project_id TEXT NOT NULL,
  content_id TEXT NOT NULL CHECK(length(content_id)=64 AND content_id NOT GLOB '*[^0-9a-f]*'),
  snapshot_id TEXT NOT NULL,
  layer_id TEXT NOT NULL,
  relative_path TEXT NOT NULL CHECK(length(CAST(relative_path AS BLOB)) BETWEEN 1 AND 32768),
  raw_sha256 TEXT NOT NULL CHECK(length(raw_sha256)=64 AND raw_sha256 NOT GLOB '*[^0-9a-f]*'),
  candidate_sha256 TEXT NOT NULL CHECK(length(candidate_sha256)=64 AND candidate_sha256 NOT GLOB '*[^0-9a-f]*'),
  candidate_size_bytes INTEGER NOT NULL CHECK(candidate_size_bytes BETWEEN 0 AND 1048576),
  canonical_json BLOB NOT NULL CHECK(typeof(canonical_json)='blob' AND length(canonical_json) BETWEEN 1 AND 1572864),
  PRIMARY KEY(project_id,content_id),
  FOREIGN KEY(project_id,snapshot_id,layer_id) REFERENCES snapshot_layers(project_id,snapshot_id,layer_id)
);
CREATE TABLE workflow_draft_heads (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  draft_id TEXT NOT NULL CHECK(length(draft_id)=36),
  current_revision INTEGER NOT NULL CHECK(current_revision BETWEEN 1 AND 9223372036854775807),
  PRIMARY KEY(project_id,draft_id),
  FOREIGN KEY(project_id,draft_id,current_revision)
    REFERENCES workflow_draft_revisions(project_id,draft_id,revision) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE workflow_draft_revisions (
  project_id TEXT NOT NULL,
  draft_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9223372036854775807),
  proposal_content_id TEXT NOT NULL,
  title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 240 AND length(CAST(title AS BLOB))<=960),
  status TEXT NOT NULL CHECK(status IN ('active','archived')),
  operation_id TEXT NOT NULL,
  PRIMARY KEY(project_id,draft_id,revision),
  UNIQUE(project_id,operation_id),
  FOREIGN KEY(project_id,draft_id) REFERENCES workflow_draft_heads(project_id,draft_id),
  FOREIGN KEY(project_id,proposal_content_id) REFERENCES workflow_proposals(project_id,content_id),
  FOREIGN KEY(project_id,operation_id) REFERENCES workflow_receipts(project_id,operation_id)
);
"""
