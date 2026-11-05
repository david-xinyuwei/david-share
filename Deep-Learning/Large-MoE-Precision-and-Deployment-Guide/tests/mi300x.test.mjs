import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir, access } from 'node:fs/promises';

const root = new URL('../', import.meta.url);
const summary = JSON.parse(await readFile(new URL('data/mi300x-run/summary.json', root), 'utf8'));
const byTag = Object.fromEntries(summary.runs.map(run => [run.tag, run]));
const docs = Object.fromEntries(await Promise.all(
  ['README.md', 'README_CN.md', 'VALIDATION.md', 'VALIDATION_CN.md'].map(async name => [name, await readFile(new URL(name, root), 'utf8')])));

test('fiveway results preserve every strategy and recompute statistics from individual requests', async () => {
  for (const runId of ['fiveway_20261103-160700', 'qwen-fiveway_20261103-172600', 'qwen-fiveway-recovery_20261103', 'muse-selectable_20261104']) {
  const evidence = new URL(`data/mi300x-fiveway/${runId}/`, root);
  const result = JSON.parse(await readFile(new URL('summary.json', evidence), 'utf8'));
  assert.deepEqual(result.strategies.map(strategy => strategy.id), ['tp', 'pp', 'tep', 'dp', 'pd']);
  if (runId === 'qwen-fiveway-recovery_20261103') {
    assert.equal(result.parent_run_id, 'qwen-fiveway_20261103-172600');
    assert.deepEqual(result.recovery_phase.execution_order, ['pp', 'tep', 'tp', 'dp', 'pd']);
    assert.equal(result.counts.completed_layouts, 5);
    assert.equal(result.counts.formal_requests, 3810);
    assert.equal(result.counts.protocol_complete_requests + result.counts.failed_requests, result.counts.formal_requests);
    assert.equal(result.counts.complete_answers, result.strategies.reduce((total, strategy) =>
      total + strategy.workloads.reduce((count, workload) => count + workload.n_complete_answers, 0), 0));
    assert.equal(new Set(result.strategies.map(strategy => strategy.runtime.image_id)).size, 1);
    for (const strategy of result.strategies) {
      assert.deepEqual(strategy.missing_resource_nodes, []);
      const workerLaunch = await readFile(new URL(`${strategy.id}/worker-launch.txt`, evidence), 'utf8');
      assert.equal(workerLaunch.split(' ', 3)[1], strategy.runtime.image_id);
    }
    assert.equal(result.scope.publication_scope, undefined);
    assert.equal(result.recovery_phase.overnight_authorization, undefined);
  }
  const median = values => {
    if (!values.length) return null;
    const sorted = [...values].sort((left, right) => left - right);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };
  for (const strategy of result.strategies) {
    assert.ok(strategy.hypothesis && strategy.discriminating_check);
    if (!['PASS', 'COMPLETE_WITH_ERRORS'].includes(strategy.status)) {
      assert.equal(strategy.workloads, undefined, `${strategy.id} cannot invent performance before completion`);
      continue;
    }
    assert.equal(strategy.runtime.revision, result.scope.revision);
    assert.equal(strategy.runtime.gpu_memory_utilization, result.conditions.gpu_memory_utilization);
    assert.equal(strategy.smoke.finish_reason, 'stop');
    assert.ok(strategy.smoke.content.trim());
    assert.equal(strategy.workloads.length, 2);
    for (const workload of strategy.workloads) {
      const raw = JSON.parse(await readFile(new URL(`${strategy.id}/${workload.file}`, evidence), 'utf8'));
      assert.equal(workload.prompt, raw.prompt);
      assert.equal(workload.max_tokens, raw.max_tokens);
      assert.deepEqual(workload.levels.map(level => level.concurrency), result.conditions.planned_concurrency);
      for (const level of workload.levels) {
        const original = raw.levels.find(candidate => candidate.concurrency === level.concurrency);
        const requests = original.rounds.flatMap(round => round.requests);
        const successful = requests.filter(request => request.status === 'OK');
        assert.equal(requests.length, raw.rounds * level.concurrency);
        assert.equal(level.n_requests, requests.length);
        assert.equal(level.n_success, successful.length);
        assert.equal(level.n_success + level.n_failed, level.n_requests);
        assert.equal(level.n_complete_answers, successful.filter(request => request.answer_complete).length);
        assert.equal(level.n_truncated, successful.filter(request => request.finish_reason === 'length').length);
        assert.equal(level.ttft_s_median, median(successful.map(request => request.ttft_s).filter(value => value !== null)));
        assert.equal(level.decode_tok_s_median, median(successful.map(request => request.decode_tok_s).filter(value => value !== null)));
        if (runId.startsWith('qwen-')) {
          assert.equal(level.e2e_s_median, median(successful.map(request => request.wall_s).filter(value => value !== null)));
          for (const [field, sourceField] of [['ttft_s_p95', 'ttft_s'], ['e2e_s_p95', 'wall_s']]) {
            const values = successful.map(request => request[sourceField]).filter(value => value !== null).sort((left, right) => left - right);
            if (!values.length) {
              assert.equal(level[field], null);
            } else {
              const position = (values.length - 1) * 0.95;
              const lower = Math.floor(position);
              const expected = values[lower] + (values[Math.ceil(position)] - values[lower]) * (position - lower);
              assert.ok(Math.abs(level[field] - expected) < 1e-9, `${strategy.id} ${field} differs from requests`);
            }
          }
        }
        const rates = original.rounds.map(round => round.requests.filter(request => request.status === 'OK')
          .reduce((total, request) => total + request.completion_tokens, 0) / round.span_s);
        assert.deepEqual(level.aggregate_tok_s_rounds, rates);
        assert.equal(level.aggregate_tok_s_median, median(rates));
      }
    }
  }
  const projection = JSON.parse(await readFile(new URL('PROJECTION.json', evidence), 'utf8'));
  for (const name of [...projection.public_files, 'summary.json']) {
    const text = await readFile(new URL(name, evidence), 'utf8');
    assert.doesNotMatch(text, /\b10\.0\.0\.[45]\b|mi3007ca|azureuser|G:\\AI-Super-Agent/);
  }
  if (runId.startsWith('qwen-')) {
    assert.equal(result.scope.model, 'Qwen/Qwen3-235B-A22B-Instruct-2507');
    for (const strategy of result.strategies.filter(candidate => candidate.workloads)) {
      const errors = strategy.workloads.some(workload => workload.status !== 'PASS');
      assert.equal(strategy.status, errors ? 'COMPLETE_WITH_ERRORS' : 'PASS');
      for (const [filename, status] of Object.entries(strategy.native_metrics_status ?? {})) {
        assert.deepEqual(JSON.parse(await readFile(new URL(`${strategy.id}/${filename}`, evidence), 'utf8')), status);
      }
      for (const [node, filename] of Object.entries(strategy.resource_files ?? {})) {
        const content = await readFile(new URL(filename, evidence), 'utf8');
        const samples = content.trim() ? content.trim().split('\n').map(line => JSON.parse(line)) : [];
        for (const workload of strategy.workloads) {
          for (const level of workload.levels) {
            const observed = samples.filter(sample => sample.workload === workload.file && sample.concurrency === level.concurrency);
            const resource = level.resources[node];
            assert.equal(resource.sample_count, observed.length);
            for (const sample of observed) {
              const window = level.round_windows.find(candidate => candidate.round === sample.round);
              assert.ok(sample.unix_s >= window.started_unix_s && sample.unix_s < window.finished_unix_s);
              assert.equal(Object.keys(sample.gpus).length, result.scope.gpus_per_node);
            }
            for (const [card, fields] of Object.entries(resource.gpus)) {
              for (const [field, statistics] of Object.entries(fields)) {
                const values = observed.map(sample => sample.gpus[card]?.[field]).filter(value => value !== null && value !== undefined);
                assert.equal(statistics.samples, values.length);
                assert.equal(statistics.missing, observed.length - values.length);
                assert.equal(statistics.max, values.length ? Math.max(...values) : null);
                if (values.length) {
                  const average = values.reduce((total, value) => total + value, 0) / values.length;
                  assert.ok(Math.abs(statistics.mean - average) <= Math.max(1e-9, Math.abs(average) * 1e-12));
                } else {
                  assert.equal(statistics.mean, null);
                }
              }
            }
          }
        }
      }
    }
  }
  }
});

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

