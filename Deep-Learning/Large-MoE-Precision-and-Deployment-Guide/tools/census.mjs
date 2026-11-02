// tools/census.mjs — summarize per-component tensor dtype censuses read from real safetensors headers.
// Input: data/tensor-census/*.json produced on the download host by tools/tensor_census.py (header-only read).
// Output: JSON with per-component bytes/share and a consistency check against data/model-evidence.json.
// This is storage dtype evidence only; it does not describe compute dtype, kernels or runtime caches.

export const COMPONENT_ORDER = [
  'embedding', 'attention_proj', 'router_gate', 'routed_expert', 'shared_expert', 'latent_proj',
  'mamba_proj', 'mamba_conv_state', 'short_conv', 'norm_bias_scale', 'vision_audio_encoder', 'dense_mlp', 'mtp', 'lm_head', 'other',
];

export function summarizeCensus(census) {
  if (!census?.total?.bytes || !census.by_component) throw new Error('Census must contain total.bytes and by_component.');
  const total = census.total.bytes;
  const rows = [];
  for (const component of COMPONENT_ORDER) {
    const dtypes = census.by_component[component];
    if (!dtypes) continue;
    const bytes = Object.values(dtypes).reduce((sum, v) => sum + v.bytes, 0);
    const tensors = Object.values(dtypes).reduce((sum, v) => sum + v.tensors, 0);
    rows.push({
      component,
      dtypes: Object.fromEntries(Object.entries(dtypes).map(([dt, v]) => [dt, {tensors: v.tensors, GB: Number((v.bytes / 1e9).toFixed(3))}])),
      tensors,
      GB: Number((bytes / 1e9).toFixed(3)),
      share_percent: Number((100 * bytes / total).toFixed(3)),
      example: census.component_examples?.[component] ?? null,
    });
  }
  const unknown = Object.keys(census.by_component).filter(c => !COMPONENT_ORDER.includes(c));
  if (unknown.length) throw new Error(`Unclassified components present: ${unknown.join(', ')}`);
  return {
    snapshot_dir: census.snapshot_dir,
    files: census.total.files,
    tensors: census.total.tensors,
    total_bytes: total,
    total_GB: Number((total / 1e9).toFixed(3)),
    rows,
    unmatched_patterns: census.unmatched_patterns_top ?? [],
    evidence_type: 'OBSERVED_SAFETENSORS_HEADER',
    scope: 'Storage dtype of each tensor in the fixed revision. Not compute dtype, kernel selection or runtime cache dtype.',
  };
}

export function crossCheck(censusSummary, evidenceModel) {
  const payload = Object.entries(evidenceModel.safetensors.parameters)
    .reduce((sum, [dt, count]) => sum + count * ({BF16: 2, F16: 2, F32: 4, F8_E4M3: 1, U8: 1, I64: 8}[dt] ?? NaN), 0);
  return {
    model_id: evidenceModel.model_id,
    revision: evidenceModel.revision,
    calculated_from_api_bytes: payload,
    observed_header_bytes: censusSummary.total_bytes,
    match: payload === censusSummary.total_bytes,
  };
}

async function main(args) {
  const {readFile, readdir} = await import('node:fs/promises');
  const dir = new URL('../data/tensor-census/', import.meta.url);
  const evidence = JSON.parse(await readFile(new URL('../data/model-evidence.json', import.meta.url), 'utf8'));
  const out = [];
  for (const name of (await readdir(dir)).filter(f => f.endsWith('.json')).sort()) {
    const census = JSON.parse(await readFile(new URL(name, dir), 'utf8'));
    const summary = summarizeCensus(census);
    const model = evidence.models.find(m => summary.snapshot_dir.includes(m.revision));
    out.push({file: name, summary, cross_check: model ? crossCheck(summary, model) : {match: null, note: 'revision not in model-evidence.json'}});
  }
  if (args.includes('--table')) {
    for (const {file, summary, cross_check} of out) {
      console.log(`\n# ${file}  total=${summary.total_GB} GB  tensors=${summary.tensors}  api_match=${cross_check.match}`);
      console.log('| component | dtypes (tensors) | GB | share % |\n|---|---|---:|---:|');
      for (const r of summary.rows) console.log(`| ${r.component} | ${Object.entries(r.dtypes).map(([d, v]) => `${d} (${v.tensors})`).join(', ')} | ${r.GB} | ${r.share_percent} |`);
    }
  } else {
    console.log(JSON.stringify(out, null, 2));
  }
}

if (typeof process !== 'undefined' && process.versions?.node) {
  const {pathToFileURL} = await import('node:url');
  if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    try { await main(process.argv.slice(2)); } catch (error) { console.error(error instanceof Error ? error.message : 'Census summary failed.'); process.exitCode = 1; }
  }
}
