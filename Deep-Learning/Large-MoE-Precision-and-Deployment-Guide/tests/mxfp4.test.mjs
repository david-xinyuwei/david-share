import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const summary = JSON.parse(await readFile(new URL('data/mi300x-mxfp4/summary.json', root), 'utf8'));
const docs = Object.fromEntries(await Promise.all(
  ['README.md', 'README_CN.md', 'VALIDATION.md', 'VALIDATION_CN.md'].map(async name => [name, await readFile(new URL(name, root), 'utf8')])));
const readmes = Object.fromEntries(Object.entries(docs).filter(([n]) => n.startsWith('README')));
const byTag = Object.fromEntries(summary.full_model_mxfp4.map(r => [r.tag, r]));

test('run 3: the MXFP4 summary is derived from the projected raw files and both passing runs used the emulated kernel', async () => {
  assert.deepEqual(Object.keys(byTag).sort(), ['inkling_mxfp4_8xMI300X', 'nemotron_mxfp4_8xMI300X']);
  for (const run of summary.full_model_mxfp4) {
    const dir = new URL(`data/mi300x-mxfp4/${run.tag}/`, root);
    for (const f of ['launch.json', 'first_response.json', '08_perf.json', 'acceptance_state.json', 'server_keylines.log', 'PROJECTION.json', 'SHA256SUMS.private.txt']) {
      await readFile(new URL(f, dir));
    }
    const launch = JSON.parse(await readFile(new URL('launch.json', dir), 'utf8'));
    assert.equal(launch.image, run.image_id);
    assert.ok(launch.args.includes('--enforce-eager'), `${run.tag} ran eager`);
    assert.equal(run.status, 'PASS');
    assert.deepEqual(run.mxfp4_backend_selected, ['EMULATION'], `${run.tag} selected the emulated MXFP4 backend`);
    assert.ok(run.expert_classes.includes('OCP_MXQuantizationEmulationTritonExperts'));
    assert.equal(run.tensor_parallel_size, 8);
    assert.equal(run.first_answer.finish_reason, 'stop');
    assert.match(run.first_answer.content, /8 位指数|8-bit|8 bit/, `${run.tag} first answer names the BF16 exponent width`);
    const perf = JSON.parse(await readFile(new URL('08_perf.json', dir), 'utf8'));
    assert.equal(perf.max_tokens, 256); assert.equal(perf.rounds, 3);
    assert.deepEqual(run.perf.levels.map(l => l.n_requests), [3, 24]);
    for (const [i, lv] of run.perf.levels.entries()) {
      assert.equal(lv.ttft_s_median, Math.round(perf.levels[i].ttft_s_median * 1000) / 1000);
      assert.equal(lv.decode_tok_s_per_request_median, Math.round(perf.levels[i].decode_tok_s_per_request_median * 10) / 10);
      assert.equal(lv.agg_tok_s_median, Math.round(perf.levels[i].agg_tok_s_median * 10) / 10);
    }
    // no private identifiers survive the projection
    const text = (await Promise.all(['launch.json', 'first_response.json', '08_perf.json', 'server_keylines.log'].map(f => readFile(new URL(f, dir), 'utf8')))).join('\n');
    assert.doesNotMatch(text, /\b10\.0\.0\.\d+\b|mi3007ca|azureuser|\b20\.2\d\d\.\d+\.\d+\b/);
  }
  // Inkling is a Quark checkpoint; Nemotron is the BF16 checkpoint quantized online with vLLM's official flags
  assert.equal(byTag.inkling_mxfp4_8xMI300X.model_arg, 'lightseekorg/Inkling-MXFP4');
  assert.equal(byTag.inkling_mxfp4_8xMI300X.online_quantization_flags, null);
  assert.equal(byTag.nemotron_mxfp4_8xMI300X.model_arg, 'nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16');
  assert.equal(byTag.nemotron_mxfp4_8xMI300X.revision, '77df655d5e9f8362164ed14dd8b48f8bce657498');
  assert.match(byTag.nemotron_mxfp4_8xMI300X.online_quantization_flags, /--quantization online --quantization-config \{"moe":"mxfp4"\} --moe-backend emulation/);
  assert.equal(byTag.nemotron_mxfp4_8xMI300X.expert_parallel, true);
  assert.equal(byTag.inkling_mxfp4_8xMI300X.expert_parallel, false);
});

