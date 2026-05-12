const { spawn } = require('child_process');

const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

let buffer = '';
server.stdout.on('data', (data) => {
  buffer += data.toString();
  // Parse JSON-RPC responses separated by newlines
  const lines = buffer.split('\n');
  buffer = lines.pop(); // keep incomplete line
  for (const line of lines) {
    if (line.trim()) {
      try {
        const msg = JSON.parse(line);
        if (msg.result && msg.result.tools) {
          console.log(`\n=== ${msg.result.tools.length} TOOLS AVAILABLE ===\n`);
          // Group by prefix
          const groups = {};
          for (const t of msg.result.tools) {
            const prefix = t.name.split('_').slice(0, 3).join('_');
            if (!groups[prefix]) groups[prefix] = [];
            groups[prefix].push(t.name);
          }
          for (const [prefix, tools] of Object.entries(groups).sort()) {
            console.log(`${prefix} (${tools.length}): ${tools.slice(0, 5).join(', ')}${tools.length > 5 ? '...' : ''}`);
          }
        } else if (msg.result) {
          // Tool call result
          const content = msg.result.content;
          if (content && content[0]) {
            const text = content[0].text || JSON.stringify(content[0]);
            console.log(`\n=== TOOL RESULT (id=${msg.id}) ===`);
            console.log(text.substring(0, 2000));
            if (text.length > 2000) console.log(`... (${text.length} chars total)`);
          }
        }
      } catch(e) {}
    }
  }
});

server.stderr.on('data', (data) => {
  const s = data.toString();
  if (s.includes('listening') || s.includes('ready') || s.includes('start')) {
    console.log('SERVER:', s.trim());
  }
});

// Initialize
setTimeout(() => {
  const init = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}};
  server.stdin.write(JSON.stringify(init) + '\n');
}, 3000);

// List tools
setTimeout(() => {
  const listTools = {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}};
  server.stdin.write(JSON.stringify(listTools) + '\n');
}, 5000);

// Test 1: List subscriptions
setTimeout(() => {
  const callTool = {"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"azure_subscription_list","arguments":{}}};
  server.stdin.write(JSON.stringify(callTool) + '\n');
  console.log('\n>>> Calling azure_subscription_list...');
}, 8000);

// Test 2: List resource groups
setTimeout(() => {
  const callTool = {"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"azure_group_list","arguments":{}}};
  server.stdin.write(JSON.stringify(callTool) + '\n');
  console.log('\n>>> Calling azure_group_list...');
}, 12000);

// Test 3: List deployments (cost-related)
setTimeout(() => {
  const callTool = {"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"azure_extension_cli_generate","arguments":{"intent":"list all Azure OpenAI deployments in my subscription","cli-type":"az"}}};
  server.stdin.write(JSON.stringify(callTool) + '\n');
  console.log('\n>>> Calling azure_extension_cli_generate for AOAI deployments...');
}, 16000);

// Exit after tests
setTimeout(() => {
  console.log('\n=== ALL TESTS COMPLETE ===');
  server.kill();
  process.exit(0);
}, 25000);
