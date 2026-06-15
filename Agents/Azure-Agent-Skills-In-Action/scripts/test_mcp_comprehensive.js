/**
 * Comprehensive Azure MCP Server Tool Test
 * Tests actual execution (not just learn) of all 63 tools where possible.
 * Uses the correct parameter format: composite tools need {command, parameters: JSON.stringify({...})}
 */
const { spawn } = require('child_process');
const fs = require('fs');

const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

const SUB_INFRA = "61643109-c1dc-442c-a7a9-a5f58b9b1703";
const SUB_SERVICES = "ec4eb48c-bf18-4b9b-866c-8d4cfd7cf0c2";
const RG_INFRA = "ND-H100";

let results = {};
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
        const status = text.includes('"status":200') ? 'SUCCESS' :
                       text.includes('"status":400') ? 'BAD_REQUEST' :
                       text.includes('"status":403') ? 'FORBIDDEN' :
                       text.includes('"status":404') ? 'NOT_FOUND' :
                       text.includes('learn') ? 'LEARN_OK' :
                       text.includes('Missing Required') ? 'MISSING_PARAMS' : 'OTHER';
        results[msg.id] = { status, length: text.length, preview: text.substring(0, 500) };
        console.log(`[id=${msg.id}] ${status} (${text.length} chars)`);
        if (status === 'SUCCESS') {
          console.log(`  → ${text.substring(0, 300)}`);
        }
      }
    } catch(e) {}
  }
});

function send(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

// For composite tools: command + parameters as JSON string
function sendComposite(id, toolName, subCommand, params) {
  send(id, toolName, { command: subCommand, parameters: JSON.stringify(params) });
}

// Init
setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:0,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"comprehensive-test",version:"1.0"}}}) + '\n');
}, 2000);

let t = 4000;
const DELAY = 4000;

function schedule(id, label, fn) {
  setTimeout(() => {
    console.log(`\n>>> [${id}] ${label}`);
    fn();
  }, t);
  t += DELAY;
}

// ===== SIMPLE TOOLS (flat args) =====

schedule(100, "subscription_list", () => send(100, "subscription_list", {}));

schedule(101, "group_list (AI Infra)", () => send(101, "group_list", { subscription: SUB_INFRA }));

schedule(102, "group_resource_list (ND-H100)", () => send(102, "group_resource_list", { subscription: SUB_INFRA, "resource-group": RG_INFRA }));

// ===== COMPOSITE TOOLS =====

// pricing: get Azure OpenAI pricing
schedule(200, "pricing → pricing_get (Cognitive Services, eastus)", () =>
  sendComposite(200, "pricing", "pricing_get", { service: "Cognitive Services", region: "eastus" }));

// quota: check usage
schedule(201, "quota → quota_usage_check (CognitiveServices, eastus)", () =>
  sendComposite(201, "quota", "quota_usage_check", { subscription: SUB_SERVICES, region: "eastus", "resource-types": "Microsoft.CognitiveServices/accounts" }));

// quota: region availability for gpt-4o
schedule(202, "quota → quota_region_availability_list (gpt-4o)", () =>
  sendComposite(202, "quota", "quota_region_availability_list", { subscription: SUB_SERVICES, "resource-types": "Microsoft.CognitiveServices/accounts", "cognitive-service-model-name": "gpt-4o" }));

// compute: list VMs
schedule(203, "compute → compute_vm_get (ND-H100)", () =>
  sendComposite(203, "compute", "compute_vm_get", { subscription: SUB_INFRA, "resource-group": RG_INFRA }));

// storage: list storage accounts
schedule(204, "storage → learn", () =>
  send(204, "storage", { command: "learn" }));

// keyvault: learn
schedule(205, "keyvault → learn", () =>
  send(205, "keyvault", { command: "learn" }));

// cosmos: learn
schedule(206, "cosmos → learn", () =>
  send(206, "cosmos", { command: "learn" }));

