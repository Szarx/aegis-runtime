"""Immutable request bindings and row-locked manual decisions."""

from psycopg import sql


class ApprovalConflict(Exception):
    pass


class ApprovalMissing(Exception):
    pass


def effective(row, now):
    row = dict(row)
    if row["status"] in ("pending", "approved") and row["expires_at"] <= now:
        row["status"] = "expired"
    return row


class ApprovalStore:
    @property
    def _reviewed(self):
        return sql.SQL("{}.reviewed_actions").format(sql.Identifier(self.schema))

    @property
    def _approvals(self):
        return sql.SQL("{}.approvals").format(sql.Identifier(self.schema))

    def create_approval(self, data):
        with self.connection() as connection:
            row, _ = self._insert_approval(connection, data)
            if connection.execute(sql.SQL("SELECT 1 FROM {} WHERE action_id=%s").format(self._reviewed), [data["action_id"]]).fetchone():
                raise ApprovalConflict()
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            return effective(row, now)

    def _insert_approval(self, connection, data):
        columns = list(data)
        inserted = connection.execute(sql.SQL("INSERT INTO {} ({}, expires_at) VALUES ({}, statement_timestamp() + %s * INTERVAL '1 second') ON CONFLICT (action_id) DO NOTHING RETURNING action_id").format(
                self._approvals, sql.SQL(", ").join(map(sql.Identifier, columns)),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns)), [*data.values(), data["ttl_seconds"]]).fetchone()
        row = connection.execute(sql.SQL("SELECT * FROM {} WHERE action_id=%s FOR UPDATE").format(self._approvals), [data["action_id"]]).fetchone()
        if any(row[key] != value for key, value in data.items()):
            raise ApprovalConflict()
        return row, inserted is not None

    def list_approvals(self, *, limit=20, offset=0):
        with self.connection(readonly=True) as connection:
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            where = sql.SQL("NOT EXISTS (SELECT 1 FROM {} r WHERE r.action_id=a.action_id)").format(self._reviewed)
            total = connection.execute(sql.SQL("SELECT COUNT(*) AS total FROM {} a WHERE {}").format(self._approvals, where)).fetchone()["total"]
            rows = connection.execute(sql.SQL("SELECT a.* FROM {} a WHERE {} ORDER BY created_at DESC, action_id LIMIT %s OFFSET %s").format(self._approvals, where), [limit, offset]).fetchall()
        return dict(items=[effective(row, now) for row in rows], total=total, limit=limit, offset=offset)

    def decide_approval(self, action_id, decision, reviewer):
        with self.connection() as connection:
            row = connection.execute(sql.SQL("SELECT * FROM {} WHERE action_id=%s FOR UPDATE").format(self._approvals), [action_id]).fetchone()
            if row is None:
                raise ApprovalMissing()
            if connection.execute(sql.SQL("SELECT 1 FROM {} WHERE action_id=%s").format(self._reviewed), [action_id]).fetchone():
                raise ApprovalMissing()
            now = connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if row["expires_at"] <= now or row["status"] not in ("pending", decision):
                raise ApprovalConflict()
            if row["status"] == "pending":
                row = connection.execute(sql.SQL("UPDATE {} SET status=%s, decided_at=%s, reviewer=%s WHERE action_id=%s RETURNING *").format(self._approvals), [decision, now, reviewer, action_id]).fetchone()
            return row
