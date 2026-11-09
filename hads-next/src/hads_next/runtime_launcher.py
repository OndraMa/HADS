"""Small privileged launcher. Has no HA/model credentials or database API.

Started before controller drops privileges, with an explicit environment and
one inherited private control FD. Accepts no executable, filesystem path or
shell command. The child is always the fixed HADS Hermes worker.
"""
import ctypes
import json
import os
from pathlib import Path
import re
import socket
import select
import subprocess
import sys
import tempfile
import threading
import time

from .hermes_sandbox import private_home
from .worker_protocol import receive, send


def serve(fd):
    if os.geteuid()!=0:raise RuntimeError('Root launcher unavailable')
    if ctypes.CDLL(None).prctl(1,9,0,0,0)!=0:raise RuntimeError('Cannot supervise launcher parent')
    if ctypes.CDLL(None).prctl(38,1,0,0,0)!=0:raise RuntimeError('Cannot restrict launcher privileges')
    with socket.socket(fileno=fd) as control:
        send(control,{'ok':True,'kind':'ready'})
        while True:
            try:request=receive(control)
            except EOFError:return
            if request=={'kind':'stop'}:return
            if request=={'kind':'cancel'}:continue
            try:
                if set(request)!={'kind','port','nonce','model','prompt','schemas'} or request['kind']!='run':
                    raise ValueError('Invalid launcher request')
                if type(request['port']) is not int or not 1024<=request['port']<=65535:
                    raise ValueError('Invalid broker port')
                if not isinstance(request['nonce'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,64}',request['nonce']):
                    raise ValueError('Invalid session capability')
                if not isinstance(request['prompt'],str) or len(request['prompt'].encode())>48000:
                    raise ValueError('Invalid prompt size')
                if not isinstance(request['schemas'],list) or not 1<=len(request['schemas'])<=32:
                    raise ValueError('Invalid tool catalog')
                available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
                limit_file=Path('/sys/fs/cgroup/memory.max');used_file=Path('/sys/fs/cgroup/memory.current')
                if limit_file.exists() and used_file.exists() and limit_file.read_text().strip()!='max':
                    available=min(available,int(limit_file.read_text())-int(used_file.read_text()))
                if available<576*1024*1024:raise RuntimeError('Insufficient memory reserve for safe investigation')
                with private_home() as directory, socket.create_connection(('127.0.0.1',request['port']),timeout=5) as channel:
                    env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','PYTHONPATH':'/app',
                        'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','PYTHONUNBUFFERED':'1',
                        'HOME':'/tmp/'+directory.name,'HERMES_HOME':'/tmp/'+directory.name,
                        'HADS_BROKER_FD':str(channel.fileno()),'LD_LIBRARY_PATH':'/usr/local/lib',
                        'MALLOC_ARENA_MAX':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
                    env.update({'USER':'nobody','LOGNAME':'nobody','TMPDIR':'/tmp/'+directory.name})
                    with tempfile.TemporaryFile() as output:
                        with subprocess.Popen([sys.executable,'-m','hads_next.hermes_worker'],cwd='/',env=env,
                            stdin=subprocess.PIPE,stdout=output,stderr=subprocess.DEVNULL,
                            pass_fds=(channel.fileno(),)) as process:
                            process.stdin.write(json.dumps(request).encode());process.stdin.close()
                            deadline=time.monotonic()+175;cancelled=False
                            while process.poll() is None:
                                if time.monotonic()>deadline:
                                    process.kill();process.wait();raise RuntimeError('Worker wall-time limit reached')
                                if select.select([control],[],[],.1)[0]:
                                    command=receive(control)
                                    process.kill();process.wait()
                                    if command=={'kind':'stop'}:return
                                    if command!={'kind':'cancel'}:raise ValueError('Invalid active-worker control')
                                    cancelled=True;break
                        output.seek(0);raw=output.read(48001)
                        if len(raw)>48000:raise RuntimeError('Worker output too large')
                        if cancelled:result={'completed':False,'error':'worker_cancelled','exit_status':process.returncode}
                        elif process.returncode:result={'completed':False,'error':'worker_exit','exit_status':process.returncode}
                        else:result=json.loads(raw)
                send(control,{'ok':True,'result':result})
            except Exception as error:
                # No exception messages from SDK, socket or remote responses.
                send(control,{'ok':False,'error':'Hermes launcher: '+type(error).__name__})


class RuntimeLauncher:
    def __init__(self):
        if os.geteuid()!=0:raise RuntimeError('Hermes launcher must start before UID drop')
        self.channel,child=socket.socketpair()
        self._send_lock=threading.Lock();self._run_lock=threading.Lock();self._active=threading.Event()
        self.channel.settimeout(180)
        env={'PATH':'/usr/local/bin:/usr/bin:/bin','LANG':'C.UTF-8','PYTHONPATH':'/app',
             'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','HADS_LAUNCHER_FD':str(child.fileno())}
        try:
            self.process=subprocess.Popen([sys.executable,'-m','hads_next.runtime_launcher'],env=env,cwd='/',
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,pass_fds=(child.fileno(),))
        finally:child.close()
        self.channel.settimeout(5)
        if receive(self.channel)!={'ok':True,'kind':'ready'}:raise RuntimeError('Root launcher did not initialize')
        self.channel.settimeout(180)

    def run(self,*,port,nonce,model,prompt,schemas):
        with self._run_lock:
            try:
                with self._send_lock:
                    send(self.channel,{'kind':'run','port':port,'nonce':nonce,'model':model,'prompt':prompt,'schemas':schemas})
                    self._active.set()
                response=receive(self.channel)
            finally:self._active.clear()
        if response.get('ok') is not True:raise RuntimeError(response.get('error','Launcher failed'))
        return response['result']

    def cancel(self):
        with self._send_lock:
            if not self._active.is_set():return False
            send(self.channel,{'kind':'cancel'});return True

    def close(self):
        try:send(self.channel,{'kind':'stop'})
        except OSError:pass
        self.channel.close()
        try:self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:self.process.kill();self.process.wait()


if __name__=='__main__':serve(int(os.environ['HADS_LAUNCHER_FD']))
