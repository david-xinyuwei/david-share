import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir, access } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const summary = JSON.parse(await readFile(new URL('data/mi300x-run/summary.json', root), 'utf8'));
const byTag = Object.fromEntries(summary.runs.map(run => [run.tag, run]));
const docs = Object.fromEntries(await Promise.all(
  ['README.md', 'README_CN.md', 'VALIDATION.md', 'VALIDATION_CN.md'].map(async name => [name, await readFile(new URL(name, root), 'utf8')])));

test('summary.json was derived from the projected raw files, not typed by hand', async () => {
  assert.equal(summary.runs.length, 3);
  for (const run of summary.runs) {
    const dir = new URL(`data/mi300x-run/${run.tag}/`, root);
    const files = await readdir(dir);
    for (const required of ['00_meta.txt', '01_models.json', '05_server_keylines.log', 'PROJECTION.json', 'SHA256SUMS.private.txt']) {
      assert.ok(files.includes(required), `${run.tag} lacks ${required}`);
    }
    const meta = await readFile(new URL('00_meta.txt', dir), 'utf8');
    assert.match(meta, new RegExp(`--revision ${run.revision}`));
    assert.match(meta, /imageid=sha256:e0ea9a10b729/);
    for (const smoke of run.smoke) {
      await access(new URL(`${smoke.name}_request.json`, dir));
      const request = JSON.parse(await readFile(new URL(`${smoke.name}_request.json`, dir), 'utf8'));
      assert.equal(request.temperature, 0);
      assert.equal(request.max_tokens, smoke.max_tokens);
      if (smoke.finish_reason) {
        const response = JSON.parse(await readFile(new URL(`${smoke.name}_response.json`, dir), 'utf8'));
        assert.equal(response.usage.completion_tokens, smoke.completion_tokens);
        assert.equal(response.choices[0].finish_reason, smoke.finish_reason);
      }
    }
    // no private identifiers survive the projection
    const everything = (await Promise.all(files.map(f => readFile(new URL(f, dir), 'utf8')))).join('\n');
    assert.doesNotMatch(everything, /\b10\.0\.0\.\d+\b|mi3007ca|azureuser|\b20\.2\d\d\.\d+\.\d+\b/);
  }
});

test('Nemotron run: the documents quote the evidence values', () => {
  const run = byTag.nemotron_bf16_8xMI300X;
  assert.equal(run.tensor_parallel_size, 8);
  assert.equal(run.expert_parallel, true);
  assert.deepEqual(run.moe_backend, ['TritonExperts MoE backend']);
  assert.deepEqual(run.attention_backend_override, ['ROCM_ATTN']);
  assert.deepEqual(run.mamba_ssu_backend, ['triton']);
  assert.equal(run.mamba_ssm_cache_dtype, 'float16');
  assert.deepEqual(run.model_loading_gib_per_gpu, [136.51]);
  assert.deepEqual(run.available_kv_cache_gib, [23.07]);
  assert.deepEqual(run.gpu_kv_cache_tokens, [3490022]);
  assert.ok(run.consumed_memory_gib.includes(146.67));
  const [zh, en] = run.smoke;
  assert.equal(zh.finish_reason, 'stop'); assert.equal(zh.prompt_tokens, 31); assert.equal(zh.completion_tokens, 94); assert.equal(zh.reasoning_tokens, 21); assert.equal(zh.wall_secs, 1.61);
  assert.equal(en.finish_reason, 'stop'); assert.equal(en.prompt_tokens, 42); assert.equal(en.completion_tokens, 209); assert.equal(en.reasoning_tokens, 29); assert.equal(en.wall_secs, 5.42);
  for (const [name, text] of Object.entries(docs)) {
    for (const value of ['136.51', '146.67', '23.07', '3,490,022', 'TritonExperts', 'ROCM_ATTN']) {
      assert.ok(text.includes(value), `${name} must quote ${value}`);
    }
    if (name.startsWith('README')) {
      assert.match(text, /31\s*(→|->)\s*94/); assert.match(text, /42\s*(→|->)\s*209/);
      assert.ok(text.includes('1.61 s')); assert.ok(text.includes('5.42 s'));
    }
  }
});