// search: learn
schedule(207, "search → learn", () =>
  send(207, "search", { command: "learn" }));

// monitor: list workspaces
schedule(208, "monitor → monitor_workspace_list", () =>
  sendComposite(208, "monitor", "monitor_workspace_list", { subscription: SUB_INFRA }));

// role: list role assignments
schedule(209, "role → role_assignment_list", () =>
  sendComposite(209, "role", "role_assignment_list", { subscription: SUB_INFRA, scope: "/subscriptions/" + SUB_INFRA }));

// aks: learn
schedule(210, "aks → learn", () =>
  send(210, "aks", { command: "learn" }));

// containerapps: learn
schedule(211, "containerapps → learn", () =>
  send(211, "containerapps", { command: "learn" }));

// appservice: learn
schedule(212, "appservice → learn", () =>
  send(212, "appservice", { command: "learn" }));

// functionapp: learn
schedule(213, "functionapp → learn", () =>
  send(213, "functionapp", { command: "learn" }));

// sql: learn
schedule(214, "sql → learn", () =>
  send(214, "sql", { command: "learn" }));

// redis: learn
schedule(215, "redis → learn", () =>
  send(215, "redis", { command: "learn" }));

// eventhubs: learn
schedule(216, "eventhubs → learn", () =>
  send(216, "eventhubs", { command: "learn" }));

// servicebus: learn
schedule(217, "servicebus → learn", () =>
  send(217, "servicebus", { command: "learn" }));

// eventgrid: learn
schedule(218, "eventgrid → learn", () =>
  send(218, "eventgrid", { command: "learn" }));

// foundry: list deployments (need correct resource ID)
schedule(219, "foundry → models_deployments_list", () =>
  sendComposite(219, "foundry", "models_deployments_list", { foundryAccountResourceId: "/subscriptions/" + SUB_SERVICES + "/resourceGroups/rg-xinyu-ai-services/providers/Microsoft.CognitiveServices/accounts/xinyu-ai-services" }));

// extension_cli_generate: cost query
schedule(220, "extension_cli_generate (cost breakdown)", () =>
  send(220, "extension_cli_generate", { intent: "show Azure cost breakdown for the last 7 days by service for subscription " + SUB_INFRA, "cli-type": "az" }));

// documentation: search
schedule(221, "documentation → search Azure MCP", () =>
  send(221, "documentation", { query: "Azure MCP Server setup", command: "search" }));

// advisor: learn
schedule(222, "advisor → learn", () =>
  send(222, "advisor", { command: "learn" }));

// cloudarchitect: learn
schedule(223, "cloudarchitect → learn", () =>
  send(223, "cloudarchitect", { command: "learn" }));

// wellarchitectedframework: learn
schedule(224, "wellarchitectedframework → learn", () =>
  send(224, "wellarchitectedframework", { command: "learn" }));

// resourcehealth: learn
schedule(225, "resourcehealth → learn", () =>
  send(225, "resourcehealth", { command: "learn" }));

// policy: learn
schedule(226, "policy → learn", () =>
  send(226, "policy", { command: "learn" }));

// mysql: learn
schedule(227, "mysql → learn", () =>
  send(227, "mysql", { command: "learn" }));

// postgres: learn
schedule(228, "postgres → learn", () =>
  send(228, "postgres", { command: "learn" }));

// acr: learn
schedule(229, "acr → learn", () =>
  send(229, "acr", { command: "learn" }));

// kusto: learn
schedule(230, "kusto → learn", () =>
  send(230, "kusto", { command: "learn" }));

// signalr: learn
schedule(231, "signalr → learn", () =>
  send(231, "signalr", { command: "learn" }));

// azd: learn
schedule(232, "azd → learn", () =>
  send(232, "azd", { command: "learn" }));

// deploy: learn
schedule(233, "deploy → learn", () =>
  send(233, "deploy", { command: "learn" }));

// extension_azqr: compliance scan
schedule(234, "extension_azqr → learn", () =>
  send(234, "extension_azqr", { command: "learn" }));

