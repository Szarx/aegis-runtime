"""Transactional, immutable-span storage with derived trace summaries."""

import re
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import asdict
from importlib.resources import files

import psycopg
from psycopg import IsolationLevel, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..ingestion.otlp import SpanRecord
from .approvals import ApprovalStore
from .reviewed import ReviewedActionStore


class StorageError(RuntimeError):
    pass


class PostgresSpanStore(ApprovalStore, ReviewedActionStore):
    def __init__(self, database_url: str, schema: str = "aegis"):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("invalid database schema name")
        if not database_url:
            raise ValueError("database configuration is required")
        self.database_url = database_url
        self.schema = schema
        self._table = sql.SQL("{}.spans").format(sql.Identifier(schema))

    @contextmanager
    def connection(self, *, readonly: bool = False):
        try:
            with psycopg.connect(
                self.database_url, connect_timeout=3, options="-c statement_timeout=5000 -c timezone=UTC", row_factory=dict_row
            ) as connection:
                if readonly:
                    connection.isolation_level = IsolationLevel.REPEATABLE_READ
                    connection.read_only = True
                yield connection
        except psycopg.Error:
            raise StorageError("database operation failed") from None

    def migrate(self) -> None:
        script = files("aegis_collector.storage").joinpath("migrations/001_initial.sql").read_text(encoding="utf-8")
        version_table = sql.SQL("{}.schema_version").format(sql.Identifier(self.schema))
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ["aegis-migration:" + self.schema])
            connection.execute(sql.SQL(script).format(schema=sql.Identifier(self.schema)))
            versions = connection.execute(sql.SQL("SELECT version FROM {}").format(version_table)).fetchall()
            present = {row["version"] for row in versions}
            if not present <= {1, 2, 3, 4} or (present and present != set(range(1, max(present) + 1))):
                raise StorageError("unsupported schema version")
            connection.execute(sql.SQL("INSERT INTO {} (version) VALUES (1) ON CONFLICT DO NOTHING").format(version_table))
            if 2 not in present:
                upgrade = files("aegis_collector.storage").joinpath("migrations/002_llm_spans.sql").read_text(encoding="utf-8")
                connection.execute(sql.SQL(upgrade).format(schema=sql.Identifier(self.schema)))
                connection.execute(sql.SQL("INSERT INTO {} (version) VALUES (2)").format(version_table))
            if 3 not in present:
                upgrade = files("aegis_collector.storage").joinpath("migrations/003_approvals.sql").read_text(encoding="utf-8")
                connection.execute(sql.SQL(upgrade).format(schema=sql.Identifier(self.schema)))
                connection.execute(sql.SQL("INSERT INTO {} (version) VALUES (3)").format(version_table))
            if 4 not in present:
                upgrade = files("aegis_collector.storage").joinpath("migrations/004_reviewed_actions.sql").read_text(encoding="utf-8")
                connection.execute(sql.SQL(upgrade).format(schema=sql.Identifier(self.schema)))
                connection.execute(sql.SQL("INSERT INTO {} (version) VALUES (4)").format(version_table))

    def ping(self) -> None:
        with self.connection(readonly=True) as connection:
            connection.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(self._table))
            versions = connection.execute(sql.SQL("SELECT version FROM {}.schema_version").format(sql.Identifier(self.schema))).fetchall()
            connection.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(self._approvals))
            connection.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(self._reviewed))
            if {row["version"] for row in versions} != {1, 2, 3, 4}:
                raise StorageError("database schema migration is required")

    def insert(self, records: Sequence[SpanRecord]) -> int:
        if not records:
            return 0
        columns = list(asdict(records[0]))
        statement = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (trace_id, span_id) DO NOTHING").format(
            self._table,
            sql.SQL(", ").join(sql.Identifier(key) for key in columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
        values = []
        for record in records:
            data = asdict(record)
            values.append(tuple(Jsonb(data[key]) if key in ("resource", "scope", "attributes", "events") else data[key] for key in columns))
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(statement, values)
                return cursor.rowcount

    def _aggregate(self):
        return sql.SQL("""
            SELECT trace_id, MIN(start_time_ns) AS start_time_unix_nano,
                   MAX(end_time_ns) AS end_time_unix_nano,
                   MAX(end_time_ns) - MIN(start_time_ns) AS duration_ns,
                   COUNT(*) AS span_count,
                   CASE WHEN BOOL_OR(status = 'ERROR') THEN 'ERROR' ELSE 'UNSET' END AS status,
                   ARRAY_REMOVE(ARRAY_AGG(DISTINCT agent_name ORDER BY agent_name), NULL) AS agent_names,
                   CASE
                     WHEN BOOL_OR(attributes->>'aegis.mapping.version' = 'aegis.graph.v1' AND attributes->>'aegis.graph.outcome' = 'error') THEN 'error'
                     WHEN BOOL_OR(attributes->>'aegis.mapping.version' = 'aegis.graph.v1' AND attributes->>'aegis.graph.outcome' = 'cancelled') THEN 'cancelled'
                     WHEN BOOL_OR(attributes->>'aegis.mapping.version' = 'aegis.graph.v1' AND attributes->>'aegis.graph.outcome' = 'closed') THEN 'closed'
                     WHEN BOOL_OR(attributes->>'aegis.mapping.version' = 'aegis.graph.v1' AND attributes->>'aegis.graph.outcome' = 'completed') THEN 'completed'
                     ELSE NULL END AS graph_outcome
            FROM {} GROUP BY trace_id
        """).format(self._table)

    def list_traces(
        self, *, limit=50, offset=0, agent_name=None, service_name=None,
        status=None, started_after_ns=None, started_before_ns=None,
    ) -> dict:
        clauses = []
        params = []
        for column, value in (("agent_name", agent_name), ("service_name", service_name)):
            if value is not None:
                clauses.append(sql.SQL("EXISTS (SELECT 1 FROM {} s WHERE s.trace_id=t.trace_id AND s.{}=%s)").format(self._table, sql.Identifier(column)))
                params.append(value)
        for column, operator, value in (
            ("status", "=", status),
            ("start_time_unix_nano", ">=", started_after_ns),
            ("start_time_unix_nano", "<=", started_before_ns),
        ):
            if value is not None:
                clauses.append(sql.SQL("{} {} %s").format(sql.Identifier(column), sql.SQL(operator)))
                params.append(value)
        where = sql.SQL(" AND ").join(clauses) if clauses else sql.SQL("TRUE")
        def select_query(selection):
            return sql.SQL("WITH traces AS ({}) SELECT {} FROM traces t WHERE {}").format(self._aggregate(), selection, where)
        with self.connection(readonly=True) as connection:
            total = connection.execute(select_query(sql.SQL("COUNT(*) AS total")), params).fetchone()["total"]
            query = select_query(sql.SQL("*")) + sql.SQL(" ORDER BY start_time_unix_nano DESC, trace_id ASC LIMIT %s OFFSET %s")
            items = connection.execute(query, [*params, limit, offset]).fetchall()
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def trace_detail(self, trace_id: str) -> dict | None:
        with self.connection(readonly=True) as connection:
            summary = connection.execute(
                sql.SQL("WITH traces AS ({}) SELECT * FROM traces WHERE trace_id=%s").format(self._aggregate()), [trace_id]
            ).fetchone()
            if summary is None:
                return None
            rows = connection.execute(
                sql.SQL("SELECT * FROM {} WHERE trace_id=%s ORDER BY start_time_ns, span_id").format(self._table), [trace_id]
            ).fetchall()
        spans = []
        for row in rows:
            row.pop("received_at")
            row["start_time_unix_nano"] = row.pop("start_time_ns")
            row["end_time_unix_nano"] = row.pop("end_time_ns")
            spans.append(row)
        identifiers = {span["span_id"] for span in spans}
        missing = sorted({span["parent_span_id"] for span in spans if span["parent_span_id"] and span["parent_span_id"] not in identifiers})
        return {"trace": summary, "spans": spans, "missing_parent_ids": missing}

    def list_security_events(self, *, limit=20, offset=0, **filters):
        attributes={'subject':'aegis.subject.id','tool':'gen_ai.tool.name','permission':'aegis.tool.permission',
            'action_id':'aegis.action.id','effect':'aegis.decision.effect','outcome':'aegis.action.outcome'}
        clauses=[sql.SQL("attributes->>'aegis.mapping.version' IN ('aegis.governance.v1','aegis.governance.v2') AND operation='execute_tool' AND kind='INTERNAL'")]
        params=[]
        for key,attribute in attributes.items():
            if filters.get(key) is not None:
                clauses.append(sql.SQL('attributes->>%s = %s'));params.extend((attribute,filters[key]))
        for column in ('service_name','trace_id'):
            if filters.get(column) is not None:
                clauses.append(sql.SQL('{} = %s').format(sql.Identifier(column)));params.append(filters[column])
        for key,operator in (('started_after_ns','>='),('started_before_ns','<=')):
            if filters.get(key) is not None:
                clauses.append(sql.SQL('start_time_ns {} %s').format(sql.SQL(operator)));params.append(filters[key])
        where=sql.SQL(' AND ').join(clauses)
        selection=sql.SQL("""trace_id,span_id,service_name,agent_name,status,
            start_time_ns AS start_time_unix_nano,end_time_ns AS end_time_unix_nano,
            attributes->>'aegis.action.id' AS action_id,attributes->>'gen_ai.tool.name' AS tool,
            attributes->>'aegis.subject.id' AS subject,attributes->>'aegis.tool.permission' AS permission,
            attributes->>'aegis.policy.revision' AS policy_revision,attributes->>'aegis.decision.rule_id' AS rule_id,
            attributes->>'aegis.decision.effect' AS effect,attributes->>'aegis.decision.reason' AS reason,
            attributes->>'aegis.action.outcome' AS outcome""")
        with self.connection(readonly=True) as connection:
            total=connection.execute(sql.SQL('SELECT COUNT(*) AS total FROM {} WHERE {}').format(self._table,where),params).fetchone()['total']
            items=connection.execute(sql.SQL('SELECT {} FROM {} WHERE {} ORDER BY start_time_ns DESC,trace_id ASC,span_id ASC LIMIT %s OFFSET %s').format(selection,self._table,where),[*params,limit,offset]).fetchall()
        return dict(items=items,total=total,limit=limit,offset=offset)
