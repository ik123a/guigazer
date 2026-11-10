// Offline protocol test: minimal DOM and WebSocket stubs; never connects.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('dashboard consumes the server screenshot_b64 and report_html fields', () => {
  const nodes = new Map();
  const node = () => ({textContent: '', style: {}, classList: {add() {}, remove() {}}, addEventListener() {}, appendChild() {}});
  const handlers = {};
  let report = null;
  const document = {getElementById(id) { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); }};
  class WebSocket { addEventListener(name, fn) { handlers[name] = fn; } }
  const context = {document, WebSocket, location: {protocol: 'http:', hostname: 'localhost'}, console, setTimeout() {}, window: {open() {return {document: {write(html) {report = html;}, close() {}}};}}, DOMParser: class {parseFromString() {return {body: {firstChild: null}};}}};
  document.createElement = () => ({...node(), get innerHTML() {return this.textContent;}});
  vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '../frontend/app.js'), 'utf8'), context);
  handlers.message({data: JSON.stringify({type: 'step', screenshot_b64: 'OFFLINE'})});
  assert.equal(nodes.get('screenshot-img').src, 'data:image/png;base64,OFFLINE');
  handlers.message({data: JSON.stringify({type: 'audit_result', report_html: '<p>offline report</p>'})});
  assert.equal(report, '<p>offline report</p>');
});
