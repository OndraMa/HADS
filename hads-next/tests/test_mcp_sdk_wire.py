"""Real upstream MCP SDK server; transport proof, not an installed HA provider."""
import importlib.util
import socket
import threading
import time
import unittest
from hads_next.connector_transport import MCPConnection

@unittest.skipUnless(importlib.util.find_spec('mcp') and importlib.util.find_spec('uvicorn'),'MCP SDK integration dependencies are separate from the controller')
class RealSDK(unittest.TestCase):
    def test_real_sdk_streamable_http_json_and_sse_both_return_structured_tool_data(self):
        from mcp.server.fastmcp import FastMCP
        import uvicorn
        for json_response in (True,False):
            with self.subTest(json_response=json_response):
                listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
                mcp=FastMCP('real-upstream-sdk-fixture',host='127.0.0.1',port=port,stateless_http=True,json_response=json_response,log_level='ERROR')
                @mcp.tool()
                def read_fixture(entity_id:str)->dict:
                    return {'entity_id':entity_id,'state':'off'}
                server=uvicorn.Server(uvicorn.Config(mcp.streamable_http_app(),host='127.0.0.1',port=port,log_level='error',lifespan='on'))
                thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True);thread.start()
                try:
                    deadline=time.monotonic()+10
                    while not server.started and time.monotonic()<deadline:time.sleep(.02)
                    self.assertTrue(server.started)
                    client=MCPConnection('http://127.0.0.1:'+str(port)+'/mcp',allow_private_http=True)
                    catalog=client.discover();self.assertEqual([r['name'] for r in catalog],['read_fixture'])
                    self.assertEqual(client.call('read_fixture',{'entity_id':'light.fixture'}),{'entity_id':'light.fixture','state':'off'})
                finally:
                    server.should_exit=True;thread.join(5);listener.close()
                self.assertFalse(thread.is_alive())
