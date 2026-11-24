"""Fetch the exact public upstream Inspector sources for container proof only."""
import hashlib,json,pathlib,sys,urllib.request
root=pathlib.Path(__file__).resolve().parents[1];pin=json.loads((root/'lab/inspector-pin.json').read_text());context=pathlib.Path(sys.argv[1]);target=context/'lab/vendor/inspector'
for entry in pin['files']:
 path=entry['path'];data=urllib.request.urlopen('https://raw.githubusercontent.com/'+pin['repository']+'/'+pin['commit']+'/'+path,timeout=30).read()
 assert len(data)<128000 and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==entry['git_blob_sha1'],path
 dest=target/path.removeprefix('automation_inspector/');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
print(json.dumps({'commit':pin['commit'],'verified_source_files':len(pin['files']),'scope':'lab_only_not_production_payload'}))
