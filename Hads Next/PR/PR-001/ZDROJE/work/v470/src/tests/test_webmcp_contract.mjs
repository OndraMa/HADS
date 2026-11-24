import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(here, '..', 'web', 'webmcp.js'), 'utf8');
const registered = [];
const requests = [];
const events = [];
let captainAllows = true;

const response = value => ({ok:true, status:200, async json(){return value;}});
const document = {
  modelContext: {async registerTool(tool, options){assert.ok(options.signal); registered.push(tool);}},
  querySelectorAll(){return [];},
  getElementById(id){
    if (id === 'main') return {dataset:{hadsPage:'captain'}};
    if (id === 'launch') return {disabled:true};
    return null;
  },
};
const window = {
  addEventListener(){},
  dispatchEvent(event){events.push(event);},
  async hadsRequestDecision(){return captainAllows;},
};
const sandbox = {
  document, window, navigator:{}, console, AbortController, AbortSignal,
  CustomEvent: class {constructor(type, init){this.type=type;this.detail=init?.detail;}},
  fetch: async (url, init={}) => {
    requests.push({url, init});
    if (String(url).includes('acceptance-snapshot')) return response({incidents:[],hads_version:'4.6.0'});
    return response({ok:true,url});
  },
  encodeURIComponent, setTimeout, clearTimeout,
};
vm.runInNewContext(source, sandbox, {filename:'webmcp.js'});
await new Promise(resolve => setTimeout(resolve, 0));

assert.equal(registered.length, 9);
assert.equal(window.HADSWebMCP.supported, true);
assert.equal(new Set(registered.map(tool => tool.name)).size, 9);
assert.ok(events.some(event => event.type === 'hads:webmcp-status' && event.detail.state === 'ready'));

for (const tool of registered) {
  assert.equal(tool.inputSchema.additionalProperties, false, `${tool.name} must reject unknown inputs`);
  assert.equal(typeof tool.execute, 'function');
}
const names = registered.map(tool => tool.name).join(' ');
for (const forbidden of ['approve','execute','restart','rollback','shell']) assert.equal(names.includes(forbidden), false);

const command = registered.find(tool => tool.name === 'hads_get_command_center');
await command.execute({}, {});
assert.equal(requests.at(-1).init.method, undefined);

const quick = registered.find(tool => tool.name === 'hads_run_quick_audit');
captainAllows = false;
const beforeCancel = requests.length;
const cancelled = await quick.execute({}, {});
assert.equal(cancelled.cancelled, true);
assert.equal(requests.length, beforeCancel);

captainAllows = true;
await quick.execute({}, {});
const diagnosticRequest = requests.at(-1);
assert.equal(diagnosticRequest.init.method, 'POST');
assert.equal(diagnosticRequest.init.headers['X-HADS4-Request'], 'captain');
assert.deepEqual(JSON.parse(diagnosticRequest.init.body), {source:'webmcp',confirmation:'CAPTAIN_CONFIRMED_IN_HADS_UI'});

const acceptance = registered.find(tool => tool.name === 'hads_get_acceptance_snapshot');
const snapshot = await acceptance.execute({}, {});
assert.equal(snapshot.matches, true);
assert.equal(snapshot.ui.page, 'captain');

console.log('WebMCP contract: 9 tools, confirmation gate and UI cross-check passed.');
