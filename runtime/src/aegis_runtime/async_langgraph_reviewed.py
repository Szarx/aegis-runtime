"""Native asyncio host driver for one root reviewed LangGraph interrupt."""

import asyncio
from contextvars import ContextVar
import json
import time

from aegis_policy import identifier
from .approvals import ApprovalUnavailable, canonical_arguments
from .async_reviewed_execution import AsyncReviewedTool
from .langgraph_reviewed import GraphBindingError, GraphExecutionResult, ReviewedGraphTool, RECEIPT, TICKET, _same


class _AsyncGraphExecution(AsyncReviewedTool):
    async def _invoke(self, snapshot, *, deadline):
        await self._graph_guard(snapshot)
        # Reading a checkpoint consumes the claim's time budget too.
        if time.monotonic() >= deadline:
            raise ApprovalUnavailable()
        return await super()._invoke(snapshot, deadline=deadline)


class AsyncReviewedGraphTool(ReviewedGraphTool):
    def __init__(self, function, *, client, policy, subject, permission, tool, tool_revision,
                 graph_id, graph_revision, node_name, disclose_arguments=False):
        original = AsyncReviewedTool(function, client=client, policy=policy, subject=subject,
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
            raise ImportError("install aegis-runtime-control[reviewed-langgraph-async] to use async reviewed graphs") from None
        self._graph_type, self._command = CompiledStateGraph, Command
        self._function, self._signature, self._key = function, original._signature, client._key
        self._graph_id, self._graph_revision, self._node_name = graph_id, graph_revision, node_name
        self._tool_revision, self._loop = tool_revision, None
        self._context = ContextVar("aegis-async-reviewed-graph", default=None)

        async def guard(snapshot):
            context = self._context.get()
            if context is None:
                raise GraphBindingError()
            graph, config, expected = context
            binding, arguments, _ = await self._capture(graph, config)
            if not _same(binding, snapshot["graph_binding"]) or not _same(binding, expected) or not _same(arguments, snapshot["arguments"]):
                raise GraphBindingError()

        async def execute(*, graph_binding, arguments):
            return await self._function(**arguments)

        self._reviewed = _AsyncGraphExecution(execute, client=client, policy=policy, subject=subject,
                                             permission=permission, tool=tool, tool_revision=tool_revision,
                                             disclose_arguments=disclose_arguments)
        self._reviewed._graph_guard = guard

        async def node(state, config: RunnableConfig):
            await asyncio.sleep(0)
            self._bind_loop()
            request = self._request(state, config["configurable"]["thread_id"])
            response = interrupt(request)
            try:
                self._verify_receipt(response, request, config)
            except Exception:
                raise GraphBindingError() from None
            return {"aegis_reviewed": {"action_id": response["action_id"], "status": "completed"}}

        self.node = node

    def _bind_loop(self):
        current = asyncio.get_running_loop()
        if self._loop is not None and self._loop is not current:
            raise ValueError("async reviewed graph requires its original event loop")
        self._loop = current

    async def _capture(self, graph, config):
        self._bind_loop()
        try:
            config = self._config(graph, config)
            snapshot = await graph.aget_state(config)
            return self._capture_snapshot(snapshot, config)
        except Exception:
            raise GraphBindingError() from None

    async def prepare(self, graph, config, *, summary, ttl_seconds=300):
        await asyncio.sleep(0)
        binding, arguments, action_id = await self._capture(graph, config)
        await self._reviewed.prepare({"graph_binding": binding, "arguments": arguments}, action_id=action_id,
                                     summary=summary, ttl_seconds=ttl_seconds)
        return {"schema": TICKET, "action_id": action_id, "graph_binding": binding, "arguments": arguments,
                "summary": summary, "ttl_seconds": ttl_seconds}

    async def _ticket(self, graph, config, ticket):
        try:
            ticket = json.loads(canonical_arguments(ticket))
            if type(ticket) is not dict or set(ticket) != {"schema", "action_id", "graph_binding", "arguments", "summary", "ttl_seconds"} or ticket["schema"] != TICKET:
                raise GraphBindingError()
            binding, arguments, action_id = await self._capture(graph, config)
            if not _same(binding, ticket["graph_binding"]) or not _same(arguments, ticket["arguments"]) or ticket["action_id"] != action_id:
                raise GraphBindingError()
            return ticket
        except Exception:
            raise GraphBindingError() from None

    async def resume(self, graph, config, ticket):
        await asyncio.sleep(0)
        self._bind_loop()
        config = self._config(graph, config)
        ticket = await self._ticket(graph, config, ticket)
        binding = ticket["graph_binding"]
        token = self._context.set((graph, config, binding))
        try:
            result = await self._reviewed.resume(ticket["action_id"], {"graph_binding": binding, "arguments": ticket["arguments"]},
                                                 summary=ticket["summary"], ttl_seconds=ticket["ttl_seconds"])
        finally:
            self._context.reset(token)
        if result.confirmation != "confirmed":
            return GraphExecutionResult(result.value, result.confirmation, "not_resumed")
        try:
            await self._ticket(graph, config, ticket)
        except GraphBindingError:
            return GraphExecutionResult(result.value, result.confirmation, "blocked")
        receipt = {"schema": RECEIPT, "action_id": ticket["action_id"], "graph_binding": binding, "status": "completed"}
        receipt["mac"] = self._mac(receipt)
        try:
            state = await graph.ainvoke(self._command(resume={binding["interrupt_id"]: receipt}), config, durability="sync")
        except Exception:
            return GraphExecutionResult(result.value, result.confirmation, "unknown")
        return GraphExecutionResult(result.value, result.confirmation, "resumed", state)
