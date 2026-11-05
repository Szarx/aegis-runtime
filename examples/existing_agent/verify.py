"""Strict verification for this recipe's synthetic evidence, not arbitrary traces."""

from collections import Counter
import json


class VerificationError(ValueError):
    def __init__(self):super().__init__('existing agent verification failed')


def verify(rows, *, mode, counts, equivalent, diagnostics, flushed, closed):
    try:
        def require(value):
            if not value:raise VerificationError()
        require(mode in ('baseline','observe','allow','deny'))
        require(type(counts) is dict and all(type(value) is int for value in counts.values()))
        require(counts=={'model_calls':2,'tool_calls':0 if mode=='deny' else 1})
        require(type(equivalent) is bool and equivalent==(mode!='deny'))
        require(flushed is True and closed is True)
        if mode=='baseline':
            require(rows==[] and diagnostics is None)
            return {'trace_count':0,'span_count':0,'llm_duration_ms':[]}
        require(len(rows)==4 and len({row['trace_id'] for row in rows})==1)
        require(len({row['span_id'] for row in rows})==4)
        require(all(row['scope']['name']=='aegis' for row in rows))
        require(Counter(row['attributes']['gen_ai.operation.name'] for row in rows)==Counter(invoke_agent=1,chat=2,execute_tool=1))
        agent=next(row for row in rows if row['attributes']['gen_ai.operation.name']=='invoke_agent')
        require(agent['parent_span_id'] is None)
        require(all(row['parent_span_id']==agent['span_id'] for row in rows if row is not agent))
        for row in rows:
            require(type(row['start_time_unix_nano']) is int and type(row['end_time_unix_nano']) is int)
            require(0<row['start_time_unix_nano']<=row['end_time_unix_nano'])
            require(row['trace_id']!='0'*32 and len(row['trace_id'])==32 and int(row['trace_id'],16)>0)
            require(len(row['span_id'])==16 and int(row['span_id'],16)>0)
        models=[row for row in rows if row['attributes']['gen_ai.operation.name']=='chat']
        require(all(type(row['attributes']['gen_ai.usage.input_tokens']) is int and type(row['attributes']['gen_ai.usage.output_tokens']) is int
            and row['attributes']['gen_ai.usage.input_tokens']==7 and row['attributes']['gen_ai.usage.output_tokens']==3
            and row['attributes']['gen_ai.provider.name']=='deepseek' and row['kind']=='CLIENT' and row['status']=='UNSET' for row in models))
        tool=next(row for row in rows if row['attributes']['gen_ai.operation.name']=='execute_tool')
        if mode in ('allow','deny'):
            require(tool['attributes']['aegis.decision.effect']==mode)
            require(tool['attributes']['aegis.action.outcome']==('denied' if mode=='deny' else 'completed'))
        require(tool['status']==('ERROR' if mode=='deny' else 'UNSET'))
        require(diagnostics['accepted_spans']==diagnostics['exported_spans']==4)
        require(all(type(value) is int for value in diagnostics.values()))
        require(all(diagnostics[key]==0 for key in ('failed_spans','dropped_spans','pending_spans','export_failures','instrumentation_failures')))
        # These sentinels are synthetic private data supplied by the offline fixture.
        require(all(value not in json.dumps(rows) for value in ('demo-order','private-tool-id','synthetic-only-key','private-content')))
        return {'trace_count':1,'span_count':4,'llm_duration_ms':[
            round((row['end_time_unix_nano']-row['start_time_unix_nano'])/1_000_000,6) for row in models]}
    except Exception:
        raise VerificationError() from None
