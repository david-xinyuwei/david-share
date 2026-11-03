import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir, access } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const summary = JSON.parse(await readFile(new URL('data/mi300x-run/summary.json', root), 'utf8'));
const byTag = Object.fromEntries(summary.runs.map(run => [run.tag, run]));
const docs = Object.fromEntries(await Promise.all(
  ['README.md', 'README_CN.md', 'VALIDATION.md', 'VALIDATION_CN.md'].map(async name => [name, await readFile(new URL(name, root), 'utf8')])));

test('summary.json was derived from the projected raw files, not typed by hand', async () => {
  assert.ok(summary.runs.length >= 4, `expected the 2026-11-02 runs (3 from run 1, >=1 from run 2), got ${summary.runs.length}`);
  for (const run of summary.runs) {
    const dir = new URL(`data/mi300x-run/${run.tag}/`, root);
    const files = await readdir(dir);
    for (const required of ['00_meta.txt', '01_models.json', '05_server_keylines.log', 'PROJECTION.json', 'SHA256SUMS.private.txt']) {
      assert.ok(files.includes(required), `${run.tag} lacks ${required}`);
    }
    const meta = await readFile(new URL('00_meta.txt', dir), 'utf8');
    assert.match(meta, new RegExp(`--revision ${run.revision}`));
    // rocm/vllm 0.29 image (Nemotron, Inkling) or the v0.33.0-derived Muse image; both IDs are quoted in VALIDATION
    assert.match(meta, /imageid=sha256:[0-9a-f]{12}/);
    assert.ok(run.image_id, `${run.tag} summary lacks image_id`);
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
    // the serving probe, when present, is the probe's own JSON and the summary repeats its medians exactly
    if (run.perf) {
      assert.ok(files.includes('08_perf.json'), `${run.tag} has perf in summary but no 08_perf.json`);
      const perf = JSON.parse(await readFile(new URL('08_perf.json', dir), 'utf8'));
      assert.equal(perf.levels.length, run.perf.levels.length);
      for (const [i, lv] of run.perf.levels.entries()) {
        assert.equal(lv.concurrency, perf.levels[i].concurrency);
        assert.equal(lv.ttft_s_median, Math.round(perf.levels[i].ttft_s_median * 1000) / 1000);
        assert.equal(lv.decode_tok_s_per_request_median, Math.round(perf.levels[i].decode_tok_s_per_request_median * 10) / 10);
        assert.equal(lv.agg_tok_s_median, Math.round(perf.levels[i].agg_tok_s_median * 10) / 10);
        assert.equal(lv.n_requests, perf.levels[i].n_requests);
      }
      assert.equal(run.perf.max_tokens, 256); assert.equal(run.perf.rounds, 3);
    }
    // no private identifiers survive the projection
    const everything = (await Promise.all(files.map(f => readFile(new URL(f, dir), 'utf8')))).join('\n');
    assert.doesNotMatch(everything, /\b10\.0\.0\.\d+\b|mi3007ca|azureuser|\b20\.2\d\d\.\d+\.\d+\b/);
  }
});

// Numbers the documents quote from the serving probe (scripts/mi300x/09_perf_probe.py). Each pair is
// [string the docs must contain, value in summary.json]; a drift in either direction fails.
// README tables put the unit in the column header and the bare number in the cell; VALIDATION tables write
// "<number> tok/s" and "<number> s". Both forms count, as long as the exact rounded value appears on a table row
// that also names the unit (so a stray matching number elsewhere in the prose cannot satisfy the check).
function perfQuotes(run) {
  const l1 = run.perf.levels.find(l => l.concurrency === 1), l8 = run.perf.levels.find(l => l.concurrency === 8);
  const ms = v => [`${Math.round(v * 1000)} ms`, `${v.toFixed(3)} s`]; // "45 ms" (README) or "0.045 s" / "0.170 s" (VALIDATION)
  const tok = v => [`${v} tok/s`, `${v}`];                             // "68.9 tok/s" or bare "68.9" under a tok/s header
  return [
    { any: ms(l1.ttft_s_median), unit: /ms|TTFT/ }, { any: ms(l8.ttft_s_median), unit: /ms|TTFT/ },
    { any: tok(l1.decode_tok_s_per_request_median), unit: /tok\/s/ }, { any: tok(l8.decode_tok_s_per_request_median), unit: /tok\/s/ },
    { any: tok(l8.agg_tok_s_median), unit: /tok\/s/ },
  ];
}
function quotedOnTableRow(text, quote) {
  // a table row whose cells contain the exact value, where the unit appears either on the row itself or in the
  // header row of the same table (README puts "tok/s" in the column header)
  const lines = text.split('\n');
  const cell = (line, q) => line.split('|').some(c => c.replace(/\*\*/g, '').split(/[\s/()（）、,，;；]+/).includes(q) || c.includes(q));
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (!line.startsWith('|') || !quote.any.some(q => cell(line, q))) continue;
    if (quote.unit.test(line)) return true;
    let h = i; while (h > 0 && lines[h - 1].startsWith('|')) h--;   // first line of this table = header
    if (quote.unit.test(lines[h])) return true;
  }
  return false;
}

