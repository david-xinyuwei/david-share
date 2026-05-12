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
        console.log(text.substring(0, 3000));
        if (text.length > 3000) console.log(`... (${text.length} chars total)`);
      }
    } catch(e) {}
  }
}
server.stdout.on('data', parseOutput);

function send(id, method, params) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method, params}) + '\n');
}

// Init
setTimeout(() => send(1, "initialize", {protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"test",version:"1.0"}}), 2000);

// Test 1: subscription_list
setTimeout(() => {
  console.log('\n>>> TEST 1: subscription_list');
  send(10, "tools/call", {name:"subscription_list", arguments:{}});
}, 5000);

// Test 2: group_list
setTimeout(() => {
  console.log('\n>>> TEST 2: group_list');
  send(11, "tools/call", {name:"group_list", arguments:{}});
}, 10000);

// Test 3: pricing (查某个服务的价格)
setTimeout(() => {
  console.log('\n>>> TEST 3: pricing');
  send(12, "tools/call", {name:"pricing", arguments:{query:"Azure OpenAI gpt-4o pricing per 1M tokens"}});
}, 15000);

// Test 4: quota (查配额)
setTimeout(() => {
  console.log('\n>>> TEST 4: quota');
  send(13, "tools/call", {name:"quota", arguments:{provider:"Microsoft.CognitiveServices", location:"eastus"}});
}, 20000);

// Test 5: foundry (查模型)
setTimeout(() => {
  console.log('\n>>> TEST 5: foundry');
  send(14, "tools/call", {name:"foundry", arguments:{}});
}, 25000);

// Test 6: extension_cli_generate
setTimeout(() => {
  console.log('\n>>> TEST 6: extension_cli_generate (list AOAI resources)');
  send(15, "tools/call", {name:"extension_cli_generate", arguments:{intent:"list all Azure OpenAI resources in my subscription", "cli-type":"az"}});
}, 30000);

setTimeout(() => { console.log('\n=== ALL 6 TESTS COMPLETE ==='); server.kill(); process.exit(0); }, 40000);
