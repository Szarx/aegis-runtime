ALTER TABLE {schema}.spans DROP CONSTRAINT IF EXISTS spans_operation_check;
ALTER TABLE {schema}.spans DROP CONSTRAINT IF EXISTS spans_kind_check;
ALTER TABLE {schema}.spans ADD CONSTRAINT spans_operation_kind_check CHECK (
    (operation IN ('invoke_agent', 'execute_tool') AND kind = 'INTERNAL')
    OR (operation = 'chat' AND kind = 'CLIENT')
);
