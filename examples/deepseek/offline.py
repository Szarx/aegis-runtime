"""DeepSeek-shaped JSON/SSE, including usage on the last choices chunk."""

import json
import httpx2

from examples.openai.offline import Fixture as BaseFixture, SyncBytes, AsyncBytes, PRIVATE_TEXT


class Fixture(BaseFixture):
    def __call__(self, request):
        body = json.loads(request.content)
        if not request.url.path.endswith('/chat/completions'):
            return super().__call__(request)
        self.requests.append(body)
        if self.http_errors:
            self.http_errors -= 1
            return httpx2.Response(401, json={'error': {'message': PRIVATE_TEXT, 'type': 'authentication_error'}})
        counts = {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10, 'prompt_cache_hit_tokens': 0, 'prompt_cache_miss_tokens': 7}
        base = {'id': 'deepseek-private-response', 'created': 0, 'model': body['model'], 'system_fingerprint': PRIVATE_TEXT}
        tool = body.get('tool_choice') not in (None, 'none', 'auto')
        message = {'role': 'assistant', 'content': None if tool else PRIVATE_TEXT, 'reasoning_content': PRIVATE_TEXT}
        if tool:
            message['tool_calls'] = [{'id': 'private-tool-id', 'type': 'function', 'function': {'name': 'lookup_order', 'arguments': '{"order_id":"demo-order"}'}}]
        if not body.get('stream'):
            return httpx2.Response(200, json={**base, 'object':'chat.completion', 'choices':[{'index':0,'message':message,'finish_reason':'tool_calls' if tool else 'stop'}], 'usage':counts if self.usage else None})
        base['object'] = 'chat.completion.chunk'
        events = [{**base, 'choices':[{'index':0,'delta':{'content':PRIVATE_TEXT, 'reasoning_content':PRIVATE_TEXT},'finish_reason':None}]}]
        if self.terminal:
            events.append({**base,'choices':[{'index':0,'delta':{},'finish_reason':'stop'}], 'usage':counts if self.usage else None})
        if self.stream_error:
            events.append({'error':{'message':PRIVATE_TEXT,'type':'server_error'}})
        parts = [('data: ' + json.dumps(event) + '\n\n').encode() for event in events] + [b'data: [DONE]\n\n']
        stream = (AsyncBytes if self.asynchronous else SyncBytes)(parts)
        self.streams.append(stream)
        return httpx2.Response(200, stream=stream, headers={'content-type':'text/event-stream'})
