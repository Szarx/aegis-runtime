import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def write_application(folder,*,endpoint=None,token_env='SYNTHETIC_TRACE_TOKEN'):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    (folder/'policy.json').write_bytes((ROOT/'examples/configured-agent/policy.json').read_bytes())
    document=json.loads((ROOT/'examples/configured-agent/application.json').read_text())
    document['telemetry']=dict(mode='jsonl',path='traces.jsonl') if endpoint is None else dict(mode='otlp',endpoint=endpoint,token_env=token_env,timeout_millis=1000)
    path=folder/'application.json';path.write_text(json.dumps(document));return path
