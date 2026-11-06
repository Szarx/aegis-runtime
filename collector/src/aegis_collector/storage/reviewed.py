"""A consumed claim is never released, including after a crash or business failure."""

from psycopg import sql
from psycopg.types.json import Jsonb
from .approvals import ApprovalConflict, ApprovalMissing, effective

EXTRA = ("tool_revision", "review_arguments", "review_digest")
BINDING = ("subject", "tool", "permission", "policy_revision", "policy_digest", "arguments_hmac",
           "tool_revision", "review_digest", "summary", "ttl_seconds")


class ReviewedActionStore:
    def _reviewed_select(self, suffix):
        return sql.SQL("SELECT a.*, r.tool_revision, r.review_arguments, r.review_digest, r.execution_state, r.claim_id, r.executor, r.claimed_at, r.finished_at FROM {} a JOIN {} r USING (action_id) ").format(self._approvals, self._reviewed) + suffix

    def _locked_reviewed(self, connection, action_id):
        row = connection.execute(self._reviewed_select(sql.SQL("WHERE a.action_id=%s FOR UPDATE OF a, r")), [action_id]).fetchone()
        if row is None:
            raise ApprovalMissing()
        return row

    def create_reviewed(self, data):
        base = {key: value for key, value in data.items() if key not in EXTRA}
        with self.connection() as connection:
            _, created = self._insert_approval(connection, base)
            prior = connection.execute(sql.SQL("SELECT * FROM {} WHERE action_id=%s").format(self._reviewed), [data["action_id"]]).fetchone()
            if not created and prior is None:
                raise ApprovalConflict()
            if prior is not None and any(prior[key] != data[key] for key in EXTRA):
                raise ApprovalConflict()
            if created:
                connection.execute(sql.SQL("INSERT INTO {} (action_id, tool_revision, review_arguments, review_digest) VALUES (%s,%s,%s,%s)").format(self._reviewed), [data["action_id"], data["tool_revision"], Jsonb(data["review_arguments"]), data["review_digest"]])
            row = self._locked_reviewed(connection, data["action_id"])
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            return effective(row, now)

    def list_reviewed(self, *, limit=20, offset=0, action_id=None):
        where = sql.SQL("WHERE r.action_id=%s ") if action_id is not None else sql.SQL("")
        params = [action_id] if action_id is not None else []
        with self.connection(readonly=True) as connection:
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            total = connection.execute(sql.SQL("SELECT COUNT(*) AS total FROM {} r ").format(self._reviewed) + where, params).fetchone()["total"]
            rows = connection.execute(
                self._reviewed_select(where + sql.SQL("ORDER BY created_at DESC, action_id LIMIT %s OFFSET %s")),
                [*params, limit, offset],
            ).fetchall()
        return dict(items=[effective(row, now) for row in rows], total=total, limit=limit, offset=offset)

    def decide_reviewed(self, action_id, decision, digest, reviewer):
        with self.connection() as connection:
            row = self._locked_reviewed(connection, action_id)
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if row["review_digest"] != digest or row["expires_at"] <= now or row["status"] not in ("pending", decision) or row["execution_state"] != "available":
                raise ApprovalConflict()
            if row["status"] == "pending":
                connection.execute(sql.SQL("UPDATE {} SET status=%s, decided_at=%s, reviewer=%s WHERE action_id=%s").format(self._approvals), [decision, now, reviewer, action_id])
            return self._locked_reviewed(connection, action_id)

    def claim_reviewed(self, action_id, binding, executor):
        with self.connection() as connection:
            row = self._locked_reviewed(connection, action_id)
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if any(row[key] != binding[key] for key in BINDING) or row["status"] != "approved" or row["expires_at"] <= now or row["execution_state"] != "available":
                raise ApprovalConflict()
            # Random claim IDs are globally unique. Collisions fail the transaction.
            connection.execute(sql.SQL("UPDATE {} SET execution_state='claimed', claim_id=%s, executor=%s, claimed_at=%s WHERE action_id=%s").format(self._reviewed), [binding["claim_id"], executor, now, action_id])
            result = self._locked_reviewed(connection, action_id)
            result["remaining_ms"] = max(0, int((row["expires_at"] - now).total_seconds() * 1000))
            return result

    def complete_reviewed(self, action_id, claim_id, outcome, executor):
        with self.connection() as connection:
            row = self._locked_reviewed(connection, action_id)
            if row["claim_id"] != claim_id or row["executor"] != executor or row["execution_state"] not in ("claimed", outcome):
                raise ApprovalConflict()
            if row["execution_state"] == "claimed":
                connection.execute(sql.SQL("UPDATE {} SET execution_state=%s, finished_at=clock_timestamp() WHERE action_id=%s").format(self._reviewed), [outcome, action_id])
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            return effective(self._locked_reviewed(connection, action_id), now)
