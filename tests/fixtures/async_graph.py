"""Real async graph driver with the shared strict HTTP transport fixture."""

from aegis_runtime.async_langgraph_reviewed import AsyncReviewedGraphTool
from tests.fixtures.reviewed import policy
from tests.fixtures.graph_reviewed import build, config, initial


def gate(function, connection, **changes):
    return AsyncReviewedGraphTool(function, **{**dict(client=connection, policy=policy(), subject='demo-agent',
        permission='records.write', tool='write', tool_revision='async-impl-v1', graph_id='demo-graph',
        graph_revision='graph-v1', node_name='review', disclose_arguments=True), **changes})
