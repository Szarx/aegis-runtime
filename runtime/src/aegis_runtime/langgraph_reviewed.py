"""Explicit host-driven review of one root LangGraph interrupt."""

from contextvars import ContextVar
from dataclasses import dataclass
import hashlib
import hmac
import json
import time

from aegis_policy import identifier
from .approvals import ApprovalUnavailable, canonical_arguments, _hex
from .reviewed_execution import ReviewedTool, reviewed_snapshot

REQUEST = "aegis.graph-request.v1"
TICKET = "aegis.graph-ticket.v1"
RECEIPT = "aegis.graph-receipt.v1"


class GraphBindingError(ValueError):
    def __init__(self):
        super().__init__("reviewed graph binding unavailable")


@dataclass(frozen=True, slots=True)
class GraphExecutionResult:
    value: object
    confirmation: str
    continuation: str
    graph_state: object = None


def _same(left, right):
    return canonical_arguments(left) == canonical_arguments(right)


class _GraphExecution(ReviewedTool):
    def _invoke(self, snapshot, *, deadline):
        self._graph_guard(snapshot)
        if time.monotonic() >= deadline:
            raise ApprovalUnavailable()
        return super()._invoke(snapshot, deadline=deadline)


class ReviewedGraphTool:
    def __init__(self, function, *, client, policy, subject, permission, tool, tool_revision,
                 graph_id, graph_revision, node_name, disclose_arguments=False):
        # Validate the original function using the unchanged sync contract.
        original = ReviewedTool(function, client=client, policy=policy, subject=subject,
                                permission=permission, tool=tool, tool_revision=tool_revision,
                                disclose_arguments=disclose_arguments)
        for value in (graph_id, graph_revision, node_name):
            if type(value) is not str:
                raise ValueError("invalid graph identifier")
            identifier(value)
        try:
            from langchain_core.runnables import RunnableConfig
            from langgraph.graph.state import CompiledStateGraph
            from langgraph.types import Command, interrupt
        except ImportError:
            raise ImportError("install aegis-runtime-control[reviewed-langgraph] to use reviewed graphs") from None
        self._graph_type, self._command = CompiledStateGraph, Command
        self._function, self._signature = function, original._signature
        self._key = client._key
        self._graph_id, self._graph_revision, self._node_name = graph_id, graph_revision, node_name
        self._tool_revision = tool_revision
        self._context = ContextVar("aegis-reviewed-graph", default=None)

        def guard(snapshot):
            graph_binding, arguments = snapshot['graph_binding'], snapshot['arguments']
            context = self._context.get()
            if context is None:
                raise GraphBindingError()
            graph, config, expected = context
            binding, current_arguments, _ = self._capture(graph, config)
            if not _same(binding, graph_binding) or not _same(binding, expected) or not _same(arguments, current_arguments):
                raise GraphBindingError()

        def execute(*, graph_binding, arguments):
            return self._function(**arguments)

        self._reviewed = _GraphExecution(execute, client=client, policy=policy, subject=subject,
                                      permission=permission, tool=tool, tool_revision=tool_revision,
                                      disclose_arguments=disclose_arguments)
        self._reviewed._graph_guard = guard

        def node(state, config: RunnableConfig):
            request = self._request(state, config["configurable"]["thread_id"])
            response = interrupt(request)
            try:
                self._verify_receipt(response, request, config)
            except Exception:
                raise GraphBindingError() from None
            return {"aegis_reviewed": {"action_id": response["action_id"], "status": "completed"}}

        self.node = node

    def _action_id(self, thread_id, call_id):
        raw = canonical_arguments({"graph_id": self._graph_id, "thread_id": thread_id, "call_id": call_id})
        return hmac.new(self._key, b"aegis.graph-action.v1\x00" + raw, hashlib.sha256).hexdigest()[:32]

    def _mac(self, value):
        return hmac.new(self._key, b"aegis.graph-receipt.v1\x00" + canonical_arguments(value), hashlib.sha256).hexdigest()

    def _request(self, state, thread_id):
        if type(thread_id) is not str:
            raise GraphBindingError()
        identifier(thread_id)
        if type(state) is not dict or type(state.get("aegis_call")) is not dict:
            raise GraphBindingError()
        call = state["aegis_call"]
        if set(call) != {"call_id", "arguments"} or not _hex(call["call_id"], 32):
            raise GraphBindingError()
        incoming, _ = reviewed_snapshot(call["arguments"])
        bound = self._signature.bind(**incoming)
        bound.apply_defaults()
        arguments, _ = reviewed_snapshot(dict(bound.arguments))
        request = {"schema": REQUEST, "graph_id": self._graph_id, "graph_revision": self._graph_revision,
                   "node": self._node_name, "thread_id": thread_id, "call_id": call["call_id"],
                   "tool_revision": self._tool_revision, "arguments": arguments}
        return reviewed_snapshot(request)[0]

    def _config(self, graph, config):
        if type(graph) is not self._graph_type or graph.checkpointer is None or graph.checkpointer is False:
            raise GraphBindingError()
        if type(config) is not dict or set(config) != {"configurable"}:
            raise GraphBindingError()
        options = config["configurable"]
        if type(options) is not dict or set(options) != {"thread_id"} or type(options["thread_id"]) is not str:
            raise GraphBindingError()
        identifier(options["thread_id"])
        return {"configurable": {"thread_id": options["thread_id"]}}

    def _capture(self, graph, config):
        try:
            config = self._config(graph, config)
            snapshot = graph.get_state(config)
            return self._capture_snapshot(snapshot, config)
        except Exception:
            raise GraphBindingError() from None

    def _capture_snapshot(self, snapshot, config):
        try:
            options = snapshot.config["configurable"]
            if options["thread_id"] != config["configurable"]["thread_id"] or options["checkpoint_ns"] != "":
                raise GraphBindingError()
            checkpoint = options["checkpoint_id"]
            if type(checkpoint) is not str or not 1 <= len(checkpoint) <= 128:
                raise GraphBindingError()
            if snapshot.next != (self._node_name,) or len(snapshot.tasks) != 1 or len(snapshot.interrupts) != 1:
                raise GraphBindingError()
            task, pending = snapshot.tasks[0], snapshot.interrupts[0]
            if task.name != self._node_name or task.error is not None or task.state is not None or len(task.interrupts) != 1 or task.interrupts[0].id != pending.id:
                raise GraphBindingError()
            if not _hex(pending.id, 32):
                raise GraphBindingError()
            request = self._request(snapshot.values, options["thread_id"])
            if not _same(request, pending.value):
                raise GraphBindingError()
            binding = {key: request[key] for key in ("graph_id", "graph_revision", "node", "thread_id", "call_id", "tool_revision")}
            binding.update(checkpoint_id=checkpoint, interrupt_id=pending.id,
                           request_digest=hashlib.sha256(canonical_arguments(request)).hexdigest())
            return binding, request["arguments"], self._action_id(request["thread_id"], request["call_id"])
        except Exception:
            raise GraphBindingError() from None

    def prepare(self, graph, config, *, summary, ttl_seconds=300):
        binding, arguments, action_id = self._capture(graph, config)
        self._reviewed.prepare({"graph_binding": binding, "arguments": arguments}, action_id=action_id,
                               summary=summary, ttl_seconds=ttl_seconds)
        return {"schema": TICKET, "action_id": action_id, "graph_binding": binding, "arguments": arguments,
                "summary": summary, "ttl_seconds": ttl_seconds}

    def _ticket(self, graph, config, ticket):
        try:
            ticket = json.loads(canonical_arguments(ticket))
            if type(ticket) is not dict or set(ticket) != {"schema", "action_id", "graph_binding", "arguments", "summary", "ttl_seconds"} or ticket["schema"] != TICKET:
                raise GraphBindingError()
            binding, arguments, action_id = self._capture(graph, config)
            if not _same(binding, ticket["graph_binding"]) or not _same(arguments, ticket["arguments"]) or ticket["action_id"] != action_id:
                raise GraphBindingError()
            return ticket
        except Exception:
            raise GraphBindingError() from None

    def _verify_receipt(self, response, request, config):
        if type(response) is not dict or set(response) != {"schema", "action_id", "graph_binding", "status", "mac"}:
            raise GraphBindingError()
        value = {key: child for key, child in response.items() if key != "mac"}
        if response["schema"] != RECEIPT or response["status"] != "completed" or type(response["mac"]) is not str or not hmac.compare_digest(response["mac"], self._mac(value)):
            raise GraphBindingError()
        binding = response["graph_binding"]
        if response["action_id"] != self._action_id(request["thread_id"], request["call_id"]):
            raise GraphBindingError()
        expected = {key: request[key] for key in ("graph_id", "graph_revision", "node", "thread_id", "call_id", "tool_revision")}
        expected.update(request_digest=hashlib.sha256(canonical_arguments(request)).hexdigest())
        if any(binding[key] != child for key, child in expected.items()):
            raise GraphBindingError()
        # Locked LangGraph 1.2.15 supplies the root snapshot ID in this map.
        if binding["checkpoint_id"] != config["configurable"]["checkpoint_map"][""]:
            raise GraphBindingError()

    def resume(self, graph, config, ticket):
        config = self._config(graph, config)
        ticket = self._ticket(graph, config, ticket)
        binding = ticket["graph_binding"]
        token = self._context.set((graph, config, binding))
        try:
            result = self._reviewed.resume(ticket["action_id"], {"graph_binding": binding, "arguments": ticket["arguments"]},
                                           summary=ticket["summary"], ttl_seconds=ticket["ttl_seconds"])
        finally:
            self._context.reset(token)
        if result.confirmation != "confirmed":
            return GraphExecutionResult(result.value, result.confirmation, "not_resumed")
        try:
            self._ticket(graph, config, ticket)
        except GraphBindingError:
            return GraphExecutionResult(result.value, result.confirmation, "blocked")
        receipt = {"schema": RECEIPT, "action_id": ticket["action_id"], "graph_binding": binding, "status": "completed"}
        receipt["mac"] = self._mac(receipt)
        try:
            state = graph.invoke(self._command(resume={binding["interrupt_id"]: receipt}), config, durability="sync")
        except Exception:
            return GraphExecutionResult(result.value, result.confirmation, "unknown")
        return GraphExecutionResult(result.value, result.confirmation, "resumed", state)