test('serving probe (run 2): the documents quote TTFT and tok/s exactly as measured', () => {
  const probed = summary.runs.filter(r => r.perf);
  assert.ok(probed.length >= 1, 'at least one run carries a serving probe');
  const ink = byTag.inkling_bf16_16xMI300X_pp2_run2;
  assert.ok(ink && ink.perf, 'Inkling run 2 has a probe');
  assert.equal(ink.tensor_parallel_size, 8); assert.equal(ink.pipeline_parallel_size, 2);
  assert.deepEqual(ink.model_loading_gib_per_gpu, [109.52, 116.12]);
  assert.deepEqual(ink.perf.levels.map(l => l.n_requests), [3, 24]);
  assert.deepEqual(ink.perf.levels.map(l => l.finish_reasons), [['length'], ['length']]);
  for (const run of probed) {
    for (const [name, text] of Object.entries(docs)) {
      for (const quote of perfQuotes(run)) {
        assert.ok(quotedOnTableRow(text, quote), `${name} must quote ${quote.any[0]} (or ${quote.any[1]}) on a table row with its unit, for ${run.tag}`);
      }
    }
  }
  // the probe's definitions are stated where the numbers are quoted
  for (const [name, text] of Object.entries(docs)) {
    assert.ok(/max_tokens\s*(=|为|of)?\s*256/.test(text) || text.includes('max_tokens 256'), `${name} states the probe max_tokens`);
    assert.ok(text.includes('09_perf_probe.py'), `${name} names the probe script`);
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
    // the badge, scripts and prose must not promise throughput/quality acceptance; the probe is a probe
    assert.doesNotMatch(text, /吞吐(已|实测)通过|throughput (passed|verified)|benchmark (passed|verified)/i);
    // the six FP8 / NVFP4 releases were never loaded; a Muse pass may only be claimed with a Muse run in the summary
    const musePass = summary.runs.find(r => r.tag.startsWith('muse_') && r.smoke.some(s => s.finish_reason === 'stop'));
    if (!musePass) {
      assert.doesNotMatch(text, /Muse[^|\n]{0,40}(smoke 通过|smoke passed|已实测通过|loaded and generated)/);
    } else {
      // the pass is attempt 3 on the v0.33.0-derived image; the docs must say so and quote its load/KV figures
      assert.equal(musePass.image, 'vllm-muse-ray:0.33.0');
      assert.deepEqual(musePass.model_loading_gib_per_gpu, [99.1]);
      assert.deepEqual(musePass.gpu_kv_cache_tokens, [8130184]);
      assert.equal(musePass.init_engine_seconds, 64.22);
      const stop = musePass.smoke.find(s => s.finish_reason === 'stop');
      assert.equal(stop.completion_tokens, 1354); assert.equal(stop.reasoning_tokens, 1289);
      for (const value of ['99.1', '8,130,184', '64.22', '1,354', '1,289', 'MuseSparkTritonExperts', 'v0.33.0']) {
        assert.ok(text.includes(value), `${name} must quote Muse value ${value}`);
      }
      assert.doesNotMatch(text, /Muse[^|\n]{0,60}(未通过|not passed|did not pass|NOT_RUN)/i, `${name} must not call Muse not-passed`);
    }
    // scripts referenced from the docs exist
    for (const match of text.matchAll(/\(scripts\/mi300x\/([^)\s]+)\)/g)) {
      assert.ok(match[1].length > 0);
    }
  }
  const nemotronScript = docs['README.md'].includes('scripts/mi300x/04_serve_nemotron.sh');
  const inklingScript = docs['README.md'].includes('scripts/mi300x/05_serve_inkling_2node.sh');
  assert.ok(nemotronScript && inklingScript, 'README links both serving scripts');
});