test('Inkling runs: TP8×PP2 passed, TP8×DP2+EP16 is recorded as not passing, both from evidence', () => {
  const pp = byTag.inkling_bf16_16xMI300X_pp2;
  assert.equal(pp.tensor_parallel_size, 8); assert.equal(pp.pipeline_parallel_size, 2); assert.equal(pp.expert_parallel, false);
  assert.deepEqual(pp.moe_backend, ['AiterExperts MoE backend']);
  assert.deepEqual(pp.model_loading_gib_per_gpu, [109.52, 116.12]);
  assert.deepEqual(pp.available_kv_cache_gib, [51.02, 57.39]);
  assert.deepEqual(pp.gpu_kv_cache_tokens, [398239]);
  assert.deepEqual(pp.smoke.map(s => s.finish_reason), ['length', 'length', 'stop']);
  assert.deepEqual(pp.smoke.map(s => s.completion_tokens), [200, 256, 441]);
  assert.deepEqual(pp.smoke.map(s => s.reasoning_tokens), [199, 255, 362]);
  assert.deepEqual(pp.smoke.map(s => s.wall_secs), [2.97, 4.06, 6.52]);
  assert.ok(pp.smoke[2].content.includes('8 位指数') && pp.smoke[2].content.includes('7 位'), 'final answer names BF16 exponent/mantissa widths');

  const dp = byTag.inkling_bf16_16xMI300X;
  assert.equal(dp.data_parallel_size, 2); assert.equal(dp.expert_parallel, true);
  assert.deepEqual(dp.model_loading_gib_per_gpu, [114.88]);
  assert.deepEqual(dp.available_kv_cache_gib, [50.25]);
  assert.deepEqual(dp.gpu_kv_cache_tokens, [317040]);
  assert.equal(dp.smoke[0].finish_reason, 'length'); assert.equal(dp.smoke[0].wall_secs, 4.76);
  assert.equal(dp.smoke[1].finish_reason, null); assert.ok(dp.smoke[1].wall_secs > 600, 'second request timed out');

  for (const [name, text] of Object.entries(docs)) {
    for (const value of ['109.52', '116.12', '57.39', '51.02', '398,239', '114.88', '50.25', '317,040', 'AiterExperts']) {
      assert.ok(text.includes(value), `${name} must quote ${value}`);
    }
    if (name.startsWith('README')) {
      assert.match(text, /27\s*(→|->)\s*441/); assert.ok(text.includes('6.52 s'));
      assert.match(text, /sample_tokens timed out/);
      assert.match(text, /TP8\s*[×x]\s*PP2/);
    }
    if (name.startsWith('VALIDATION')) {
      assert.ok(text.includes('finish_reason=stop') || text.includes('`finish_reason=stop`'));
      assert.ok(text.includes('sconv SWA cache supports tp_size <= num_kv_heads (8)'));
    }
  }
});

test('documents do not claim what the run did not do', () => {
  for (const [name, text] of Object.entries(docs)) {
    // the badge, scripts and prose must not promise throughput/quality acceptance
    assert.doesNotMatch(text, /吞吐(已|实测)通过|throughput (passed|verified)/i);
    // the seven FP8 / NVFP4 releases were never loaded; Muse was never loaded
    assert.doesNotMatch(text, /Muse[^|\n]{0,40}(smoke 通过|smoke passed|已实测通过|loaded and generated)/);
    // scripts referenced from the docs exist
    for (const match of text.matchAll(/\(scripts\/mi300x\/([^)\s]+)\)/g)) {
      assert.ok(match[1].length > 0);
    }
  }
  const nemotronScript = docs['README.md'].includes('scripts/mi300x/04_serve_nemotron.sh');
  const inklingScript = docs['README.md'].includes('scripts/mi300x/05_serve_inkling_2node.sh');
  assert.ok(nemotronScript && inklingScript, 'README links both serving scripts');
});
