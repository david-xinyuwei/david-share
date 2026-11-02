import assert from 'node:assert/strict';
import {readFile, readdir} from 'node:fs/promises';
import test from 'node:test';
import {COMPONENT_ORDER, crossCheck, summarizeCensus} from '../tools/census.mjs';

const evidence = JSON.parse(await readFile(new URL('../data/model-evidence.json', import.meta.url), 'utf8'));
const censusDir = new URL('../data/tensor-census/', import.meta.url);
const censusFiles = (await readdir(censusDir)).filter(name => name.endsWith('.json')).sort();

test('observed safetensors headers reproduce the calculated tensor payload byte-for-byte', async () => {
  assert.deepEqual(censusFiles, ['inkling_bf16_828496ee.json', 'nemotron3ultra_bf16_77df655d.json']);
  for (const name of censusFiles) {
    const census = JSON.parse(await readFile(new URL(name, censusDir), 'utf8'));
    const summary = summarizeCensus(census);
    const model = evidence.models.find(m => summary.snapshot_dir.includes(m.revision));
    assert.ok(model, `${name} must point at a revision recorded in model-evidence.json`);
    const check = crossCheck(summary, model);
    assert.equal(check.match, true, `${name}: header bytes ${check.observed_header_bytes} != API payload ${check.calculated_from_api_bytes}`);
    assert.equal(summary.evidence_type, 'OBSERVED_SAFETENSORS_HEADER');
    assert.deepEqual(summary.unmatched_patterns, [], `${name} has unclassified tensor names`);
  }
});

test('Nemotron BF16 census: router gate carries BF16 weights and F32 correction bias; experts dominate', async () => {
  const census = JSON.parse(await readFile(new URL('nemotron3ultra_bf16_77df655d.json', censusDir), 'utf8'));
  const rows = Object.fromEntries(summarizeCensus(census).rows.map(r => [r.component, r]));
  assert.deepEqual(Object.keys(rows.router_gate.dtypes).sort(), ['BF16', 'F32']);
  assert.equal(rows.router_gate.dtypes.F32.tensors, 48);
  assert.match(rows.router_gate.example.F32.name, /gate\.e_score_correction_bias$/);
  assert.equal(rows.routed_expert.tensors, 49152);
  assert.ok(rows.routed_expert.share_percent > 91 && rows.routed_expert.share_percent < 93);
  assert.ok(rows.mamba_proj.GB > 40 && rows.mamba_proj.GB < 41);
  assert.equal(Object.keys(rows.mamba_conv_state.dtypes).join(), 'BF16');
  assert.ok(rows.mtp.GB > 22 && rows.mtp.GB < 23);
});

test('Inkling BF16 census: fused expert tensors, shared-expert sinks and F32 gate bias are observed', async () => {
  const census = JSON.parse(await readFile(new URL('inkling_bf16_828496ee.json', censusDir), 'utf8'));
  const rows = Object.fromEntries(summarizeCensus(census).rows.map(r => [r.component, r]));
  assert.equal(rows.routed_expert.tensors, 128);
  assert.deepEqual(rows.routed_expert.example.BF16.shape.slice(0, 1), [256]);
  assert.deepEqual(rows.shared_expert.example.BF16.shape, [2, 6144, 6144]);
  assert.equal(rows.router_gate.example.BF16.shape[0], 258);
  assert.equal(rows.norm_bias_scale.dtypes.F32.tensors, 128);
  assert.equal(rows.short_conv.tensors, 264);
  assert.deepEqual(rows.short_conv.example.BF16.shape, [2048, 1, 4]);
  assert.ok(rows.routed_expert.share_percent > 97);
  assert.equal(rows.mamba_proj, undefined);
});

test('an unclassified component or a tampered total is rejected', () => {
  assert.throws(() => summarizeCensus({total: {bytes: 10, files: 1, tensors: 1}, by_component: {mystery: {BF16: {tensors: 1, elements: 5, bytes: 10}}}}), /Unclassified/);
  assert.throws(() => summarizeCensus({total: {bytes: 0}, by_component: {}}), /total\.bytes/);
  assert.ok(COMPONENT_ORDER.includes('router_gate') && COMPONENT_ORDER.includes('routed_expert'));
});
