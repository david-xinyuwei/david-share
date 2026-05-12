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
        console.log(text.substring(0, 6000));
        if (text.length > 6000) console.log(`... (${text.length} chars total)`);
      }
    } catch(e) {}
  }
});

function send(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

// Init
setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:1,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"test",version:"1.0"}}}) + '\n');
}, 2000);

const SUB = "ec4eb48c-bf18-4b9b-866c-8d4cfd7cf0c2"; // AI GBB - AI Services

// ============= Test A: pricing =============
setTimeout(() => {
  console.log('\n>>> TEST A: pricing (learn)');
  send(40, "pricing", {command: "learn"});
}, 5000);

// ============= Test B: quota =============
setTimeout(() => {
  console.log('\n>>> TEST B: quota (learn)');
  send(41, "quota", {command: "learn"});
}, 10000);

// ============= Test C: compute_vm_get — list VMs in a resource group =============
setTimeout(() => {
  console.log('\n>>> TEST C: compute vm_get (list VMs in rg-xinyu-ai-services)');
  send(42, "compute", {command: "compute_vm_get", parameters: JSON.stringify({subscription: SUB, "resource-group": "rg-xinyu-ai-services"})});
}, 15000);

// ============= Test D: foundry models_deployments_list =============
setTimeout(() => {
  console.log('\n>>> TEST D: foundry models_deployments_list');
  send(43, "foundry", {command: "models_deployments_list", parameters: JSON.stringify({foundryAccountResourceId: "/subscriptions/" + SUB + "/resourceGroups/rg-xinyu-ai-services/providers/Microsoft.CognitiveServices/accounts/xinyu-ai-services"})});
}, 20000);

// ============= Test E: group_resource_list — enumerate resources in an RG =============
setTimeout(() => {
  console.log('\n>>> TEST E: group_resource_list (rg-xinyu-ai-services)');
  send(44, "group_resource_list", {subscription: SUB, "resource-group": "rg-xinyu-ai-services"});
}, 25000);

// ============= Test F: monitor — learn available monitoring commands =============
setTimeout(() => {
  console.log('\n>>> TEST F: monitor (learn)');
  send(45, "monitor", {command: "learn"});
}, 30000);

// ============= Test G: extension_cli_generate — generate az cost command =============
setTimeout(() => {
  console.log('\n>>> TEST G: extension_cli_generate (cost query)');
  send(46, "extension_cli_generate", {intent: "show my Azure cost breakdown for the last 30 days by service in subscription " + SUB, "cli-type": "az"});
}, 35000);

// ============= Test H: role — learn RBAC tools =============
setTimeout(() => {
  console.log('\n>>> TEST H: role (learn)');
  send(47, "role", {command: "learn"});
}, 40000);

setTimeout(() => { console.log('\n=== ALL 8 DEEP TESTS COMPLETE ==='); server.kill(); process.exit(0); }, 50000);
