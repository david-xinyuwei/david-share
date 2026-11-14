const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, '..', 'static', 'app.js'), 'utf8');
const start = source.indexOf('  // ---- Model connection:');
const end = source.indexOf('  // Non-OK responses', start);
assert.ok(start >= 0 && end > start, 'Connection event handlers must be found');
const connectionCode = source.slice(start, end);
const key = 's3d.aoai';
const sample = { endpoint: 'https://test-resource.openai.azure.com', deployment: 'test-deployment', key: 'dummy-key-for-local-tests-only' };

function harness(store = new Map(), me = { deployment: 'host', byok_required: false }) {
  const elements = new Map(), downloads = [], blobs = new Map(), timers = [];
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', title: '', dataset: {}, disabled: false, files: [], events: {},
      classList: { toggle() {}, add() {}, remove() {} },
      addEventListener(name, callback) { this.events[name] = callback; },
      querySelectorAll() { return [...elements.values()]; },
      appendChild() {},
      showModal() { this.open = true; },
      close() { this.open = false; },
      click() { return this.events.click?.(); },
    });
    return elements.get(id);
  }
  const storage = {
    getItem: (name) => store.get(name) ?? null,
    setItem: (name, value) => store.set(name, value),
    removeItem: (name) => store.delete(name),
  };
  const context = vm.createContext({
    $: element, localStorage: storage, t: (name) => name, state: { me },
    window: { confirm: () => false },
    document: { createElement: () => element('created') },
    URL: {
      createObjectURL(blob) { const url = `blob:test-${blobs.size}`; blobs.set(url, blob); return url; },
      revokeObjectURL(url) { blobs.delete(url); },
    },
    Blob, setTimeout: (callback) => timers.push(callback),
    download: (url, name) => downloads.push({ blob: blobs.get(url), name }),
    fetch: () => { throw new Error('Persistence must not send credentials to the server'); },
  });
  vm.runInContext(connectionCode, context);
  context.fillConnForm(sample);
  return {
    context, store, storage, elements, downloads, timers, element,
    click: (id) => element(id).events.click(),
    async importFile(text, size = Buffer.byteLength(text)) {
      element('connImportFile').files = [{ size, text: async () => text }];
      await element('connImportFile').events.change();
    },
    status: () => element('connStatus').textContent,
    ok: () => element('connStatus').dataset.ok,
  };
}

test('existing browser connection survives initialization and reopening', () => {
  const store = new Map([[key, JSON.stringify(sample)], ['s3d.lang', 'en']]);
  const h = harness(store);
  h.context.openConnDialog();
  assert.equal(h.element('connEndpoint').value, sample.endpoint);
  assert.equal(h.element('connKey').value, sample.key);
  assert.equal(store.get(key), JSON.stringify(sample));
  assert.equal(h.context.connHeaders()['X-AOAI-Key'], sample.key);
});

test('host-managed mode requires no browser key and only displays server connection metadata', () => {
  const store = new Map([[key, JSON.stringify(sample)]]);
  const me = {
    deployment: 'gpt-6-astra',
    endpoint: 'https://host-resource.openai.azure.com',
    endpoint_host: 'host-resource.openai.azure.com',
    host_auth: 'entra_id',
    host_connection_for_all: true,
    byok_required: true,
  };
  const h = harness(store, me);
  h.storage.getItem = () => { throw new Error('Host mode must not read browser credentials'); };
  assert.equal(Object.keys(h.context.connHeaders()).length, 0);
  assert.equal(h.context.connectionReady(), true);
  h.context.openConnDialog();
  assert.equal(h.element('connEndpoint').value, me.endpoint);
  assert.equal(h.element('connDeployment').value, me.deployment);
  assert.equal(h.element('connKey').value, 'conn_managed_key');
  assert.equal(h.element('connEndpointValue').textContent, me.endpoint);
  assert.equal(h.element('connDeploymentValue').textContent, me.deployment);
  assert.equal(h.element('connKeyValue').textContent, 'conn_managed_key');
  assert.equal(h.element('connEndpoint').readOnly, true);
  assert.equal(h.element('connDeployment').readOnly, true);
  assert.equal(h.element('connKey').readOnly, true);
  assert.equal(h.element('connKey').type, 'text');
  assert.equal(store.get(key), JSON.stringify(sample));
});

