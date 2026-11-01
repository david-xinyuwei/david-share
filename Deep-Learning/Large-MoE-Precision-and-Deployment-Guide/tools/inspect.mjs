export const dtypeBytes = Object.freeze({
  BOOL: 1, U8: 1, I8: 1, F8_E4M3: 1, F8_E4M3FN: 1, F8_E5M2: 1,
  BF16: 2, F16: 2, I16: 2, U16: 2, F32: 4, I32: 4, U32: 4,
  F64: 8, I64: 8, U64: 8,
});

export function tensorPayload(parameters) {
  if (!parameters || Object.keys(parameters).length === 0) {
    throw new Error('Missing per-dtype tensor counts; do not use nominal model parameters instead.');
  }
  let bytes = 0;
  let elements = 0;
  for (const [dtype, count] of Object.entries(parameters)) {
    if (!(dtype in dtypeBytes)) throw new Error(`Unknown tensor dtype: ${dtype}`);
    if (!Number.isSafeInteger(count) || count < 0) throw new Error(`Invalid count for ${dtype}`);
    bytes += count * dtypeBytes[dtype];
    elements += count;
  }
  if (!Number.isSafeInteger(bytes)) throw new Error('Tensor byte count exceeds exact integer range.');
  return {bytes, elements};
}

export function summarizeModel(model) {
  if (!model.model_id || !/^[0-9a-f]{40}$/i.test(model.revision ?? '')) {
    throw new Error('A model ID and a complete revision SHA are required.');
  }
  const payload = tensorPayload(model.safetensors?.parameters);
  return {
    model_id: model.model_id,
    revision: model.revision,
    family: model.family,
    variant: model.variant,
    tensor_payload_bytes: payload.bytes,
    tensor_payload_GB: Number((payload.bytes / 1e9).toFixed(3)),
    tensor_payload_GiB: Number((payload.bytes / 2 ** 30).toFixed(3)),
    reported_total_elements: model.safetensors.total ?? null,
    sum_dtype_elements: payload.elements,
    metadata_total_matches: model.safetensors.total === payload.elements,
    inference_status: 'NOT_RUN',
    scope: 'Tensor payload only; excludes file headers, non-tensor files, KV/state cache and runtime overhead.',
  };
}

export function summarizeSnapshot(snapshot) {
  if (!snapshot.capture_utc || !Array.isArray(snapshot.models) || snapshot.models.length === 0) {
    throw new Error('Snapshot must contain a capture time and model records.');
  }
  const identifiers = snapshot.models.map(model => model.model_id);
  if (new Set(identifiers).size !== identifiers.length) throw new Error('Duplicate model IDs in snapshot.');
  return {
    capture_utc: snapshot.capture_utc,
    result_type: 'CALCULATED_FROM_PUBLIC_METADATA',
    inference_status: 'NOT_RUN',
    models: snapshot.models.map(summarizeModel),
  };
}

export async function refreshSnapshot(snapshot, fetcher = fetch) {
  const models = [];
  for (const model of snapshot.models) {
    const response = await fetcher(`https://huggingface.co/api/models/${model.model_id}`);
    if (!response.ok) throw new Error(`Metadata read failed: ${model.model_id}, HTTP ${response.status}`);
    const current = await response.json();
    if (current.id !== model.model_id) throw new Error(`Metadata model identity changed: ${model.model_id}`);
    models.push({...model, revision: current.sha, gated: current.gated, safetensors: current.safetensors});
  }
  return {...snapshot, capture_utc: new Date().toISOString(), models, quantization_configs: [],
    quantization_config_capture_utc: null,
    scope: 'Fresh public model metadata; quantization configuration must be checked separately.'};
}

async function main(args) {
  const {readFile} = await import('node:fs/promises');
  const snapshot = JSON.parse(await readFile(new URL('../data/model-evidence.json', import.meta.url), 'utf8'));
  if (args.length > 1 || (args.length === 1 && args[0] !== '--live')) {
    throw new Error('Usage: node tools/inspect.mjs [--live]');
  }
  const result = args[0] === '--live' ? await refreshSnapshot(snapshot) : snapshot;
  console.log(JSON.stringify(summarizeSnapshot(result), null, 2));
}

if (typeof process !== 'undefined' && process.versions?.node) {
  const {pathToFileURL} = await import('node:url');
  if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    try {
      await main(process.argv.slice(2));
    } catch (error) {
      console.error(error instanceof Error ? error.message : 'Metadata inspection failed.');
      process.exitCode = 1;
    }
  }
}