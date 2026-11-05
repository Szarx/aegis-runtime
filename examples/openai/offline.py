"""Synthetic JSON/SSE, parsed by the real SDK. Never a real Provider claim."""

import json

import httpx2

PRIVATE_TEXT = "synthetic-private-content-not-for-telemetry"


def response_body(api, model="offline-model", *, state="completed", usage=True):
    counts = {"input_tokens": 7, "output_tokens": 3, "total_tokens": 10} if api == "responses" else {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}
    if api == "responses":
        return {"id": "resp_offline_private", "object": "response", "created_at": 0, "model": model, "status": state, "error": {"code": "server_error", "message": PRIVATE_TEXT} if state == "failed" else None, "incomplete_details": {"reason": "max_output_tokens"} if state == "incomplete" else None, "output": [{"id": "msg_private", "type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": PRIVATE_TEXT, "annotations": []}]}], "parallel_tool_calls": False, "tool_choice": "auto", "tools": [], "usage": counts if usage else None}
    return {"id": "chatcmpl_offline_private", "object": "chat.completion", "created": 0, "model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": PRIVATE_TEXT, "refusal": None}, "finish_reason": "stop", "logprobs": None}], "usage": counts if usage else None}


class SyncBytes(httpx2.SyncByteStream):
    def __init__(self, parts):
        self.parts, self.reads, self.closes = parts, 0, 0
    def __iter__(self):
        for part in self.parts:
            self.reads += 1
            yield part
    def close(self):
        self.closes += 1


class AsyncBytes(httpx2.AsyncByteStream):
    def __init__(self, parts):
        self.parts, self.reads, self.closes = parts, 0, 0
    async def __aiter__(self):
        for part in self.parts:
            self.reads += 1
            yield part
    async def aclose(self):
        self.closes += 1


class Fixture:
    def __init__(self, *, asynchronous=False, state="completed", usage=True, http_errors=0, stream_error=False, terminal=True):
        self.asynchronous, self.state, self.usage = asynchronous, state, usage
        self.http_errors, self.stream_error, self.terminal = http_errors, stream_error, terminal
        self.requests, self.streams = [], []

    def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        if self.http_errors:
            self.http_errors -= 1
            return httpx2.Response(503, json={"error": {"message": PRIVATE_TEXT, "type": "server_error"}}, headers={"retry-after-ms": "1"})
        api = "responses" if request.url.path.endswith("responses") else "chat.completions"
        response = response_body(api, body["model"], state=self.state, usage=self.usage)
        if not body.get("stream"):
            return httpx2.Response(200, json=response)
        if api == "responses":
            events = [{"type": "response.output_text.delta", "sequence_number": 0, "item_id": "item_private", "output_index": 0, "content_index": 0, "delta": PRIVATE_TEXT, "logprobs": []}]
            if self.terminal:
                events.append({"type": "response." + self.state, "sequence_number": 1, "response": response})
        else:
            base = {"id": response["id"], "object": "chat.completion.chunk", "created": 0, "model": body["model"]}
            events = [{**base, "choices": [{"index": 0, "delta": {"content": PRIVATE_TEXT}, "finish_reason": None}], "usage": None}]
            if self.terminal:
                events.append({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": None})
            if self.usage and body.get("stream_options", {}).get("include_usage"):
                events.append({**base, "choices": [], "usage": response["usage"]})
        if self.stream_error:
            events.append({"error": {"message": PRIVATE_TEXT, "type": "server_error"}})
        parts = [("data: " + json.dumps(event) + "\n\n").encode() for event in events] + [b"data: [DONE]\n\n"]
        stream = (AsyncBytes if self.asynchronous else SyncBytes)(parts)
        self.streams.append(stream)
        return httpx2.Response(200, stream=stream, headers={"content-type": "text/event-stream"})

    def http_client(self):
        cls = httpx2.AsyncClient if self.asynchronous else httpx2.Client
        return cls(transport=httpx2.MockTransport(self), trust_env=False)
