#!/usr/local/bin/python3
"""Fixture only, refuses all app operations except the exact published install."""
import json,sys
from pathlib import Path
args=sys.argv[1:];state_path=Path('/tmp/recovery-ha.json');value=json.loads(state_path.read_text())
with open('/tmp/recovery-ha-calls.jsonl','a') as out:out.write(json.dumps(args)+'\n')
slug='local_hads_next_practical'
if args==['apps','--help']:pass
elif args==['apps','--raw-json']:
    row={'slug':slug,'version':value['version'],'state':value['state']}
    print(json.dumps({'result':'ok','data':{'addons':([row] if value['installed'] else [])+[{'slug':'unrelated','state':'started'}]}}))
elif args==['store','reload']:pass
elif args==['apps','install',slug]:
    assert not value['installed'];value.update(installed=True,version='1.0.0-rc3',state='stopped')
elif args==['apps','start',slug]:assert value['installed'];value['state']='started'
elif args==['apps','info',slug,'--raw-json']:print(json.dumps({'result':'ok','data':{'version':value['version'],'state':value['state']}}))
else:sys.exit(91)
state_path.write_text(json.dumps(value))
