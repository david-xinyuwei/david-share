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

// Test 1: pricing_get — Azure OpenAI gpt-4o pricing
setTimeout(() => {
  console.log('\n>>> TEST 1: pricing_get (gpt-4o eastus)');
  send(50, "pricing", {command: "pricing_get", parameters: JSON.stringify({service: "Cognitive Services", region: "eastus", sku: "S0"})});
}, 5000);

// Test 2: quota_usage_check — CognitiveServices in eastus
setTimeout(() => {
  console.log('\n>>> TEST 2: quota_usage_check');
  send(51, "quota", {command: "quota_usage_check", parameters: JSON.stringify({subscription: SUB_SERVICES, region: "eastus", "resource-types": "Microsoft.CognitiveServices/accounts"})});
}, 12000);

// Test 3: quota_region_availability_list
setTimeout(() => {
  console.log('\n>>> TEST 3: quota_region_availability_list (CognitiveServices gpt-4o)');
  send(52, "quota", {command: "quota_region_availability_list", parameters: JSON.stringify({subscription: SUB_SERVICES, "resource-types": "Microsoft.CognitiveServices/accounts", "cognitive-service-model-name": "gpt-4o"})});
}, 19000);

// Test 4: compute_vm_get (correct parameter nesting)
setTimeout(() => {
  console.log('\n>>> TEST 4: compute_vm_get');
  send(53, "compute", {command: "compute_vm_get", parameters: JSON.stringify({subscription: SUB_INFRA, "resource-group": "ND-H100"})});
}, 26000);

// Test 5: role_assignment_list
setTimeout(() => {
  console.log('\n>>> TEST 5: role_assignment_list');
  send(54, "role", {command: "role_assignment_list", parameters: JSON.stringify({scope: "/subscriptions/" + SUB_SERVICES})});
}, 33000);

// Test 6: extension_cli_generate — cost query
setTimeout(() => {
  console.log('\n>>> TEST 6: extension_cli_generate (cost last 7 days)');
  send(55, "extension_cli_generate", {intent: "show my Azure cost for the last 7 days grouped by service name for subscription " + SUB_SERVICES, "cli-type": "az"});
}, 40000);

setTimeout(() => { console.log('\n=== ALL 6 FINAL TESTS COMPLETE ==='); server.kill(); process.exit(0); }, 55000);
