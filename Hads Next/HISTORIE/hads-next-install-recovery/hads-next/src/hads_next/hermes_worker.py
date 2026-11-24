"""Original pinned Hermes native loop, confined before any model processing."""
import contextlib
import ctypes
import io
import json
import os
from pathlib import Path
import socket
import sys


def confinement_probe():
    import subprocess
    for path in ('/etc/passwd','/data/options.json','/proc/1/environ','/app/hads_next/repair.py'):
        try:Path(path).read_bytes()
        except (FileNotFoundError,PermissionError):pass
        else:raise RuntimeError('Forbidden host file visible')
    for family in (socket.AF_INET,socket.AF_INET6,socket.AF_UNIX):
        try:socket.socket(family)
        except PermissionError:pass
        else:raise RuntimeError('Socket creation permitted')
    for operation in (os.fork,lambda:os.setuid(0),lambda:os.chroot('/..'),
                      lambda:subprocess.run([sys.executable,'-c','pass'])):
        try:operation()
        except PermissionError:pass
        else:raise RuntimeError('Execution or privilege escape permitted')


def run(payload):
    from .hermes_sandbox import confine, seal_filesystem
    # If launcher dies, its child must not survive as an abandoned investigator.
    if ctypes.CDLL(None).prctl(1,9,0,0,0)!=0 or os.getppid()==1:raise RuntimeError('Parent supervision failed')
    confine(os.environ['HERMES_HOME'],payload['port'])
    confinement_probe()
    import site
    sys.path[:]=['/app','/opt/hermes','/usr/local/lib/python3.14','/usr/local/lib/python3.14/lib-dynload']
    site.addsitedir('/opt/hermes/.venv/lib/python3.14/site-packages')
    sys.prefix=sys.exec_prefix='/opt/hermes/.venv'
    sys.executable='/opt/hermes/.venv/bin/python'
    pin='d923a5eb487a17c0a68801bba9ef0f56c81040a8'
    if Path('/opt/hermes/HADS_PINNED_REVISION').read_text().strip()!=pin:raise RuntimeError('Wrong Hermes revision')
    Path(os.environ['HERMES_HOME'],'config.yaml').write_text('tools:\n  tool_search:\n    enabled: off\n')
    from .worker_protocol import WorkerChannel
    inherited=socket.socket(fileno=int(os.environ['HADS_BROKER_FD']))
    # create_connection(timeout=...) leaves O_NONBLOCK on the inherited FD;
    # synchronize Python's timeout state before the first framed receive.
    inherited.settimeout(160)
    channel=WorkerChannel(inherited,payload['nonce'])
    from tools.registry import registry
    from run_agent import AIAgent
    import httpx

    class ModelTransport(httpx.BaseTransport):
        def handle_request(self,request):
            if request.method!='POST' or str(request.url)!='http://127.0.0.1:1/v1/chat/completions':
                return httpx.Response(403,json={'error':{'message':'Only metered model requests are supported'}},request=request)
            data=request.read()
            if len(data)>192000:raise RuntimeError('Model context limit reached')
            reply=channel.call('model',body=json.loads(data))
            return httpx.Response(200,json=reply,request=request)

    AIAgent._build_keepalive_http_client=staticmethod(lambda *a,**k:httpx.Client(transport=ModelTransport(),trust_env=False,timeout=60))
    for schema in payload['schemas']:
        name=schema['name']
        def handler(arguments,_name=name,**kwargs):
            try:return json.dumps(channel.call('read',name=_name,arguments=arguments),ensure_ascii=False)
            except Exception:return json.dumps({'status':'read_failed','detail_cs':'Broker čtení zastavil; nevytvářej neověřený závěr.'})
        registry.register(name=name,toolset='hads_broker',schema=schema,handler=handler)
    agent=AIAgent(base_url='http://127.0.0.1:1/v1',api_key='broker-only-not-a-provider-key',
        provider='custom',api_mode='chat_completions',model=payload['model'],enabled_toolsets=['hads_broker'],
        max_iterations=8,max_tokens=1024,save_trajectories=False,quiet_mode=True,skip_memory=True,
        skip_context_files=True,skip_background_review=True,checkpoints_enabled=False,run_budget_seconds=150)
    try:
        if {x['function']['name'] for x in agent.tools}!={x['name'] for x in payload['schemas']}:
            raise RuntimeError('Unexpected upstream tool capability')
        agent.compression_enabled=False;agent._disable_streaming=True;agent._skip_mcp_refresh=True
        agent._api_max_retries=1;agent._auto_recovery_cycles=0;agent._persist_disabled=True
        agent._try_recover_primary_transport=lambda *a,**k:False
        agent._try_activate_fallback=lambda *a,**k:False
        wire_errors=[]
        def capture(original):
            def call(*args,**kwargs):
                try:return original(*args,**kwargs)
                except Exception as error:
                    tb=error.__traceback__;frames=[]
                    while tb:
                        frames.append(Path(tb.tb_frame.f_code.co_filename).name+':'+str(tb.tb_lineno));tb=tb.tb_next
                    wire_errors.append({'type':type(error).__name__,'errno':getattr(error,'errno',None),'at':frames[-8:]})
                    raise
            return call
        for name in ('_interruptible_api_call','_interruptible_streaming_api_call'):
            setattr(agent,name,capture(getattr(agent,name)))
        seal_filesystem()
        try:Path('write-canary').write_text('forbidden')
        except PermissionError:pass
        else:raise RuntimeError('Inference filesystem seal failed')
        if payload.get('probe_only') is True:
            import resource
            return {'completed':True,'probe_only':True,'engine':'NousResearch/hermes-agent','revision':pin,
                'native_agent_loaded':True,'model_calls':0,'isolation_verified':True,'uid':os.geteuid(),
                'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'execution_authority':'none'}
        result=agent.run_conversation(payload['prompt'])
        if not isinstance(result,dict) or result.get('completed') is not True:
            return {'completed':False,'error':'native_loop_incomplete','wire_errors':wire_errors[-2:],
                'native_api_calls':result.get('api_calls') if isinstance(result,dict) else None,
                'result_keys':sorted(result) if isinstance(result,dict) else [],'isolation_verified':True}
        import resource
        return {'completed':True,'engine':'NousResearch/hermes-agent','revision':pin,
            'final_response':result.get('final_response',''),'isolation_verified':True,
            'uid':os.geteuid(),'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            'execution_authority':'none'}
    finally:agent.close()


if __name__=='__main__':
    try:
        raw=sys.stdin.buffer.read(128001)
        if len(raw)>128000:raise ValueError('Worker input too large')
        class Sink(io.TextIOBase):
            def write(self,value):return len(value)
        with contextlib.redirect_stdout(Sink()),contextlib.redirect_stderr(Sink()):
            result=run(json.loads(raw))
    except BaseException as error:
        frames=[];tb=error.__traceback__
        while tb:
            frames.append(Path(tb.tb_frame.f_code.co_filename).name+':'+str(tb.tb_lineno));tb=tb.tb_next
        result={'completed':False,'error':type(error).__name__,'at':frames[-5:]}
    print(json.dumps(result,ensure_ascii=False))
