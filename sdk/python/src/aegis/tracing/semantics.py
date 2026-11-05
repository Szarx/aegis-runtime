"""The deliberately small GenAI mapping frozen by SPEC-001."""

MAPPING_VERSION = "aegis.genai.v1"
GENAI_REFERENCE = "5293effb97f18ddb0602da884dadee6119d67679"
ATTRIBUTE_KEYS = frozenset(
    {
        "gen_ai.operation.name",
        "gen_ai.agent.name",
        "gen_ai.tool.name",
        "aegis.tool.permission",
        "aegis.mapping.version",
        "error.type",
    }
)
RESOURCE_KEYS = frozenset(
    {
        "service.name",
        "telemetry.sdk.name",
        "telemetry.sdk.language",
        "telemetry.sdk.version",
    }
)

LLM_MAPPING_VERSION = "aegis.genai.v2"
LLM_STRING_KEYS = frozenset({
    "gen_ai.provider.name", "gen_ai.request.model", "gen_ai.response.model",
    "aegis.call.api", "aegis.call.mode", "aegis.call.outcome",
})
TOKEN_KEYS = frozenset({"gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens"})
GRAPH_MAPPING_VERSION = "aegis.graph.v1"
GRAPH_KEYS = (ATTRIBUTE_KEYS - {"gen_ai.tool.name", "aegis.tool.permission"}) | frozenset({"aegis.graph.mode", "aegis.graph.outcome"})
GOVERNANCE_MAPPING_VERSION = 'aegis.governance.v1'
GOVERNANCE_KEYS = ATTRIBUTE_KEYS | frozenset({'aegis.action.id','aegis.subject.id','aegis.policy.revision',
    'aegis.decision.rule_id','aegis.decision.effect','aegis.decision.reason','aegis.action.outcome'})
APPROVAL_GOVERNANCE_KEYS = GOVERNANCE_KEYS | frozenset({'aegis.approval.phase'})


def validate_label(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError(f"{field} must be a nonblank string of at most 128 characters")
    return value


def validate_timeout(timeout_millis: int) -> None:
    if type(timeout_millis) is not int or timeout_millis < 0:
        raise ValueError("timeout_millis must be a nonnegative integer")
