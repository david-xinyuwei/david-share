const { spawn } = require('child_process');
const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

let buffer = '';
function parseOutput(data) {
  buffer += data.toString();
  const lines = buffer.split('\n');
  buffer = lines.pop();
  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const msg = JSON.parse(line);
      if (msg.result && msg.result.content) {
        const text = msg.result.content[0]?.text || JSON.stringify(msg.result.content[0]);
        console.log(`\n=== RESULT id=${msg.id} ===`);
        console.log(text.substring(0, 4000));
        if (text.length > 4000) console.log(`... (${text.length} chars total)`);
      }
    } catch(e) {}
  }
}
server.stdout.on('data', parseOutput);

function send(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

// Init
setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:1,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"test",version:"1.0"}}}) + '\n');
}, 2000);

// Test: group_list with subscription
setTimeout(() => {
  console.log('\n>>> TEST: group_list with subscription');
  send(20, "group_list", {subscription: "61643109-c1dc-442c-a7a9-a5f58b9b1703"});
}, 5000);

// Test: group_resource_list
setTimeout(() => {
  console.log('\n>>> TEST: group_resource_list');
  send(21, "group_resource_list", {subscription: "61643109-c1dc-442c-a7a9-a5f58b9b1703", "resource-group": "rg-ai-infra"});
}, 12000);

// Test: foundry (learn mode)
setTimeout(() => {
  console.log('\n>>> TEST: foundry learn');
  send(22, "foundry", {command: "learn"});
}, 18000);

// Test: quota learn
setTimeout(() => {
  console.log('\n>>> TEST: quota learn');
  send(23, "quota", {command: "learn"});
}, 24000);

// Test: pricing
setTimeout(() => {
  console.log('\n>>> TEST: pricing');
  send(24, "pricing", {query: "Azure OpenAI gpt-4o pricing"});
}, 30000);

// Test: compute
setTimeout(() => {
  console.log('\n>>> TEST: compute learn');
  send(25, "compute", {command: "learn"});
}, 36000);

setTimeout(() => { console.log('\n=== ALL TESTS COMPLETE ==='); server.kill(); process.exit(0); }, 45000);