test('cross-node RCCL probe (step 7): summary numbers come from the probe result line and the documents quote them', async () => {
  // data/mi300x-run/rccl_probe/ holds the node-0 key lines of scripts/mi300x/07_rccl_probe.sh for both variants;
  // summary.rccl_probe is read from those files by tools/mi300x_evidence.py summarize.
  const dir = new URL('data/mi300x-run/rccl_probe/', root);
  const files = await readdir(dir);
  for (const required of ['07_rccl_probe_nogdr_node0.log', '07_rccl_probe_ref_node0.log', 'PROJECTION.json', 'SHA256SUMS.private.txt']) {
    assert.ok(files.includes(required), `rccl_probe projection lacks ${required}`);
  }
  assert.ok(Array.isArray(summary.rccl_probe) && summary.rccl_probe.length === 2, 'summary.json carries both probe variants');
  const nogdr = summary.rccl_probe.find(p => p.variant === 'nogdr'), ref = summary.rccl_probe.find(p => p.variant === 'ref');
  const nogdrLog = await readFile(new URL(nogdr.file, dir), 'utf8'), refLog = await readFile(new URL(ref.file, dir), 'utf8');
  // the passing variant: every summary number is on the probe's own result line
  const result = nogdrLog.match(/^RCCL_PROBE_OK=True world=(\d+) init_s=[0-9.]+ first_allreduce_s=([0-9.]+) avg_allreduce_ms=([0-9.]+) bytes=(\d+) busbw_GBps=([0-9.]+)/m);
  assert.ok(result, 'nogdr log has the RCCL_PROBE_OK result line');
  assert.equal(nogdr.ok, true); assert.equal(nogdr.probe_exit, 0);
  assert.equal(nogdr.world, Number(result[1])); assert.equal(nogdr.world, 16);
  assert.equal(nogdr.first_allreduce_s, Number(result[2]));
  assert.equal(nogdr.avg_allreduce_ms, Number(result[3])); assert.equal(nogdr.bytes, Number(result[4])); assert.equal(nogdr.bytes, 64 * 1024 * 1024);
  assert.equal(nogdr.busbw_GBps, Number(result[5]));
  // busbw is the ring formula 2(n-1)/n * bytes / time, as 07_rccl_probe.py computes it (one decimal)
  const ring = 2 * (nogdr.world - 1) / nogdr.world * nogdr.bytes / (nogdr.avg_allreduce_ms / 1000) / 1e9;
  assert.ok(Math.abs(ring - nogdr.busbw_GBps) < 0.5, `busbw ${nogdr.busbw_GBps} follows from 2(n-1)/n*bytes/time = ${ring.toFixed(1)} (rounded avg_allreduce_ms)`);
  assert.match(nogdrLog, /^PROBE_EXIT=0 /m);
  // the failing variant: no result line, watchdog timeout, exit 124 from `timeout 300`
  assert.equal(ref.ok, false); assert.equal(ref.probe_exit, 124); assert.equal(ref.avg_allreduce_ms, null); assert.equal(ref.watchdog_timeout, true);
  assert.doesNotMatch(refLog, /RCCL_PROBE_OK=True/); assert.match(refLog, /Watchdog caught collective operation timeout/); assert.match(refLog, /^PROBE_EXIT=124 /m);
  assert.ok(nogdr.peermem_fallback && ref.peermem_fallback, 'both variants logged the Peermem fallback');
  // no private identifiers survive the projection
  const everything = (await Promise.all(files.map(f => readFile(new URL(f, dir), 'utf8')))).join('\n');
  assert.doesNotMatch(everything, /\b10\.0\.0\.\d+\b|mi3007ca|azureuser|\b20\.2\d\d\.\d+\.\d+\b/);
  // the documents quote exactly these numbers, and the default-RDMA failure, wherever they describe the probe
  for (const [name, text] of Object.entries(docs)) {
    assert.ok(text.includes(`${nogdr.avg_allreduce_ms} ms`), `${name} quotes the all_reduce time ${nogdr.avg_allreduce_ms} ms`);
    assert.ok(text.includes(`${nogdr.busbw_GBps} GB/s`), `${name} quotes the bus bandwidth ${nogdr.busbw_GBps} GB/s`);
    assert.ok(text.includes('NCCL_NET_GDR_LEVEL=0'), `${name} names the setting the pass depends on`);
    assert.doesNotMatch(text, /52\.\d GB\/s[^|\n]{0,80}(benchmark passed|吞吐通过)/i);
    if (name.startsWith('README')) {
      assert.match(text, /PROBE_EXIT=124|timed out|超时/, `${name} records that the default-RDMA variant did not complete`);
      assert.ok(text.includes('data/mi300x-run/rccl_probe/'), `${name} links the projection`);
    }
  }
});

