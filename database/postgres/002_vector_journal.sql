CREATE TABLE vector_operation_commits (
 operation_id uuid PRIMARY KEY,
 committed_at timestamptz NOT NULL DEFAULT now()
);
