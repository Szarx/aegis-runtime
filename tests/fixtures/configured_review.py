import json
from pathlib import Path
from tests.fixtures.application_config import ROOT


def write_review_application(folder,*,endpoint=None):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    (folder/'policy.json').write_bytes((ROOT/'examples/configured-review/policy.json').read_bytes())
    document=json.loads((ROOT/'examples/configured-review/application.json').read_text())
    document['telemetry']=dict(mode='jsonl',path='traces.jsonl') if endpoint is None else dict(mode='otlp',endpoint=endpoint,token_env='AEGIS_API_TOKEN',timeout_millis=1000)
    path=folder/'application.json';path.write_text(json.dumps(document));return path