test('muse selectable run (2026-11-04): website flags, image, scripts, comparisons, transport, tables and charts come from the projected records', async () => {
  const { createHash } = await import('node:crypto');
  const sha = buffer => createHash('sha256').update(buffer).digest('hex');
  const lf = text => text.replace(/\r\n/g, '\n');
  const runId = 'muse-selectable_20261104';
  const evidence = new URL(`data/mi300x-fiveway/${runId}/`, root);
  const result = JSON.parse(await readFile(new URL('summary.json', evidence), 'utf8'));
  assert.equal(result.publication.marker, 'MUSE SELECTABLE RESULTS');
  assert.equal(result.publication.figure_basename, 'mi300x-muse-selectable');
  assert.deepEqual(result.strategies.map(strategy => [strategy.id, strategy.status]),
    [['tp', 'PASS'], ['pp', 'PASS'], ['tep', 'PASS'], ['dp', 'EXCLUDED'], ['pd', 'BLOCKED_RESOURCE_SCOPE']]);
  const byId = Object.fromEntries(result.strategies.map(strategy => [strategy.id, strategy]));
  assert.equal(byId.pd.available_nodes, result.scope.nodes);
  assert.ok(byId.pd.required_nodes > byId.pd.available_nodes, 'the website P/D configuration needs more nodes than the run had');
  assert.equal(byId.pd.required_gpus, byId.pd.required_nodes * result.scope.gpus_per_node);
  assert.equal(byId.dp.workloads, undefined);
  assert.equal(byId.pd.workloads, undefined);
  const measured = result.strategies.filter(strategy => strategy.workloads);
  for (const key of ['formal_requests', 'protocol_complete_requests', 'failed_requests', 'complete_answers', 'truncated_answers']) {
    assert.equal(result.counts[key], measured.reduce((total, strategy) => total + strategy.counts[key], 0), `${key} is the sum over layouts`);
  }
  assert.equal(result.counts.failed_requests, 0);
  assert.equal(result.counts.complete_answers + result.counts.truncated_answers, result.counts.protocol_complete_requests);

  // every flag the recipe page generates is in the recorded argv; every other flag is a listed addition
  const website = result.source.website_command;
  const imageId = result.conditions.image.split('@')[1];
  for (const strategy of measured) {
    const args = strategy.runtime.arguments;
    const flags = [...website.common_flags, ...website.layout_flags[strategy.id]];
    for (const flag of flags) {
      assert.ok(args.some((_, index) => flag.every((part, offset) => args[index + offset] === part)), `${strategy.id}: ${flag.join(' ')} is in the argv`);
    }
    const known = new Set([...flags.map(flag => flag[0]), ...result.conditions.added_flags, ...website.operator_value_flags]);
    for (const arg of args.filter(candidate => candidate.startsWith('--'))) {
      assert.ok(known.has(arg), `${strategy.id}: ${arg} is a website flag or a listed addition`);
    }
    for (const name of ['launch.txt', 'worker-launch.txt']) {
      const recorded = (await readFile(new URL(`${strategy.id}/${name}`, evidence), 'utf8')).split(' ', 3)[1];
      assert.equal(recorded, imageId, `${strategy.id}/${name} used the pinned image`);
    }
    assert.deepEqual(strategy.missing_resource_nodes, []);
  }

  // the all-reduce backends the README quotes are the ones the server logs record, and the README links those logs
  for (const [id, backends, crossNode] of [['tp', "['PYNCCL']", true], ['tep', "['PYNCCL']", true], ['pp', "['AITER_CUSTOM', 'PYNCCL']", false]]) {
    const log = await readFile(new URL(`${id}/server-keylines.log`, evidence), 'utf8');
    assert.ok(log.includes(`Using ${backends} all-reduce backends (in dispatch order) for group 'tp:0'`), `${id}: TP-group all-reduce backends`);
    assert.equal(log.includes('Custom allreduce is disabled because this process group spans across nodes'), crossNode, `${id}: custom all-reduce is disabled only when the TP group spans nodes`);
  }
  for (const name of ['README.md', 'README_CN.md']) {
    const text = await readFile(new URL(name, root), 'utf8');
    for (const id of ['tp', 'pp']) assert.ok(text.includes(`(data/mi300x-fiveway/${runId}/${id}/server-keylines.log)`), `${name} links the ${id} server log`);
  }

  // the scripts that ran have the same text as the published scripts (Git stores LF, so compare LF-normalized digests);
  // the deployment-analysis input is the 2026-11-03 text
  const sums = (await readFile(new URL('SOURCE_SHA256SUMS', evidence), 'utf8')).trim().split('\n').map(line => line.trim().split(/\s+/));
  const scripts = sums.filter(([, name]) => name.startsWith('source/'));
  assert.equal(scripts.length, 6);
  assert.deepEqual(result.source_scripts.map(script => [script.recorded_sha256, script.file]), scripts);
  for (const script of result.source_scripts) {
    const published = await readFile(new URL(`scripts/mi300x/${script.file.slice('source/'.length)}`, root), 'utf8');
    assert.equal(sha(Buffer.from(lf(published), 'utf8')), script.lf_sha256, `${script.file} has the same text as the published script`);
  }
  const guide = lf(await readFile(new URL('guide_prompt.txt', evidence), 'utf8'));
  assert.equal(guide, lf(await readFile(new URL('data/mi300x-fiveway/fiveway_20261103-160700/guide_prompt.txt', root), 'utf8')));

  // per-level statistics and unit costs from the individual requests
  const median = values => {
    const sorted = [...values].sort((left, right) => left - right);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };
  const p95 = values => {
    const sorted = [...values].sort((left, right) => left - right);
    const position = (sorted.length - 1) * 0.95;
    const lower = Math.floor(position);
    return sorted[lower] + (sorted[Math.ceil(position)] - sorted[lower]) * (position - lower);
  };
  for (const strategy of measured) {
    for (const workload of strategy.workloads) {
      const raw = JSON.parse(await readFile(new URL(`${strategy.id}/${workload.file}`, evidence), 'utf8'));
      if (workload.file === 'perf-guide.json') assert.equal(raw.prompt, guide);
      for (const level of workload.levels) {
        const rounds = raw.levels.find(candidate => candidate.concurrency === level.concurrency).rounds;
        const complete = rounds.flatMap(round => round.requests).filter(request => request.status === 'OK');
        assert.equal(level.e2e_s_median, median(complete.map(request => request.wall_s)));
        for (const [field, source] of [['ttft_s_p95', 'ttft_s'], ['e2e_s_p95', 'wall_s']]) {
          assert.ok(Math.abs(level[field] - p95(complete.map(request => request[source]))) < 1e-9, `${strategy.id} ${workload.file} C${level.concurrency} ${field}`);
        }
        assert.deepEqual(level.completion_tokens, [...new Set(complete.map(request => request.completion_tokens))].sort((left, right) => left - right));
        assert.deepEqual(level.round_spans_s, rounds.map(round => round.span_s));
        const cost = result.billing_reference.reference_two_vm_hour * 1e6 / (level.aggregate_tok_s_median * 3600);
        assert.ok(Math.abs(level.steady_state_usd_per_million_output_tokens - cost) <= cost * 1e-12);
      }
    }
  }

  // layout comparisons follow from the stored level statistics
  const levelOf = (strategyId, file, concurrency) => byId[strategyId].workloads.find(workload => workload.file === file)
    .levels.find(level => level.concurrency === concurrency);
  for (const comparison of result.comparisons) {
    const higher = comparison.better === 'higher';
    const best = Object.fromEntries(measured.map(strategy => [strategy.id, 0]));
    for (const point of comparison.points) {
      for (const strategy of measured) {
        assert.equal(point.values[strategy.id], levelOf(strategy.id, point.workload, point.concurrency)[comparison.metric]);
      }
      const ordered = Object.entries(point.values).sort((left, right) => higher ? right[1] - left[1] : left[1] - right[1]);
      assert.equal(point.best, ordered[0][0]);
      best[point.best] += 1;
      for (const change of point.changes) {
        const expected = point.values[change.strategy] / point.values[comparison.baseline] - 1;
        assert.ok(Math.abs(change.relative_change_ratio - expected) < 1e-12);
        assert.ok(Math.abs(change.abs_relative_change_ratio - Math.abs(expected)) < 1e-12);
      }
    }
    assert.equal(comparison.summary.points, comparison.points.length);
    assert.deepEqual(comparison.summary.best_counts, best);
  }
  const decode = result.comparisons.find(comparison => comparison.metric === 'decode_tok_s_median');
  assert.equal(decode.summary.points, 14);
  assert.equal(decode.summary.best_counts.pp, 14, 'TP8 x PP2 decodes fastest at every point, as the documents state');

  // inter-node receive rates follow from the one-second samples inside each level's rounds
  const mean = values => values.reduce((total, value) => total + value, 0) / values.length;
  for (const strategy of measured) {
    const stored = [];
    for (const [node, filename] of Object.entries(strategy.resource_files)) {
      const samples = (await readFile(new URL(filename, evidence), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
      for (const workload of strategy.workloads) {
        for (const level of workload.levels) {
          const observed = samples.filter(sample => sample.workload === workload.file && sample.concurrency === level.concurrency);
          assert.equal(level.resources[node].sample_count, observed.length);
          const devices = Object.keys(observed[0].infiniband_bytes_per_s).filter(device => device.startsWith('mlx5_ib'));
          assert.equal(devices.length, result.conditions.network.infiniband_ports_per_node);
          const expected = devices.reduce((total, device) => total + mean(observed.map(sample => sample.infiniband_bytes_per_s[device].port_rcv_data_bytes)
            .filter(value => value !== null && value !== undefined)), 0) / 1e6;
          const rate = level.transport[node].infiniband_rx_mb_s;
          assert.ok(Math.abs(rate - expected) <= Math.max(1e-9, expected * 1e-9), `${strategy.id} ${node} ${workload.file} C${level.concurrency}: ${rate} vs ${expected}`);
          stored.push(rate);
        }
      }
    }
    assert.equal(result.transport_peaks[strategy.id].infiniband_rx_mb_s_max, Math.max(...stored));
  }
  const network = result.conditions.network;
  assert.equal(result.transport_nominal_infiniband_mb_s_per_node, network.infiniband_ports_per_node * network.infiniband_port_rate_gbit_s * 1e9 / 8 / 1e6);

  // the time budget of one token follows from the stored level statistics; its estimate from the stored spec and sources
  const budgetSpec = result.publication.time_budget;
  const timeBudget = result.time_budget;
  const nearly = (actual, expected) => Math.abs(actual - expected) <= Math.abs(expected) * 1e-9 + 1e-12;
  assert.equal(timeBudget.estimate.status, 'ESTIMATE_NOT_MEASURED');
  assert.equal(budgetSpec.language_layers, 62);
  assert.match(budgetSpec.language_layers_source, /huggingface\.co\/meta-models\/Muse-Spark-Open-816B-A42B/);
  assert.match(budgetSpec.cross_node_collectives_source, /v0\.33\.0/);
  assert.deepEqual([...budgetSpec.cross_node_collective_layouts].sort(), ['tep', 'tp']);
  const roundOutput = level => level.aggregate_tok_s_rounds.reduce((total, rate, index) => total + rate * level.round_spans_s[index], 0);
  const roundSeconds = level => level.round_spans_s.reduce((total, span) => total + span, 0);
  const portBytes = network.infiniband_port_rate_gbit_s * 1e9 / 8;
  const nominalBytes = result.transport_nominal_infiniband_mb_s_per_node * 1e6;
  for (const layout of budgetSpec.layouts) {
    const level = levelOf(layout, budgetSpec.workload, budgetSpec.concurrency);
    const raw = JSON.parse(await readFile(new URL(`${layout}/${budgetSpec.workload}`, evidence), 'utf8'));
    const counted = raw.levels.find(candidate => candidate.concurrency === budgetSpec.concurrency).rounds
      .flatMap(round => round.requests).filter(request => request.status === 'OK')
      .reduce((total, request) => total + request.completion_tokens, 0);
    const output = roundOutput(level);
    assert.ok(Math.abs(output - counted) < 1e-6, `${layout}: round rates x round spans give back the ${counted} counted output tokens`);
    const entry = timeBudget.layouts[layout];
    assert.ok(nearly(entry.ms_per_output_token, 1000 / level.decode_tok_s_median));
    for (const node of ['node0', 'node1']) {
      const bytes = level.transport[node].infiniband_rx_mb_s * 1e6 * roundSeconds(level);
      assert.ok(nearly(entry.infiniband_rx_bytes_per_output_token[node], bytes / output), `${layout} ${node}: bytes per output token`);
      assert.ok(nearly(entry.infiniband_rx_bytes_per_processed_token[node], bytes / (output + level.n_success * level.prompt_tokens[0])));
    }
    const busier = Math.max(...Object.values(entry.infiniband_rx_bytes_per_output_token));
    assert.ok(nearly(entry.busier_node_infiniband_rx_bytes_per_output_token, busier));
    assert.ok(nearly(entry.transfer_us_per_output_token_at_nominal, busier / nominalBytes * 1e6));
    assert.ok(nearly(entry.transfer_us_per_output_token_at_one_port, busier / portBytes * 1e6));
    const extra = entry.ms_per_output_token - timeBudget.layouts[budgetSpec.reference_layout].ms_per_output_token;
    assert.ok(nearly(entry.extra_ms_per_output_token_vs_reference, extra));
    if (layout !== budgetSpec.reference_layout) {
      assert.ok(extra > 0, `${layout} needs more time per token than the reference layout`);
      assert.ok(nearly(entry.transfer_share_of_extra_ratio, entry.transfer_us_per_output_token_at_nominal / (extra * 1000)));
      assert.ok(nearly(entry.one_port_transfer_share_of_extra_ratio, entry.transfer_us_per_output_token_at_one_port / (extra * 1000)));
    }
  }
  const tpBudget = timeBudget.layouts.tp;
  const tepBudget = timeBudget.layouts.tep;
  assert.ok(tpBudget.transfer_share_of_extra_ratio < 0.01, 'at the nominal rate the TP16 data needs under 1% of its extra time');
  assert.ok(tpBudget.one_port_transfer_share_of_extra_ratio < 0.1, 'through a single port it would still need under 10%');
  assert.ok(tepBudget.busier_node_infiniband_rx_bytes_per_output_token < tpBudget.busier_node_infiniband_rx_bytes_per_output_token
    && tepBudget.extra_ms_per_output_token_vs_reference > tpBudget.extra_ms_per_output_token_vs_reference,
    'TP16 + EP moves less data than TP16 and still takes more extra time');
  const budgetAllReduces = budgetSpec.language_layers * budgetSpec.cross_node_collectives_per_layer;
  const budgetCollectives = budgetAllReduces + budgetSpec.collectives_per_step_outside_layers;
  assert.match(budgetSpec.collectives_outside_layers_source, /vocab_parallel_embedding/);
  assert.equal(timeBudget.estimate.cross_node_all_reduces_in_layers_per_token, budgetAllReduces);
  assert.equal(timeBudget.one_port_infiniband_gb_s, network.infiniband_port_rate_gbit_s / 8);
  assert.equal(timeBudget.estimate.cross_node_collectives_per_token, budgetCollectives);
  assert.ok(nearly(timeBudget.estimate.extra_us_per_cross_node_collective_lower_bound, tpBudget.extra_ms_per_output_token_vs_reference * 1000 / budgetCollectives));
  assert.ok(nearly(timeBudget.estimate.infiniband_rx_bytes_per_collective_mean, tpBudget.busier_node_infiniband_rx_bytes_per_output_token / budgetCollectives));
  assert.ok(nearly(timeBudget.estimate.transfer_us_per_collective_at_nominal, timeBudget.estimate.infiniband_rx_bytes_per_collective_mean / nominalBytes * 1e6));
  // the pipeline hand-off checks the counter scale: node 1 receives one FP32 residual stream per processed token
  const budgetHandoff = timeBudget.pipeline_handoff;
  assert.equal(budgetHandoff.expected_bytes_per_processed_token, budgetSpec.pipeline_handoff_hidden_size * budgetSpec.pipeline_handoff_bytes_per_value);
  assert.ok(nearly(budgetHandoff.measured_bytes_per_processed_token,
    timeBudget.layouts[budgetSpec.pipeline_layout].infiniband_rx_bytes_per_processed_token[budgetSpec.pipeline_receiving_node]));
  assert.ok(nearly(budgetHandoff.measured_to_expected_ratio, budgetHandoff.measured_bytes_per_processed_token / budgetHandoff.expected_bytes_per_processed_token));
  assert.ok(Math.abs(budgetHandoff.measured_to_expected_ratio - 1) < 0.05, `hand-off bytes within 5% of one hidden state (${budgetHandoff.measured_to_expected_ratio})`);
  for (const layout of budgetSpec.layouts) {
    const values = byId[layout].workloads.flatMap(workload => workload.levels.map(level =>
      Math.max(...['node0', 'node1'].map(node => level.transport[node].infiniband_rx_mb_s * 1e6 * roundSeconds(level))) / roundOutput(level)));
    assert.equal(timeBudget.all_points[layout].points, values.length);
    assert.ok(nearly(timeBudget.all_points[layout].busier_node_infiniband_rx_bytes_per_output_token_min, Math.min(...values)));
    assert.ok(nearly(timeBudget.all_points[layout].busier_node_infiniband_rx_bytes_per_output_token_max, Math.max(...values)));
  }

  // the generated README tables and the numbers quoted in the prose equal the summary
  const names = { tp: 'TP16', pp: 'TP8 × PP2', tep: 'TP16 + EP' };
  const percent = value => Math.round(value * 100);
  for (const filename of ['README.md', 'README_CN.md']) {
    const text = docs[filename];
    const regions = text.match(/<!-- BEGIN MUSE SELECTABLE RESULTS -->[\s\S]*?<!-- END MUSE SELECTABLE RESULTS -->/g) ?? [];
    assert.equal(regions.length, 1, `${filename} has one generated region`);
    const rows = regions[0].split(/\r?\n/).filter(line => line.startsWith('| '))
      .map(line => line.split('|').slice(1, -1).map(cell => cell.trim()))
      .filter(cells => cells.length === 11 && /^\d+$/.test(cells[1]));
    assert.equal(rows.length, 2 * measured.length * result.conditions.planned_concurrency.length);
    let index = 0;
    for (const file of ['perf-short.json', 'perf-guide.json']) {
      for (const strategy of measured) {
        for (const level of strategy.workloads.find(workload => workload.file === file).levels) {
          const cells = rows[index++];
          assert.equal(cells[0], names[strategy.id]);
          assert.equal(Number(cells[1]), level.concurrency);
          assert.ok(Math.abs(Number(cells[6]) - level.decode_tok_s_median) <= 0.05 + 1e-9, `${filename} ${cells[0]} C${cells[1]} decode`);
          assert.ok(Math.abs(Number(cells[7].replace(/,/g, '')) - level.aggregate_tok_s_median) <= 0.05 + 1e-9, `${filename} ${cells[0]} C${cells[1]} throughput`);
          assert.equal(cells[8], `${level.n_success}/${level.n_requests}`);
          assert.equal(cells[9], `${level.n_complete_answers}/${level.n_success}`);
        }
      }
    }
    const advantage = decode.summary.versus_baseline.pp;
    assert.ok(text.includes(`${percent(advantage.abs_relative_change_ratio_min)}–${percent(advantage.abs_relative_change_ratio_max)}%`), `${filename} quotes the TP8 x PP2 decode advantage`);
    for (const value of [result.counts.formal_requests, result.counts.complete_answers]) {
      assert.ok(text.includes(value.toLocaleString('en-US')), `${filename} quotes ${value}`);
    }
    assert.ok(text.includes(`${Math.round(result.transport_peaks.tp.infiniband_rx_mb_s_max).toLocaleString('en-US')} MB/s`), `${filename} quotes the TP16 inter-node peak`);
    assert.ok(text.includes(`${(result.transport_peaks.tp.infiniband_rx_share_of_nominal_max * 100).toFixed(1)}%`), `${filename} quotes the share of the nominal bandwidth`);
  }
  // the time-budget table is generated from the summary, and the prose quotes the same values
  for (const filename of ['README.md', 'README_CN.md']) {
    const text = docs[filename];
    const regions = text.match(/<!-- BEGIN MUSE SELECTABLE TIME BUDGET -->[\s\S]*?<!-- END MUSE SELECTABLE TIME BUDGET -->/g) ?? [];
    assert.equal(regions.length, 1, `${filename} has one time-budget region`);
    const rows = regions[0].split(/\r?\n/).filter(line => line.startsWith('| ')).map(line => line.split('|').slice(1, -1).map(cell => cell.trim())).slice(1);
    assert.equal(rows.length, budgetSpec.layouts.length);
    for (const cells of rows) {
      assert.equal(cells.length, 6, `${filename}: time-budget rows keep six columns`);
      const layout = Object.keys(names).find(id => names[id] === cells[0]);
      assert.equal(cells[1], timeBudget.layouts[layout].ms_per_output_token.toFixed(1), `${filename} ${cells[0]}: time per token`);
    }
    assert.ok(text.includes('<a id="muse-time-budget"></a>') && text.includes('(#muse-time-budget)'), `${filename} anchors and links the time budget`);
    for (const quoted of [`${Math.round(timeBudget.estimate.extra_us_per_cross_node_collective_lower_bound)} µs`,
      `${timeBudget.estimate.cross_node_collectives_per_token}`,
      `${timeBudget.estimate.cross_node_all_reduces_in_layers_per_token}`,
      `${timeBudget.one_port_infiniband_gb_s} GB/s`,
      `${(tpBudget.busier_node_infiniband_rx_bytes_per_output_token / 1e6).toFixed(1)} MB`,
      `${Math.round(tpBudget.transfer_us_per_output_token_at_nominal)} µs`,
      `${(tpBudget.transfer_share_of_extra_ratio * 100).toFixed(1)}%`,
      `${Math.round(tpBudget.transfer_us_per_output_token_at_one_port)} µs`,
      budgetHandoff.expected_bytes_per_processed_token.toLocaleString('en-US'),
      Math.round(budgetHandoff.measured_bytes_per_processed_token).toLocaleString('en-US'),
      `${Math.round(budgetHandoff.measured_to_expected_ratio * 100)}%`]) {
      assert.ok(text.includes(quoted), `${filename} quotes ${quoted}`);
    }
  }
  for (const filename of ['VALIDATION.md', 'VALIDATION_CN.md']) {
    assert.ok(docs[filename].includes(result.counts.formal_requests.toLocaleString('en-US')), `${filename} quotes the request count`);
    assert.ok(docs[filename].includes('muse-selectable-validation'), `${filename} has the validation anchor`);
    assert.ok(docs[filename].includes(Math.round(budgetHandoff.measured_bytes_per_processed_token).toLocaleString('en-US')), `${filename} records the hand-off check`);
  }

  // the four charts per language are generated from this summary and ledgered
  const ledger = JSON.parse(await readFile(new URL('data/visual-evidence.json', root), 'utf8'));
  for (const [filename, language] of [['README.md', 'en'], ['README_CN.md', 'zh']]) {
    for (const kind of ['topology', 'performance', 'resources', 'time-budget']) {
      const asset = `images/mi300x-muse-selectable-${kind}-${language}.svg`;
      assert.ok(docs[filename].includes(asset), `${filename} embeds ${asset}`);
      const svg = await readFile(new URL(asset, root));
      const entry = ledger.visuals.find(visual => visual.asset === asset);
      assert.ok(entry, `${asset} is ledgered`);
      assert.equal(sha(svg), entry.sha256, `${asset} matches its ledger hash`);
      assert.deepEqual(entry.bound_to, [`data/mi300x-fiveway/${runId}/summary.json`]);
      assert.doesNotMatch(svg.toString('utf8'), /<foreignObject\b|<script\b/);
    }
  }
});
