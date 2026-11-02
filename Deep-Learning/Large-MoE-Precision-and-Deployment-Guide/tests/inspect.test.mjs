import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {access, readFile} from 'node:fs/promises';
import test from 'node:test';
import {refreshSnapshot, summarizeSnapshot, tensorPayload} from '../tools/inspect.mjs';

const snapshot = JSON.parse(await readFile(new URL('../data/model-evidence.json', import.meta.url), 'utf8'));

test('covers all model variants and keeps the bilingual matrix and links aligned', async () => {
  const visuals = JSON.parse(await readFile(new URL('../data/visual-evidence.json', import.meta.url), 'utf8')).visuals;
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
    if (filename.startsWith('README')) {
      assert.doesNotMatch(markdown, /mp\.weixin\.qq\.com|之前的公众号|Our \[earlier article\]/);
      assert.doesNotMatch(markdown.split(/\r?\n/)[0], /[?？]/);
    }
    for (const match of markdown.matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)) {
      const target = match[1].split('#')[0];
      if (target && !/^[a-z]+:/i.test(target)) await access(new URL(target, source));
    }
    for (const match of markdown.matchAll(/<img\b[^>]*\bsrc="([^"]+)"/g)) {
      if (!/^[a-z]+:/i.test(match[1])) await access(new URL(match[1], source));
    }
    if (filename.startsWith('README')) {
      assert.doesNotMatch(markdown, /```mermaid|<wbr\b/);
      const language = filename.includes('_CN') ? 'zh' : 'en';
      for (const diagram of ['nvfp4-execution', 'mi300x-test-topology']) {
        const asset = `images/${diagram}-${language}.svg`;
        assert.ok(markdown.includes(asset), `${filename} embeds ${asset}`);
        const svg = await readFile(new URL(`../${asset}`, import.meta.url), 'utf8');
        assert.match(svg, /<svg\b/);
        assert.doesNotMatch(svg, /<foreignObject\b|<script\b|&amp;nbsp;/);
        const entry = visuals.find(visual => visual.asset === asset);
        assert.ok(entry, `${asset} has provenance`);
        assert.equal(createHash('sha256').update(svg).digest('hex'), entry.sha256);
        const diagramSource = await readFile(new URL(`../${entry.source_asset}`, import.meta.url));
        assert.equal(createHash('sha256').update(diagramSource).digest('hex'), entry.source_sha256);
      }
      const lines = markdown.split(/\r?\n/);
      const starts = lines.flatMap((line, index) => /^\| (组件|Part) \|/.test(line) ? [index] : []);
      assert.equal(starts.length, 3, `Expected one complete table per model in ${filename}`);
      const modelTables = starts.map(start => {
        const rows = [];
        for (let index = start; index < lines.length && lines[index].startsWith('|'); index++) rows.push(lines[index].split('|').slice(1, -1));
        assert.equal(rows.length, 27);
        assert.ok(rows.every(row => row.length === 4));
        return rows.map(row => row.map(cell => Array.from(cell.matchAll(/\[([A-Z]\d+)\]/g), match => match[1])));
      });
      assert.doesNotMatch(markdown, /不知道|待核|未核实|dtype 另核|Our \[earlier article\]/);
      matrices.push(modelTables);
    }
  }
  assert.deepEqual(matrices[0], matrices[1]);
});

test('comparison tables keep their columns and code identifiers stay whole (2026-11-02 layout regression)', async () => {
  // On 2026-11-02 a narrow-screen pass collapsed four multi-column tables into two-column
  // "<strong>label</strong><br>value" stacks and split identifiers such as `VALIDATION_CN.md` and
  // `max_tokens=1024` across `</code><br><code>` boundaries. GitHub already gives wide tables a local
  // horizontal scrollbar, so neither change was needed, and both destroyed side-by-side comparison
  // and copy/paste. This guard pins the minimum column count of each comparison table and rejects
  // identifier splitting anywhere in the two READMEs.
  const expectedColumns = {
    'README_CN.md': [['| 模型 | GPU × 数量 |', 6], ['| 模型 · 布局 | 加载结果 |', 6], ['| 模型 · 布局 | 加载结果（第 2 轮） |', 5], ['| 顺序 | 在哪台机器 |', 5], ['| 模型 | 发布方给出的起点与边界 |', 4], ['| 模型 · MXFP4 入口 |', 7]],
    'README.md': [['| Model | GPU × count |', 6], ['| Model · layout | Load result |', 6], ['| Model · layout | Load result (run 2) |', 5], ['| Order | Where |', 5], ['| Model | Published starting point and limits |', 4], ['| Model · MXFP4 entry |', 7]],
  };
  for (const [filename, tables] of Object.entries(expectedColumns)) {
    const markdown = await readFile(new URL(`../${filename}`, import.meta.url), 'utf8');
    const lines = markdown.split(/\r?\n/);
    for (const [prefix, columns] of tables) {
      const header = lines.find(line => line.startsWith(prefix));
      assert.ok(header, `${filename}: table starting with "${prefix}" is present`);
      assert.equal(header.split('|').length - 2, columns, `${filename}: "${prefix}" keeps ${columns} columns`);
    }
    assert.doesNotMatch(markdown, /<code><\/code>/, `${filename}: no empty <code> tag`);
    assert.doesNotMatch(markdown, /<\/code><br><code>/, `${filename}: no identifier split across <br>`);
    assert.doesNotMatch(markdown, /<code>[^<\n]*<br>[^<\n]*<\/code>/, `${filename}: no <br> inside a <code> span`);
    assert.doesNotMatch(markdown, /\| 配置与结果 \||\| Configuration and results \|/, `${filename}: no stacked two-column table`);
  }
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