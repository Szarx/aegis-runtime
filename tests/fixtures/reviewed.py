from aegis_policy import Policy, Rule
from aegis_runtime.reviewed_execution import ReviewedClient, ReviewedTool


def policy():
    return Policy("review-v1", (Rule("permit", "allow", ("demo-agent",), ("write",), ("records.write",)),))


def client(endpoint="http://127.0.0.1:8000"):
    return ReviewedClient(endpoint, token="synthetic-producer", execution_token="synthetic-executor", binding_key=b"synthetic-reviewed-binding-key-11")


def tool(function, transport=None, **changes):
    return ReviewedTool(function, **{**dict(client=transport or client(), policy=policy(), subject="demo-agent", permission="records.write", tool="write", tool_revision="impl-v1", disclose_arguments=True), **changes})


def payload(action_id="1"*32):
    def write(record="synthetic-001", value=1): pass
    return tool(write)._prepare(action_id, {}, "Synthetic change", 300)
