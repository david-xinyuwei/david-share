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
setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:1,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"test",version:"1.0"}}}) + '\n');
}, 2000);

const SUB_SERVICES = "ec4eb48c-bf18-4b9b-866c-8d4cfd7cf0c2";
const SUB_INFRA = "61643109-c1dc-442c-a7a9-a5f58b9b1703";

// Test 1: pricing_get — flat arguments
setTimeout(() => {
  console.log('\n>>> TEST 1: pricing_get (Cognitive Services eastus)');
  send(60, "pricing", {command: "pricing_get", service: "Cognitive Services", region: "eastus"});
}, 5000);

// Test 2: quota_usage_check — flat arguments
setTimeout(() => {
  console.log('\n>>> TEST 2: quota_usage_check (CognitiveServices eastus)');
  send(61, "quota", {command: "quota_usage_check", subscription: SUB_SERVICES, region: "eastus", "resource-types": "Microsoft.CognitiveServices/accounts"});
}, 12000);

// Test 3: compute_vm_get — flat arguments
setTimeout(() => {
  console.log('\n>>> TEST 3: compute_vm_get (ND-H100)');
  send(62, "compute", {command: "compute_vm_get", subscription: SUB_INFRA, "resource-group": "ND-H100"});
}, 19000);

// Test 4: group_resource_list — was successful before, this time try AI Services RG
setTimeout(() => {
  console.log('\n>>> TEST 4: group_resource_list (rg-xinyu-ai-services)');
  send(63, "group_resource_list", {subscription: SUB_SERVICES, "resource-group": "rg-xinyu-ai-services"});
}, 26000);

// Test 5: role_assignment_list — flat arguments
setTimeout(() => {
  console.log('\n>>> TEST 5: role_assignment_list');
  send(64, "role", {command: "role_assignment_list", scope: "/subscriptions/" + SUB_SERVICES});
}, 33000);

setTimeout(() => { console.log('\n=== ALL 5 CORRECT TESTS COMPLETE ==='); server.kill(); process.exit(0); }, 45000);
