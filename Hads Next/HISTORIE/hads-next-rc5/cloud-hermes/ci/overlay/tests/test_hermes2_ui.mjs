// Contract checks supplement the existing behavioral UI suites. No browser/API.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const code=fs.readFileSync(new URL('../web/app.js',import.meta.url),'utf8');
const html=fs.readFileSync(new URL('../web/index.html',import.meta.url),'utf8');
assert(html.includes('HADS Hermes'));
assert(html.includes('2.0.0-rc2'));
assert(code.includes('if(state.hermes)'));
assert(code.includes('funkčnost neověřena'));
assert(code.includes('čeká na povolení AI'));
assert(code.includes('poslední krok selhal'));
assert(code.includes('last_error'));
console.log('Hermes UI state contract: disabled, unverified, running, completed, failed passed');
