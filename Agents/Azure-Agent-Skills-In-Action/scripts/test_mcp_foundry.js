const { spawn } = require('child_process');
const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

let buffer = '';
server.stdout.on('data', (data) => {
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
        console.log(text.substring(0, 5000));
        if (text.length > 5000) console.log(`... (${text.length} chars total)`);
      }
    } catch(e) {}
  }
});

function send(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:1,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"test",version:"1.0"}}}) + '\n');
}, 2000);

// Test: foundry models_deployments_list (list model deployments)
setTimeout(() => {
  console.log('\n>>> TEST: foundry models_deployments_list');
  send(30, "foundry", {command: "models_deployments_list", parameters: JSON.stringify({foundryAccountResourceId: "/subscriptions/ec4eb48c-bf18-4b9b-866c-8d4cfd7cf0c2/resourceGroups/rg-xinyu-ai-services/providers/Microsoft.CognitiveServices/accounts/xinyu-ai-services"})});
}, 6000);

// Test: pricing
setTimeout(() => {
  console.log('\n>>> TEST: pricing Azure OpenAI');
  send(31, "pricing", {query: "Azure OpenAI gpt-4o pricing per million tokens"});
}, 15000);

// Test: compute (learn)
setTimeout(() => {
  console.log('\n>>> TEST: compute learn');
  send(32, "compute", {command: "learn"});
}, 22000);

setTimeout(() => { console.log('\n=== DONE ==='); server.kill(); process.exit(0); }, 30000);
