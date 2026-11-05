"""Explicit integration choices, kept outside the existing application."""

import aegis
from aegis.langgraph import observe_graph
from aegis.openai import wrap_openai
from aegis_policy import Policy, Rule
from aegis_runtime import Runtime
from .application import build_agent as original


def build_agent(client, lookup_order, *, asynchronous=False, mode='observe'):
    if mode not in ('observe','allow','deny'):raise ValueError('invalid integration mode')
    client=wrap_openai(client,provider='deepseek')
    if mode=='observe':
        tool=aegis.tool(lookup_order,permission='orders.read')
    else:
        policy=Policy('recipe-v1',(Rule('order-access',mode,('order-agent',),('lookup_order',),('orders.read',)),))
        tool=Runtime(policy=policy,subject='order-agent').tool(lookup_order,permission='orders.read')
    # Wrapping occurs before StructuredTool derives the callable's schema.
    graph=original(client,tool,asynchronous=asynchronous)
    return observe_graph(graph,name='existing-order-agent')