test('run 3: both READMEs quote the MXFP4 numbers exactly and do not call Muse MXFP4 passed', () => {
  const ink = byTag.inkling_mxfp4_8xMI300X, nem = byTag.nemotron_mxfp4_8xMI300X;
  const quotes = [
    ...ink.model_loading_gib_per_gpu.map(String), ...nem.model_loading_gib_per_gpu.map(String),            // 66.74, 43.21
    ...ink.available_kv_cache_gib.map(String), ...nem.available_kv_cache_gib.map(String),                  // 94.79, 111.86
    ...ink.gpu_kv_cache_tokens.map(t => t.toLocaleString('en-US')), ...nem.gpu_kv_cache_tokens.map(t => t.toLocaleString('en-US')),
    `${ink.first_answer.completion_tokens}`, `${ink.first_answer.reasoning_tokens}`, `${ink.first_answer.wall_s}`,
    `${nem.first_answer.completion_tokens}`, `${nem.first_answer.reasoning_tokens}`, `${nem.first_answer.wall_s}`,
  ];
  for (const run of [ink, nem]) {
    for (const lv of run.perf.levels) {
      quotes.push(`${Math.round(lv.ttft_s_median * 1000)} ms`, `${lv.decode_tok_s_per_request_median}`);
      if (lv.concurrency === 8) quotes.push(`${lv.agg_tok_s_median}`);
    }
  }
  const muse = summary.muse_mxfp4_attempts;
  assert.equal(muse.length, 2);
  assert.ok(muse.every(a => a.status === 'FAIL' && a.weights_loaded === false), 'both Muse attempts failed before loading weights');
  assert.deepEqual(muse[1].mxfp4_backend_selected, ['EMULATION'], 'attempt 2 entered MXFP4 and selected EMULATION');
  assert.match(muse[0].error, /got quantization 'online'/);
  assert.match(muse[1].error, /requires the AITER_MXFP4_MXFP4 backend; got EMULATION/);
  const probe = summary.nvfp4_single_expert_probe;
  assert.equal(probe.full_model_inference, 'NOT_RUN');
  assert.deepEqual(probe.results.map(r => r.status), ['PASS', 'PASS']);
  for (const [name, text] of Object.entries(readmes)) {
    for (const q of quotes) assert.ok(text.includes(q), `${name} must quote ${q}`);
    assert.ok(text.includes('OCP_MXQuantizationEmulationTritonExperts'), `${name} names the emulated expert class`);
    assert.ok(text.includes('lightseekorg/Inkling-MXFP4'), `${name} names the Inkling MXFP4 checkpoint`);
    assert.ok(text.includes('AITER_MXFP4_MXFP4'), `${name} quotes the Muse backend requirement`);
    assert.ok(text.includes("got quantization 'online'"), `${name} quotes Muse attempt 1's rejection`);
    // 2026-11-03 user ruling: NVFP4 is NVIDIA's Blackwell format with no AMD kernel; the single-expert probe stays in
    // VALIDATION only. The READMEs must not present it as a result column or quote its kernel name.
    assert.ok(!text.includes('Nvfp4QuantizationEmulationTritonExperts'), `${name} does not surface the NVFP4 probe kernel`);
    assert.doesNotMatch(text, /\| 本项目实测：原厂 NVFP4 \||\| This project's run: original NVFP4 \|/, `${name} has no NVFP4 result column`);
    // Table rows are the claims a reader scans. In the Summary-first table the Muse row's MXFP4 cell (4th column)
    // and in the run-3 table the Muse row's load-result cell (2nd column) must say failed, never passed.
    const rows = text.split(/\r?\n/).filter(line => /^\| Muse Spark Open/.test(line));
    const summaryRow = rows.find(line => line.split('|').length - 2 === 4);
    assert.ok(summaryRow, `${name} has the four-column Summary-first Muse row`);
    const mxfp4Cell = summaryRow.split('|')[4];
    assert.match(mxfp4Cell, /\*\*(失败|Failed)\*\*/, `${name}: Summary-first Muse MXFP4 cell says failed`);
    assert.doesNotMatch(mxfp4Cell, /\*\*(通过|Passed)\*\*/, `${name}: Summary-first Muse MXFP4 cell must not say passed`);
    const run3Row = rows.find(line => line.split('|').length - 2 === 7 && /两次尝试|two attempts/.test(line));
    assert.ok(run3Row, `${name} has the run-3 Muse row`);
    assert.match(run3Row.split('|')[2], /\*\*(失败|Failed)\*\*/, `${name}: run-3 Muse load result says failed`);
  }
  // The probe record itself stays in the validation pages, bounded as not full-model inference.
  for (const name of ['VALIDATION_CN.md', 'VALIDATION.md']) {
    assert.ok(docs[name].includes('Nvfp4QuantizationEmulationTritonExperts'), `${name} records the NVFP4 probe kernel`);
    assert.match(docs[name], /(不是模型加载|not model loading|不是全模型|not full-model)/, `${name} bounds the NVFP4 probe`);
  }
});
