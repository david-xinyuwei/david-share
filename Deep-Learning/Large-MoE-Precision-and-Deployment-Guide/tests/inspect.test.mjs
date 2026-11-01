import assert from 'node:assert/strict';
import {access, readFile} from 'node:fs/promises';
import test from 'node:test';
import {refreshSnapshot, summarizeSnapshot, tensorPayload} from '../tools/inspect.mjs';

const snapshot = JSON.parse(await readFile(new URL('../data/model-evidence.json', import.meta.url), 'utf8'));

test('covers all model variants and keeps the bilingual matrix and links aligned', async () => {
  assert.equal(snapshot.models.length, 6);
  for (const family of ['Muse Spark Open', 'Nemotron 3 Ultra', 'Inkling']) {
    assert.deepEqual(snapshot.models.filter(model => model.family === family).map(model => model.variant).sort(), ['BF16', 'NVFP4']);
  }
  assert.equal(snapshot.fp8_releases.length, 3);
  const inkling = snapshot.fp8_releases.find(model => model.model_id === 'RedHatAI/Inkling-FP8-dynamic');
  assert.ok(inkling.ignore.includes('re:.*\\.attn\\..*'));
  assert.equal(inkling.kv_cache_scheme, null);
  const matrices = [];
  for (const filename of ['README_CN.md', 'README.md', 'VALIDATION_CN.md', 'VALIDATION.md']) {
    const source = new URL(`../${filename}`, import.meta.url);
    const markdown = await readFile(source, 'utf8');
    for (const match of markdown.matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) {
      const target = match[1].split('#')[0];
      if (target && !/^[a-z]+:/i.test(target)) await access(new URL(target, source));
    }
    if (filename.startsWith('README')) {
      const lines = markdown.split(/\r?\n/);
      const start = lines.findIndex(line => line.startsWith('| 类别与组件/执行条件') || line.startsWith('| Category and component/execution condition'));
      assert.ok(start >= 0, `Missing component matrix in ${filename}`);
      const rows = [];
      for (let index = start; index < lines.length && lines[index].startsWith('|'); index++) rows.push(lines[index].split('|').slice(1, -1));
      assert.equal(rows.length, 27);
      assert.ok(rows.every(row => row.length === 10));
      matrices.push(rows.map(row => row.map(cell => Array.from(cell.matchAll(/\[([A-Z]\d+)\]/g), match => match[1]))));
    }
  }
  assert.deepEqual(matrices[0], matrices[1]);
});

test('counts packed bytes rather than interpreting U8 elements as original parameters', () => {
  assert.deepEqual(tensorPayload({U8: 8, F8_E4M3: 1, BF16: 2, F32: 1}), {bytes: 17, elements: 12});
});

test('reproduces the six observed tensor payloads without claiming peak VRAM', () => {
  const result = summarizeSnapshot(snapshot);
  assert.deepEqual(result.models.map(model => model.tensor_payload_bytes), [
    1644333137920, 533010718720, 1121049257984,
    320071411808, 1904755280148, 592005369312,
  ]);
  assert.equal(result.inference_status, 'NOT_RUN');
  assert.equal(result.models[2].metadata_total_matches, false);
});

test('retains a denied configuration read rather than fabricating Muse module precision', () => {
  const config = snapshot.quantization_configs.find(entry => entry.model_id.startsWith('meta-models/'));
  assert.equal(config.http_status, 401);
  assert.equal(config.inspected, false);
});

test('distinguishes Nemotron router exclusions from NVFP4 expert rules', () => {
  const config = snapshot.quantization_configs.find(entry => entry.model_id.startsWith('nvidia/'));
  assert.ok(config.excluded_examples.includes('backbone.layers.1.mixer.gate'));
  assert.equal(config.representative_rules['backbone.layers.1.mixer.experts.0.down_proj'].quant_algo, 'NVFP4');
  assert.equal(config.representative_rules['backbone.layers.1.mixer.shared_experts.down_proj'].quant_algo, 'FP8');
});

test('unknown dtype cannot silently produce a smaller capacity estimate', () => {
  assert.throws(() => tensorPayload({UNKNOWN: 32}), /Unknown tensor dtype/);
});

test('fresh metadata replaces the revision and cannot inherit old configuration verification', async () => {
  const fixture = {...snapshot, models: [snapshot.models[0]]};
  const changedRevision = '1'.repeat(40);
  const result = await refreshSnapshot(fixture, async () => ({ok: true, json: async () => ({
    id: fixture.models[0].model_id, sha: changedRevision, gated: 'manual', safetensors: {parameters: {BF16: 10}, total: 10},
  })}));
  assert.equal(summarizeSnapshot(result).models[0].tensor_payload_bytes, 20);
  assert.equal(result.models[0].revision, changedRevision);
  assert.deepEqual(result.quantization_configs, []);
});

test('a failed public read is an error, not reuse of the saved snapshot', async () => {
  await assert.rejects(refreshSnapshot({...snapshot, models: [snapshot.models[0]]}, async () => ({ok: false, status: 403})), /HTTP 403/);
});