"""Real LangGraph plus a strict, committed-response approval transport."""

import copy
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from aegis_runtime.approvals import ApprovalUnavailable
from aegis_runtime.langgraph_reviewed import ReviewedGraphTool
from aegis_runtime.reviewed_execution import BINDING
from tests.fixtures.reviewed import client, policy


class State(TypedDict, total=False):
    aegis_call: dict
    aegis_reviewed: dict


def gate(function, connection=None, **changes):
    return ReviewedGraphTool(function, **{**dict(client=connection or client(), policy=policy(), subject='demo-agent',
                                               permission='records.write', tool='write', tool_revision='impl-v1',
                                               graph_id='demo-graph', graph_revision='graph-v1', node_name='review',
                                               disclose_arguments=True), **changes})


def build(governed, saver=None):
    graph=StateGraph(State)
    graph.add_node('review',governed.node)
    graph.add_edge(START,'review');graph.add_edge('review',END)
    return graph.compile(checkpointer=saver if saver is not None else InMemorySaver())


def config(thread='demo-thread'):
    return {'configurable':{'thread_id':thread}}


def initial(arguments=None,call_id='1'*32):
    return {'aegis_call':{'call_id':call_id,'arguments':{} if arguments is None else arguments}}


class Transport:
    def __init__(self):
        self.records={};self.calls=[];self.lock=Lock();self.on_claim=lambda:None;self.fault=None;self.remaining_ms=200000

    def send(self,path,data,**kwargs):
        with self.lock:
            self.calls.append((path,copy.deepcopy(data)))
            now=datetime.now(timezone.utc)
            if path=='/api/v1/reviewed-actions':
                if data['action_id'] in self.records:
                    record=self.records[data['action_id']]
                    if any(record[key]!=value for key,value in data.items()):raise ApprovalUnavailable()
                else:
                    record={**copy.deepcopy(data),'status':'pending','created_at':now.isoformat(),
                            'expires_at':(now+timedelta(seconds=data['ttl_seconds'])).isoformat(),
                            'decided_at':None,'reviewer':None,'execution_state':'available','claim_id':None,
                            'executor':None,'claimed_at':None,'finished_at':None}
                    self.records[data['action_id']]=record
            else:
                record=self.records[path.split('/')[-2]]
                if path.endswith('/claim'):
                    if record['status']!='approved' or record['execution_state']!='available' or any(record[key]!=data[key] for key in BINDING):
                        raise ApprovalUnavailable()
                    record.update(execution_state='claimed',claim_id=data['claim_id'],executor='local-executor',claimed_at=now.isoformat())
                    self.on_claim()
                    if self.fault=='lost-claim':raise ApprovalUnavailable()
                    return {**copy.deepcopy(record),'remaining_ms':self.remaining_ms}
                record.update(execution_state=data['outcome'],finished_at=now.isoformat())
                if self.fault=='lost-complete':raise ApprovalUnavailable()
            return copy.deepcopy(record)

    def approve(self,ticket,status='approved'):
        self.records[ticket['action_id']].update(status=status,reviewer='local-reviewer',decided_at=datetime.now(timezone.utc).isoformat())
