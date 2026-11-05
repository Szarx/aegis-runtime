import json
from pathlib import Path
from tests.fixtures.application_config import ROOT


def write_managed_graph_application(folder,*,endpoint=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    (folder/'policy.json').write_bytes((ROOT/'examples/managed-graph/policy.json').read_bytes())
    doc=json.loads((ROOT/'examples/managed-graph/application.json').read_text())
    doc['telemetry']=dict(mode='jsonl',path='traces.jsonl') if endpoint is None else dict(mode='otlp',endpoint=endpoint,token_env='AEGIS_API_TOKEN',timeout_millis=1000)
    path=folder/'application.json';path.write_text(json.dumps(doc));return path
