/**
 * Skills vs No-Skills Comparison Test
 *
 * Tests 10 high-value scenarios on Xinyu Wei's personal subscription
 * (Owner permission, rich resources: 8 VMs, 19 Cognitive Services,
 *  20 Log Analytics workspaces, 10 Storage accounts, 8 ML workspaces).
 *
 * For each scenario: actually executes the MCP tool and captures the result.
 * Pairs with bash CLI commands for "without skills" comparison.
 */
const { spawn } = require('child_process');
const fs = require('fs');

const SUB = "08f95cfd-64fe-4187-99bb-7b3e661c4cde"; // Personal sub

const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

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
                       text.includes('Missing Required') ? 'MISSING_PARAMS' :
                       text.includes('learn') ? 'LEARN_FALLBACK' : 'OTHER';
        results[msg.id] = { status, length: text.length, preview: text.substring(0, 1500) };
        console.log(`\n[id=${msg.id}] ${status} (${text.length} chars)`);
        if (status === 'SUCCESS' || status === 'OTHER') {
          console.log(text.substring(0, 1500));
        }
      }
    } catch(e) {}
  }
});

function send(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

function exec(id, tool, subcmd, params) {
  send(id, tool, { command: subcmd, parameters: JSON.stringify(params) });
}

setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:0,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"comparison-test",version:"1.0"}}}) + '\n');
}, 2000);

let t = 4000;
const D = 6000; // 6s between calls

function q(id, label, fn) {
  setTimeout(() => { console.log(`\n>>> [${id}] ${label}`); fn(); }, t);
  t += D;
}

// ============================================================
// SCENARIO 1: List all subscriptions
// CLI:  az account list --query "[].{name:name,id:id}" -o table
// MCP:  subscription_list (no params)
// ============================================================
q(1, "[Scenario 1] List all subscriptions", () => send(1, "subscription_list", {}));

// ============================================================
// SCENARIO 2: List all resource groups in personal sub
// CLI:  az group list --subscription $SUB -o table
// MCP:  group_list with subscription
// ============================================================
q(2, "[Scenario 2] List resource groups", () => send(2, "group_list", { subscription: SUB }));

// ============================================================
// SCENARIO 3: Inventory all resources in a specific RG
// CLI:  az resource list --resource-group winvm --subscription $SUB -o table
// MCP:  group_resource_list
// ============================================================
q(3, "[Scenario 3] List resources in 'winvm' RG", () => send(3, "group_resource_list", { subscription: SUB, "resource-group": "winvm" }));

// ============================================================
// SCENARIO 4: Get all VMs in a resource group
// CLI:  az vm list --resource-group H100VM_group --subscription $SUB -o table
// MCP:  compute → compute_vm_get
// ============================================================
q(4, "[Scenario 4] List VMs in H100VM_group", () => exec(4, "compute", "compute_vm_get", { subscription: SUB, "resource-group": "H100VM_group" }));

// ============================================================
// SCENARIO 5: Check Azure OpenAI quota for a region
// CLI:  Complex — requires az rest call to quota API
// MCP:  quota → quota_usage_check (one-line call)
// ============================================================
q(5, "[Scenario 5] Check CognitiveServices quota in eastus", () => exec(5, "quota", "quota_usage_check", { subscription: SUB, region: "eastus", "resource-types": "Microsoft.CognitiveServices/accounts" }));

// ============================================================
// SCENARIO 6: Find regions where gpt-4o is available
// CLI:  Very complex — requires multiple API calls
// MCP:  quota → quota_region_availability_list
// ============================================================
q(6, "[Scenario 6] Find regions where gpt-4o is available", () => exec(6, "quota", "quota_region_availability_list", { subscription: SUB, "resource-types": "Microsoft.CognitiveServices/accounts", "cognitive-service-model-name": "gpt-4o" }));

// ============================================================
// SCENARIO 7: List all storage accounts
// CLI:  az storage account list --subscription $SUB -o table
// MCP:  storage → storage_account_list
// ============================================================
q(7, "[Scenario 7] List storage accounts", () => exec(7, "storage", "storage_account_list", { subscription: SUB }));

// ============================================================
// SCENARIO 8: List all Key Vaults
// CLI:  az keyvault list --subscription $SUB -o table
// MCP:  keyvault
// ============================================================
q(8, "[Scenario 8] List Key Vaults (try keyvault_list)", () => exec(8, "keyvault", "keyvault_list", { subscription: SUB }));

// ============================================================
// SCENARIO 9: List Log Analytics workspaces
// CLI:  az monitor log-analytics workspace list --subscription $SUB
// MCP:  monitor → monitor_workspace_list
// ============================================================
q(9, "[Scenario 9] List Log Analytics workspaces", () => exec(9, "monitor", "monitor_workspace_list", { subscription: SUB }));

