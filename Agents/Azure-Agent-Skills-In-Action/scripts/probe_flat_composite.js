const { spawn } = require('child_process');

const SUB = 'YOUR-SUBSCRIPTION-ID';

const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe'],
});

const results = new Map();
let buffer = '';

function classify(text) {
  if (text.includes('"status":200')) return 'SUCCESS';
  if (text.includes('"status":403')) return 'FORBIDDEN';
  if (text.includes('"status":404')) return 'NOT_FOUND';
  if (text.includes('"status":400')) return 'BAD_REQUEST';
  if (text.includes('Missing Required')) return 'MISSING_PARAMS';
  if (text.includes('available command') || text.includes('Run again with the "learn"')) return 'LEARN_FALLBACK';
  return 'OTHER';
}

server.stdout.on('data', (data) => {
  buffer += data.toString();
  const lines = buffer.split('\n');
  buffer = lines.pop();

  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const msg = JSON.parse(line);
      if (!msg.result || !msg.result.content) continue;
      const text = msg.result.content[0]?.text || JSON.stringify(msg.result.content[0]);
      const status = classify(text);
      results.set(msg.id, { status, length: text.length, preview: text.slice(0, 1200) });
      console.log(`[${msg.id}] ${status} (${text.length} chars)`);
    } catch (_) {
      // Ignore non-JSON process noise.
    }
  }
});

server.stderr.on('data', (data) => {
  const text = data.toString().trim();
  if (text) console.error(text);
});

function call(id, name, args) {
  server.stdin.write(JSON.stringify({
    jsonrpc: '2.0',
    id,
    method: 'tools/call',
    params: { name, arguments: args },
  }) + '\n');
}

setTimeout(() => {
  server.stdin.write(JSON.stringify({
    jsonrpc: '2.0',
    id: 0,
    method: 'initialize',
    params: {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: { name: 'flat-composite-probe', version: '1.0' },
    },
  }) + '\n');
}, 1500);

const tests = [
  ['compute', { command: 'compute_vm_get', subscription: SUB, 'resource-group': 'winvm' }],
  ['quota', { command: 'quota_usage_check', subscription: SUB, region: 'eastus', 'resource-types': 'Microsoft.CognitiveServices/accounts' }],
  ['storage', { command: 'storage_account_get', subscription: SUB }],
  ['monitor', { command: 'monitor_workspace_list', subscription: SUB }],
  ['role', { command: 'role_assignment_list', subscription: SUB, scope: `/subscriptions/${SUB}` }],
  ['advisor', { command: 'advisor_recommendation_list', subscription: SUB }],
];

let delay = 3500;
tests.forEach(([tool, args], index) => {
  const id = index + 1;
  setTimeout(() => {
    console.log(`>>> ${tool}/${args.command}`);
    call(id, tool, args);
  }, delay);
  delay += 5000;
});

setTimeout(() => {
  console.log('\nSUMMARY');
  for (const [id, result] of [...results.entries()].sort((a, b) => a[0] - b[0])) {
    console.log(`${id}: ${result.status} (${result.length} chars)`);
    if (result.status !== 'SUCCESS') console.log(result.preview.slice(0, 400));
  }
  server.kill();
  process.exit(0);
}, delay + 6000);