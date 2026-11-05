CREATE TABLE {schema}.reviewed_actions (
    action_id TEXT PRIMARY KEY REFERENCES {schema}.approvals(action_id),
    tool_revision TEXT NOT NULL,
    review_arguments JSONB NOT NULL CHECK (jsonb_typeof(review_arguments) = 'object'),
    review_digest TEXT NOT NULL CHECK (review_digest ~ '^[0-9a-f]{{64}}$'),
    execution_state TEXT NOT NULL DEFAULT 'available' CHECK (execution_state IN ('available','claimed','completed','failed')),
    claim_id TEXT UNIQUE CHECK (claim_id ~ '^[0-9a-f]{{32}}$' AND claim_id <> repeat('0',32)),
    executor TEXT,
    claimed_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CHECK ((execution_state='available' AND claim_id IS NULL AND executor IS NULL AND claimed_at IS NULL AND finished_at IS NULL)
       OR (execution_state='claimed' AND claim_id IS NOT NULL AND executor IS NOT NULL AND claimed_at IS NOT NULL AND finished_at IS NULL)
       OR (execution_state IN ('completed','failed') AND claim_id IS NOT NULL AND executor IS NOT NULL AND claimed_at IS NOT NULL AND finished_at IS NOT NULL))
);