// ============================================================
// SCENARIO 10: Get RBAC role assignments at subscription scope
// CLI:  az role assignment list --scope /subscriptions/$SUB
// MCP:  role → role_assignment_list
// ============================================================
q(10, "[Scenario 10] List RBAC role assignments", () => exec(10, "role", "role_assignment_list", { subscription: SUB, scope: "/subscriptions/" + SUB }));

// ============================================================
// SCENARIO 11: List Cognitive Services accounts (Azure OpenAI)
// MCP: try foundry  approach
// ============================================================
q(11, "[Scenario 11] List Cognitive Services via group_resource_list filter", () => send(11, "group_resource_list", { subscription: SUB, "resource-group": "rg-aifoundry6206" }));

// ============================================================
// SCENARIO 12: Get pricing for a specific VM SKU
// CLI:  az vm list-skus + manual pricing lookup
// MCP:  pricing → pricing_get
// ============================================================
q(12, "[Scenario 12] Get pricing for Standard_D2ads_v5 in eastus", () => exec(12, "pricing", "pricing_get", { sku: "Standard_D2ads_v5", region: "eastus" }));

// ============================================================
// SCENARIO 13: List ML workspaces
// MCP: try direct
// ============================================================
q(13, "[Scenario 13] List ML workspaces in rg-aifoundry6206", () => send(13, "group_resource_list", { subscription: SUB, "resource-group": "stargate" }));

// ============================================================
// SCENARIO 14: Generate az CLI command from natural language
// CLI:  Manually construct (requires Azure expertise)
// MCP:  extension_cli_generate
// ============================================================
q(14, "[Scenario 14] Generate CLI: 'find all idle VMs > 30 days'", () => send(14, "extension_cli_generate", { intent: "find all VMs that have been deallocated for more than 30 days in subscription " + SUB, "cli-type": "az" }));

// ============================================================
// SCENARIO 15: Get Azure best practices for a scenario
// CLI:  None — must read docs manually
// MCP:  get_azure_bestpractices
// ============================================================
q(15, "[Scenario 15] Best practices: deploying production AI agents", () => send(15, "get_azure_bestpractices", { intent: "best practices for deploying a production AI agent on Azure with high availability and cost optimization" }));

// ============================================================
// SCENARIO 16: Search Microsoft Learn documentation
// CLI:  None — manual web search
// MCP:  documentation
// ============================================================
q(16, "[Scenario 16] Search docs: 'Azure OpenAI provisioned throughput'", () => send(16, "documentation", { query: "Azure OpenAI provisioned throughput PTU vs pay-as-you-go" }));

// ============================================================
// SCENARIO 17: Get Bicep schema for a resource type
// CLI:  Read https://learn.microsoft.com manually
// MCP:  bicepschema
// ============================================================
q(17, "[Scenario 17] Get Bicep schema for Microsoft.CognitiveServices/accounts", () => exec(17, "bicepschema", "bicepschema_get", { "resource-type": "Microsoft.CognitiveServices/accounts" }));

// ============================================================
// SCENARIO 18: Get Terraform best practices for Azure
// MCP:  azureterraformbestpractices
// ============================================================
q(18, "[Scenario 18] Terraform best practices for AOAI", () => send(18, "azureterraformbestpractices", { query: "Azure OpenAI deployment with Terraform" }));

// ============================================================
// SCENARIO 19: Get Foundry model deployments
// MCP:  foundry
// ============================================================
q(19, "[Scenario 19] List Foundry model deployments", () => exec(19, "foundry", "models_deployments_list", { foundryAccountResourceId: "/subscriptions/" + SUB + "/resourceGroups/rg-aifoundry6206/providers/Microsoft.CognitiveServices/accounts/aifoundry6206" }));

// ============================================================
// SCENARIO 20: Cloud architect — recommend architecture
// CLI:  None — requires architect expertise
// MCP:  cloudarchitect
// ============================================================
q(20, "[Scenario 20] Architect a RAG agent for 1000 users", () => exec(20, "cloudarchitect", "design", { description: "Design a RAG-based AI agent on Azure for 1000 concurrent users with low latency, including AOAI, AI Search, App Service, and observability" }));

// Final summary
setTimeout(() => {
  console.log('\n\n====== COMPARISON TEST SUMMARY ======\n');
  const cats = {};
  for (const v of Object.values(results)) cats[v.status] = (cats[v.status]||0)+1;
  const total = Object.keys(results).length;
  console.log(`Total: ${total}`);
  for (const [k,v] of Object.entries(cats)) console.log(`  ${k}: ${v}`);
  console.log('\nPer-scenario:');
  for (const [id, r] of Object.entries(results).sort((a,b) => Number(a[0]) - Number(b[0]))) {
    console.log(`  [${id}] ${r.status} (${r.length} chars)`);
  }
  fs.writeFileSync('/root/mcp_comparison_results.json', JSON.stringify(results, null, 2));
  console.log('\nSaved to /root/mcp_comparison_results.json');
  console.log('====== DONE ======');
  server.kill();
  process.exit(0);
}, t + 8000);
