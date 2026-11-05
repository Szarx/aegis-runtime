CREATE TABLE {schema}.approvals (
    action_id TEXT PRIMARY KEY CHECK (action_id ~ '^[0-9a-f]{{32}}$' AND action_id <> repeat('0',32)),
    subject TEXT NOT NULL,
    tool TEXT NOT NULL,
    permission TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    policy_digest TEXT NOT NULL CHECK (policy_digest ~ '^[0-9a-f]{{64}}$'),
    arguments_hmac TEXT NOT NULL CHECK (arguments_hmac ~ '^[0-9a-f]{{64}}$'),
    summary TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL CHECK (ttl_seconds BETWEEN 30 AND 600),
    trace_id TEXT,
    span_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp(),
    expires_at TIMESTAMPTZ NOT NULL,
    decided_at TIMESTAMPTZ,
    reviewer TEXT,
    CHECK ((trace_id IS NULL) = (span_id IS NULL)),
    CHECK (expires_at > created_at),
    CHECK ((status = 'pending' AND decided_at IS NULL AND reviewer IS NULL)
        OR (status IN ('approved','rejected') AND decided_at IS NOT NULL AND reviewer IS NOT NULL))
);
CREATE INDEX approvals_created_idx ON {schema}.approvals (created_at DESC, action_id);