test('save persists all fields, downloads password.txt, and survives a new page context', async () => {
  const h = harness();
  h.element('connEndpoint').value = ` ${sample.endpoint}/// `;
  await h.click('connSave');
  assert.deepEqual(JSON.parse(h.store.get(key)), sample);
  assert.equal(h.downloads.length, 1);
  assert.equal(h.downloads[0].name, 'password.txt');
  assert.deepEqual(JSON.parse(await h.downloads[0].blob.text()), sample);
  assert.equal(h.ok(), 'true');
  assert.match(h.status(), /conn_backup_download/);
  const reloaded = harness(h.store);
  reloaded.context.openConnDialog();
  assert.equal(reloaded.element('connKey').value, sample.key);
  h.timers.forEach((callback) => callback());
});

test('native file picker writes and closes the chosen file before reporting saved', async () => {
  const h = harness();
  const calls = [];
  h.context.window.showSaveFilePicker = async (options) => {
    assert.equal(options.suggestedName, 'password.txt');
    return { createWritable: async () => ({
      write: async (text) => calls.push(JSON.parse(text)),
      close: async () => calls.push('closed'),
      abort: async () => calls.push('aborted'),
    }) };
  };
  await h.click('connSave');
  assert.deepEqual(calls, [sample, 'closed']);
  assert.match(h.status(), /conn_backup_saved/);
  assert.equal(h.downloads.length, 0);
});

test('cancelling file backup keeps the browser settings and reports the missing backup', async () => {
  const h = harness();
  h.context.window.showSaveFilePicker = async () => { throw Object.assign(new Error(), { name: 'AbortError' }); };
  await h.click('connSave');
  assert.deepEqual(JSON.parse(h.store.get(key)), sample);
  assert.match(h.status(), /conn_saved.*conn_backup_cancelled/);
  assert.equal(h.ok(), 'false');
  assert.equal(h.element('connSave').disabled, false);
});

test('write or close failures abort the file and never report successful backup', async () => {
  for (const phase of ['write', 'close']) {
    const h = harness();
    let aborted = false;
    h.context.window.showSaveFilePicker = async () => ({ createWritable: async () => ({
      write: async () => { if (phase === 'write') throw new Error(sample.key); },
      close: async () => { if (phase === 'close') throw new Error(sample.key); },
      abort: async () => { aborted = true; },
    }) });
    await h.click('connSave');
    assert.ok(aborted);
    assert.match(h.status(), /conn_saved.*conn_backup_failed/);
    assert.ok(!h.status().includes(sample.key));
    assert.equal(h.ok(), 'false');
  }
});

test('browser storage failures still offer a file backup and report partial failure', async () => {
  const h = harness(new Map([[key, JSON.stringify(sample)]]));
  h.element('connDeployment').value = 'new-deployment';
  h.storage.setItem = () => { throw new Error('QuotaExceededError'); };
  await h.click('connSave');
  assert.deepEqual(JSON.parse(h.store.get(key)), sample);
  assert.equal(JSON.parse(await h.downloads[0].blob.text()).deployment, 'new-deployment');
  assert.match(h.status(), /conn_save_failed.*conn_backup_download/);
  assert.equal(h.ok(), 'false');
});

test('password import restores browser settings without a network request or another download', async () => {
  const h = harness();
  await h.importFile('\uFEFF' + JSON.stringify(sample));
  assert.deepEqual(JSON.parse(h.store.get(key)), sample);
  assert.equal(h.element('connKey').value, sample.key);
  assert.equal(h.status(), 'conn_imported');
  assert.equal(h.element('connImportFile').value, '');
  assert.equal(h.downloads.length, 0);
});

test('malformed, oversized, or invalid imports never overwrite the previous connection', async () => {
  for (const text of ['not-json', 'null', '{}', JSON.stringify({ ...sample, endpoint: 'http://localhost' }),
    JSON.stringify({ ...sample, key: 'short' }), JSON.stringify({ ...sample, deployment: null }),
    JSON.stringify(sample) + ' '.repeat(16384)]) {
    const h = harness(new Map([[key, JSON.stringify(sample)]]));
    await h.importFile(text);
    assert.equal(h.store.get(key), JSON.stringify(sample));
    assert.equal(h.status(), 'conn_import_invalid');
    assert.equal(h.ok(), 'false');
    assert.equal(h.element('connImport').disabled, false);
  }
});

