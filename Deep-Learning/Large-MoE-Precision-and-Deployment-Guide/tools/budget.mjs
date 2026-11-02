// tools/budget.mjs — per-GPU weight budget table from observed tensor bytes and publisher GPU counts.
// Every output row is CALCULATED; "remaining" is HBM minus resident weights only (no KV/state/workspace).
export function budgetRows(budget, censusBytesByFile) {
  const rows = [];
  for (const layout of budget.layouts) {
    const bytes = censusBytesByFile[layout.census];
    if (!bytes) throw new Error(`Missing census bytes for ${layout.census}`);
    for (const cfg of layout.configs) {
      const gpu = budget.gpus[cfg.gpu];
      if (!gpu) throw new Error(`Unknown GPU ${cfg.gpu}`);
      const perGpuGB = bytes / 1e9 / cfg.count;
      const remaining = gpu.hbm_GB - perGpuGB;
      rows.push({
        model: layout.model, gpu: cfg.gpu, count: cfg.count, source: cfg.source,
        weights_total_GB: Number((bytes / 1e9).toFixed(1)),
        weights_per_gpu_GB: Number(perGpuGB.toFixed(1)),
        hbm_per_gpu_GB: gpu.hbm_GB,
        remaining_per_gpu_GB: Number(remaining.toFixed(1)),
        fits_weights: remaining > 0,
        note: remaining <= 0 ? 'weights alone exceed HBM' : remaining < 20 ? 'under 20 GB left for caches' : '',
      });
    }
  }
  return rows;
}

async function main(args) {
  const {readFile} = await import('node:fs/promises');
  const budget = JSON.parse(await readFile(new URL('../data/deployment-budget.json', import.meta.url), 'utf8'));
  const bytesByFile = {};
  for (const layout of budget.layouts) {
    const census = JSON.parse(await readFile(new URL(`../data/tensor-census/${layout.census}`, import.meta.url), 'utf8'));
    bytesByFile[layout.census] = census.total.bytes;
  }
  const rows = budgetRows(budget, bytesByFile);
  if (args.includes('--table')) {
    console.log('| model | GPU x count | weights per GPU GB | HBM per GPU GB | remaining per GPU GB | fits | source |\n|---|---|---:|---:|---:|---|---|');
    for (const r of rows) console.log(`| ${r.model} | ${r.count} x ${r.gpu} | ${r.weights_per_gpu_GB} | ${r.hbm_per_gpu_GB} | ${r.remaining_per_gpu_GB} | ${r.fits_weights ? 'yes' : 'NO'} | ${r.source} |`);
  } else {
    console.log(JSON.stringify({evidence_type: budget.evidence_type, scope: budget.scope, rows}, null, 2));
  }
}

if (typeof process !== 'undefined' && process.versions?.node) {
  const {pathToFileURL} = await import('node:url');
  if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    try { await main(process.argv.slice(2)); } catch (error) { console.error(error instanceof Error ? error.message : 'Budget failed.'); process.exitCode = 1; }
  }
}