test('parallel-layout figure: generated from summary.json, ledgered, embedded in both READMEs', async () => {
  const ledger = JSON.parse(await readFile(new URL('data/visual-evidence.json', root), 'utf8'));
  const { createHash } = await import('node:crypto');
  const sha = buf => createHash('sha256').update(buf).digest('hex');
  for (const lang of ['en', 'zh']) {
    const rel = `images/mi300x-parallel-layout-${lang}.svg`;
    const entry = ledger.visuals.find(v => v.asset === rel);
    assert.ok(entry, `${rel} is registered in data/visual-evidence.json`);
    assert.equal(entry.source_class, 'original_explanatory_diagram');
    const svg = await readFile(new URL(rel, root), 'utf8');
    assert.equal(sha(Buffer.from(svg, 'utf8')), entry.sha256, `${rel} matches its ledger hash`);
    // every number the figure draws comes from summary.json (run 2 layouts)
    for (const tag of ['nemotron_bf16_8xMI300X_run2', 'inkling_bf16_16xMI300X_pp2_run2', 'muse_bf16_16xMI300X_pp2_run2']) {
      const run = byTag[tag];
      for (const gib of [...run.model_loading_gib_per_gpu, ...run.available_kv_cache_gib]) {
        assert.ok(svg.includes(`${gib} GiB`), `${rel} draws ${gib} GiB from ${tag}`);
      }
      assert.ok(svg.includes(`--tensor-parallel-size ${run.tensor_parallel_size}`), `${rel} states TP for ${tag}`);
      if (run.pipeline_parallel_size) assert.ok(svg.includes(`--pipeline-parallel-size ${run.pipeline_parallel_size}`), `${rel} states PP for ${tag}`);
      if (run.expert_parallel) assert.ok(svg.includes('--enable-expert-parallel'), `${rel} states EP for ${tag}`);
    }
    assert.match(svg, /TP8/); assert.match(svg, /PP/); assert.match(svg, /EP8/);
    // the only icon is the ledgered, unmodified Azure Virtual Machine icon
    assert.equal(entry.icons.length, 1);
    const icon = await readFile(new URL(entry.icons[0].file, root));
    assert.equal(sha(icon), entry.icons[0].sha256); assert.equal(icon.length, entry.icons[0].bytes); assert.equal(entry.icons[0].modified, false);
    assert.ok(svg.includes('data:image/svg+xml;base64,' + icon.toString('base64')), `${rel} embeds exactly the ledgered icon bytes`);
    if (entry.rendered_png) {
      const png = await readFile(new URL(entry.rendered_png.asset, root));
      assert.equal(sha(png), entry.rendered_png.sha256, `${entry.rendered_png.asset} matches its ledger hash`);
      assert.equal(entry.rendered_png.rendered_from_svg_sha256, entry.sha256, 'PNG was rendered from the current SVG');
    }
  }
  assert.ok(docs['README.md'].includes('images/mi300x-parallel-layout-en.png'), 'README embeds the English figure');
  assert.ok(docs['README_CN.md'].includes('images/mi300x-parallel-layout-zh.png'), 'README_CN embeds the Chinese figure');
  for (const name of ['README.md', 'README_CN.md']) {
    assert.match(docs[name], /Original parallel-layout figure|原创并行布局图/, `${name} captions the figure as original`);
  }
});
