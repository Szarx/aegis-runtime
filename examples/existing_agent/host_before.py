from .application import build_agent


def connect(client, lookup_order, *, asynchronous=False):
    return build_agent(client, lookup_order, asynchronous=asynchronous)
