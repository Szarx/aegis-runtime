"""A slow synthetic agent for observing activity and collection health."""
import argparse
import os
import time
import aegis

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--collector', default='http://127.0.0.1:8000')
parser.add_argument('--seconds', type=int, default=60)
args = parser.parse_args()
if not 1 <= args.seconds <= 300:
    parser.error('seconds must be 1..300')
token = os.environ.get('AEGIS_API_TOKEN')
sdk = aegis.init('health-example', endpoint=args.collector + '/v1/traces',
                 headers={'Authorization': 'Bearer ' + token} if token else None)
sdk.start_health_reporting(args.collector + '/v1/health', token=token)

@aegis.tool
def synthetic_work():
    time.sleep(args.seconds)

@aegis.observe
def run():
    synthetic_work()

try:
    print('Synthetic work started. Open Dashboard /#/health.', flush=True)
    run()
finally:
    sdk.flush()
    sdk.shutdown()