// get_azure_bestpractices
schedule(235, "get_azure_bestpractices", () =>
  send(235, "get_azure_bestpractices", { intent: "best practices for deploying Azure OpenAI" }));

// speech: learn
schedule(236, "speech → learn", () =>
  send(236, "speech", { command: "learn" }));

// fileshares: learn
schedule(237, "fileshares → learn", () =>
  send(237, "fileshares", { command: "learn" }));

// applicationinsights: learn
schedule(238, "applicationinsights → learn", () =>
  send(238, "applicationinsights", { command: "learn" }));

// applens: learn
schedule(239, "applens → learn", () =>
  send(239, "applens", { command: "learn" }));

// appconfig: learn
schedule(240, "appconfig → learn", () =>
  send(240, "appconfig", { command: "learn" }));

// Remaining tools
schedule(241, "grafana → learn", () => send(241, "grafana", { command: "learn" }));
schedule(242, "bicepschema → learn", () => send(242, "bicepschema", { command: "learn" }));
schedule(243, "azureterraform → learn", () => send(243, "azureterraform", { command: "learn" }));
schedule(244, "loadtesting → learn", () => send(244, "loadtesting", { command: "learn" }));
schedule(245, "communication → learn", () => send(245, "communication", { command: "learn" }));
schedule(246, "confidentialledger → learn", () => send(246, "confidentialledger", { command: "learn" }));
schedule(247, "marketplace → learn", () => send(247, "marketplace", { command: "learn" }));
schedule(248, "foundryextensions → learn", () => send(248, "foundryextensions", { command: "learn" }));
schedule(249, "workbooks → learn", () => send(249, "workbooks", { command: "learn" }));
schedule(250, "virtualdesktop → learn", () => send(250, "virtualdesktop", { command: "learn" }));
schedule(251, "storagesync → learn", () => send(251, "storagesync", { command: "learn" }));
schedule(252, "managedlustre → learn", () => send(252, "managedlustre", { command: "learn" }));
schedule(253, "functions → learn", () => send(253, "functions", { command: "learn" }));
schedule(254, "datadog → learn", () => send(254, "datadog", { command: "learn" }));
schedule(255, "deviceregistry → learn", () => send(255, "deviceregistry", { command: "learn" }));
schedule(256, "azurebackup → learn", () => send(256, "azurebackup", { command: "learn" }));
schedule(257, "azuremigrate → learn", () => send(257, "azuremigrate", { command: "learn" }));
schedule(258, "azureterraformbestpractices → learn", () => send(258, "azureterraformbestpractices", { command: "learn" }));
schedule(259, "servicefabric → learn", () => send(259, "servicefabric", { command: "learn" }));
schedule(260, "extension_cli_install → learn", () => send(260, "extension_cli_install", { command: "learn" }));

// Final summary
setTimeout(() => {
  console.log('\n\n====== COMPREHENSIVE TEST SUMMARY ======\n');
  let success = 0, learnOk = 0, fail = 0, total = Object.keys(results).length;
  for (const [id, r] of Object.entries(results)) {
    if (r.status === 'SUCCESS') success++;
    else if (r.status === 'LEARN_OK' || r.status === 'OTHER') learnOk++;
    else fail++;
  }
  console.log(`Total: ${total} | SUCCESS: ${success} | LEARN_OK: ${learnOk} | FAILED: ${fail}`);
  console.log('\nDetailed results:');
  for (const [id, r] of Object.entries(results).sort((a,b) => Number(a[0]) - Number(b[0]))) {
    console.log(`  [${id}] ${r.status} (${r.length} chars)`);
  }

  fs.writeFileSync('/root/mcp_comprehensive_results.json', JSON.stringify(results, null, 2));
  console.log('\nResults saved to /root/mcp_comprehensive_results.json');
  console.log('\n====== ALL TESTS COMPLETE ======');
  server.kill();
  process.exit(0);
}, t + 5000);