test('import storage error is explicit and preserves previous connection', async () => {
  const h = harness(new Map([[key, JSON.stringify(sample)]]));
  h.storage.setItem = () => { throw new Error('Storage blocked'); };
  await h.importFile(JSON.stringify({ ...sample, deployment: 'replacement' }));
  assert.deepEqual(JSON.parse(h.store.get(key)), sample);
  assert.equal(h.status(), 'conn_import_failed');
});

test('clear requires confirmation and only removes the connection storage key', async () => {
  const h = harness(new Map([[key, JSON.stringify(sample)], ['s3d.lang', 'en']]));
  await h.click('connClear');
  assert.equal(h.store.get(key), JSON.stringify(sample));
  h.context.window.confirm = () => true;
  await h.click('connClear');
  assert.equal(h.store.has(key), false);
  assert.equal(h.store.get('s3d.lang'), 'en');
  assert.equal(h.element('connKey').value, '');
});

test('clear failure keeps form values and reports an error', async () => {
  const h = harness(new Map([[key, JSON.stringify(sample)]]));
  h.context.window.confirm = () => true;
  h.storage.removeItem = () => { throw new Error('Storage blocked'); };
  await h.click('connClear');
  assert.equal(h.element('connKey').value, sample.key);
  assert.equal(h.status(), 'conn_clear_failed');
});

test('unreadable storage and corrupt saved values are not deleted or used as host defaults', () => {
  for (const raw of ['invalid-json', 'null', JSON.stringify({ ...sample, key: false })]) {
    const h = harness(new Map([[key, raw]]));
    assert.throws(() => h.context.connHeaders(), /conn_read_failed/);
    assert.equal(h.context.connectionReady(), false);
    assert.equal(h.status(), 'conn_read_failed');
    assert.equal(h.store.get(key), raw);
  }
  const h = harness();
  h.storage.getItem = () => { throw new Error('Storage blocked'); };
  assert.equal(h.context.connectionReady(), false);
  assert.equal(h.status(), 'conn_read_failed');
});

test('invalid save neither persists nor downloads, and legacy deployment remains optional', async () => {
  const h = harness();
  h.element('connKey').value = '';
  await h.click('connSave');
  assert.equal(h.store.size, 0);
  assert.equal(h.downloads.length, 0);
  assert.equal(h.status(), 'conn_invalid');
  assert.equal(h.context.normalizeConnection({ endpoint: sample.endpoint, key: sample.key }).deployment, '');
});

test('frontend validation respects the server key and deployment length boundaries', () => {
  const h = harness();
  for (const length of [16, 256]) {
    assert.equal(h.context.normalizeConnection({ ...sample, key: 'k'.repeat(length) }).key.length, length);
  }
  for (const length of [15, 257]) {
    assert.throws(() => h.context.normalizeConnection({ ...sample, key: 'k'.repeat(length) }), /conn_invalid/);
  }
  assert.equal(h.context.normalizeConnection({ ...sample, deployment: 'd'.repeat(64) }).deployment.length, 64);
  assert.throws(() => h.context.normalizeConnection({ ...sample, deployment: 'd'.repeat(65) }), /conn_invalid/);
  for (const suffix of ['openai.azure.com', 'cognitiveservices.azure.com', 'services.ai.azure.com']) {
    const endpoint = `https://test-resource.${suffix}`;
    assert.equal(h.context.normalizeConnection({ ...sample, endpoint }).endpoint, endpoint);
  }
});

test('import accepts the exact 16 KB limit and rejects the next byte', async () => {
  const text = JSON.stringify(sample).padEnd(16 * 1024, ' ');
  const h = harness();
  await h.importFile(text);
  assert.equal(h.status(), 'conn_imported');
  await h.importFile(text + ' ');
  assert.equal(h.status(), 'conn_import_invalid');
  assert.deepEqual(JSON.parse(h.store.get(key)), sample);
});

test('save locks conflicting actions until the native file operation completes', async () => {
  const h = harness();
  let finish;
  h.context.window.showSaveFilePicker = () => new Promise((resolve) => { finish = resolve; });
  const saving = h.click('connSave');
  assert.equal(h.element('connClear').disabled, true);
  let prevented = false;
  h.element('connDialog').events.cancel({ preventDefault: () => { prevented = true; } });
  assert.ok(prevented);
  finish({ createWritable: async () => ({ write: async () => {}, close: async () => {} }) });
  await saving;
  assert.equal(h.element('connClear').disabled, false);
});
