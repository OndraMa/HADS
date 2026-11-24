"""Bounded JSON framing over an inherited connected descriptor, never pickle."""
import json
import struct
import threading

MAX_FRAME=256*1024


def receive(channel):
    def exact(size):
        data=bytearray()
        while len(data)<size:
            part=channel.recv(size-len(data))
            if not part:raise EOFError('RPC channel closed')
            data.extend(part)
        return bytes(data)
    size=struct.unpack('!I',exact(4))[0]
    if not 0<size<=MAX_FRAME:raise ValueError('RPC frame exceeds limit')
    result=json.loads(exact(size))
    if not isinstance(result,dict):raise ValueError('RPC object required')
    return result


def send(channel,value):
    raw=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    if not 0<len(raw)<=MAX_FRAME:raise ValueError('RPC frame exceeds limit')
    channel.sendall(struct.pack('!I',len(raw))+raw)


class WorkerChannel:
    def __init__(self,channel,nonce):
        self.channel,self.nonce,self.lock=channel,nonce,threading.Lock()

    def call(self,kind,**payload):
        with self.lock:
            send(self.channel,{'nonce':self.nonce,'kind':kind,**payload})
            reply=receive(self.channel)
            if reply.get('ok') is not True:raise RuntimeError(reply.get('error','Broker odmítl požadavek.'))
            return reply['result']
