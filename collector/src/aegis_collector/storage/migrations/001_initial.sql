CREATE SCHEMA IF NOT EXISTS {schema};
CREATE TABLE IF NOT EXISTS {schema}.schema_version (version INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS {schema}.spans (
    trace_id CHAR(32) NOT NULL,
    span_id CHAR(16) NOT NULL,
    parent_span_id CHAR(16),
    name VARCHAR(256) NOT NULL,
    operation VARCHAR(32) NOT NULL CHECK (operation IN ('invoke_agent', 'execute_tool')),
    kind VARCHAR(16) NOT NULL CHECK (kind = 'INTERNAL'),
    status VARCHAR(16) NOT NULL CHECK (status IN ('UNSET', 'ERROR')),
    service_name VARCHAR(128) NOT NULL,
    agent_name VARCHAR(128),
    start_time_ns BIGINT NOT NULL CHECK (start_time_ns > 0),
    end_time_ns BIGINT NOT NULL CHECK (end_time_ns >= start_time_ns),
    resource JSONB NOT NULL,
    scope JSONB NOT NULL,
    attributes JSONB NOT NULL,
    events JSONB NOT NULL,
    resource_schema_url VARCHAR(256) NOT NULL,
    scope_schema_url VARCHAR(256) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (trace_id, span_id)
);
CREATE INDEX IF NOT EXISTS spans_started_idx ON {schema}.spans (start_time_ns, trace_id);
CREATE INDEX IF NOT EXISTS spans_agent_idx ON {schema}.spans (agent_name, trace_id);
CREATE INDEX IF NOT EXISTS spans_service_idx ON {schema}.spans (service_name, trace_id);
