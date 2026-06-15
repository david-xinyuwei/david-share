/**
 * EXECUTE ALL — Actually run every MCP tool (not just learn)
 * Uses correct parameter format: composite tools need {command, parameters: JSON.stringify({...})}
 */
const { spawn } = require('child_process');
const fs = require('fs');

const server = spawn('npx', ['-y', '@azure/mcp@latest', 'server', 'start'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

const SUB = "61643109-c1dc-442c-a7a9-a5f58b9b1703"; // AI GBB - AI Infra (has Reader)
const RG = "ND-H100";
const VM = "gok-h100-post-training";

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
                       text.includes('"status":500') ? 'SERVER_ERROR' :
                       text.includes('Missing Required') ? 'MISSING_PARAMS' :
                       text.includes('learn') ? 'LEARN_FALLBACK' : 'OTHER';
        results[msg.id] = { status, length: text.length, preview: text.substring(0, 800) };
        console.log(`[id=${msg.id}] ${status} (${text.length} chars)`);
        if (status === 'SUCCESS') {
          console.log(`  preview: ${text.substring(0, 400)}`);
        } else if (status !== 'LEARN_FALLBACK' && status !== 'OTHER') {
          console.log(`  error: ${text.substring(0, 200)}`);
        }
      }
    } catch(e) {}
  }
});

function send(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

// Composite tool: parameters must be a JSON string
function exec(id, tool, subcmd, params) {
  send(id, tool, { command: subcmd, parameters: JSON.stringify(params) });
}

// Init
setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:0,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"execute-all",version:"1.0"}}}) + '\n');
}, 2000);

let t = 4000;
const D = 5000; // 5s between calls to avoid rate limiting

function q(id, label, fn) {
  setTimeout(() => { console.log(`\n>>> [${id}] ${label}`); fn(); }, t);
  t += D;
}

// ======== SIMPLE TOOLS (flat args) ========
q(1, "subscription_list", () => send(1, "subscription_list", {}));
q(2, "group_list", () => send(2, "group_list", { subscription: SUB }));
q(3, "group_resource_list (ND-H100)", () => send(3, "group_resource_list", { subscription: SUB, "resource-group": RG }));

// ======== COMPUTE ========
q(10, "compute → compute_vm_get (list VMs)", () => exec(10, "compute", "compute_vm_get", { subscription: SUB, "resource-group": RG }));
q(11, "compute → compute_vm_get (specific VM + instance-view)", () => exec(11, "compute", "compute_vm_get", { subscription: SUB, "resource-group": RG, "vm-name": VM, "instance-view": true }));

// ======== PRICING ========
q(20, "pricing → pricing_get (VM Standard_D2ads_v5 eastus)", () => exec(20, "pricing", "pricing_get", { sku: "Standard_D2ads_v5", region: "eastus" }));
q(21, "pricing → pricing_get (Cognitive Services eastus)", () => exec(21, "pricing", "pricing_get", { service: "Cognitive Services", region: "eastus" }));

// ======== QUOTA ========
q(30, "quota → quota_usage_check (CognitiveServices eastus)", () => exec(30, "quota", "quota_usage_check", { subscription: SUB, region: "eastus", "resource-types": "Microsoft.CognitiveServices/accounts" }));
q(31, "quota → quota_usage_check (Compute eastus)", () => exec(31, "quota", "quota_usage_check", { subscription: SUB, region: "southafricanorth", "resource-types": "Microsoft.Compute/virtualMachines" }));
q(32, "quota → quota_region_availability_list (ContainerApps)", () => exec(32, "quota", "quota_region_availability_list", { subscription: SUB, "resource-types": "Microsoft.App/containerApps" }));

// ======== MONITOR ========
q(40, "monitor → monitor_workspace_list", () => exec(40, "monitor", "monitor_workspace_list", { subscription: SUB }));

// ======== ROLE / RBAC ========
q(50, "role → role_assignment_list", () => exec(50, "role", "role_assignment_list", { subscription: SUB, scope: "/subscriptions/" + SUB }));

// ======== STORAGE ========
q(60, "storage → storage_account_list", () => exec(60, "storage", "storage_account_list", { subscription: SUB }));

// ======== KEYVAULT ========
q(61, "keyvault → keyvault_list", () => exec(61, "keyvault", "keyvault_list", { subscription: SUB }));

// ======== COSMOS ========
q(62, "cosmos → cosmos_account_list", () => exec(62, "cosmos", "cosmos_account_list", { subscription: SUB }));

// ======== SQL ========
q(63, "sql → sql_server_list", () => exec(63, "sql", "sql_server_list", { subscription: SUB }));

// ======== REDIS ========
q(64, "redis → redis_list", () => exec(64, "redis", "redis_list", { subscription: SUB }));

// ======== MYSQL ========
q(65, "mysql → mysql_server_list", () => exec(65, "mysql", "mysql_server_list", { subscription: SUB }));

// ======== POSTGRES ========
q(66, "postgres → postgres_server_list", () => exec(66, "postgres", "postgres_server_list", { subscription: SUB }));

// ======== ACR ========
q(67, "acr → acr_list", () => exec(67, "acr", "acr_list", { subscription: SUB }));

// ======== AKS ========
q(70, "aks → aks_list", () => exec(70, "aks", "aks_list", { subscription: SUB }));

// ======== CONTAINER APPS ========
q(71, "containerapps → containerapps_list", () => exec(71, "containerapps", "containerapps_list", { subscription: SUB }));

// ======== APP SERVICE ========
q(72, "appservice → appservice_list", () => exec(72, "appservice", "appservice_list", { subscription: SUB }));

// ======== FUNCTION APP ========
q(73, "functionapp → functionapp_list", () => exec(73, "functionapp", "functionapp_list", { subscription: SUB }));

// ======== EVENT HUBS ========
q(74, "eventhubs → eventhubs_namespace_list", () => exec(74, "eventhubs", "eventhubs_namespace_list", { subscription: SUB }));

// ======== SERVICE BUS ========
q(75, "servicebus → servicebus_namespace_list", () => exec(75, "servicebus", "servicebus_namespace_list", { subscription: SUB }));

// ======== EVENT GRID ========
q(76, "eventgrid → eventgrid_topic_list", () => exec(76, "eventgrid", "eventgrid_topic_list", { subscription: SUB }));

// ======== SIGNALR ========
q(77, "signalr → signalr_list", () => exec(77, "signalr", "signalr_list", { subscription: SUB }));

// ======== SEARCH (AI Search) ========
q(78, "search → search_service_list", () => exec(78, "search", "search_service_list", { subscription: SUB }));

// ======== APP INSIGHTS ========
q(80, "applicationinsights → applicationinsights_list", () => exec(80, "applicationinsights", "applicationinsights_list", { subscription: SUB }));

// ======== RESOURCE HEALTH ========
q(81, "resourcehealth → resourcehealth_list", () => exec(81, "resourcehealth", "resourcehealth_list", { subscription: SUB }));

// ======== ADVISOR ========
q(82, "advisor → advisor_recommendation_list", () => exec(82, "advisor", "advisor_recommendation_list", { subscription: SUB }));

// ======== POLICY ========
q(83, "policy → policy_assignment_list", () => exec(83, "policy", "policy_assignment_list", { subscription: SUB }));

// ======== FOUNDRY ========
q(90, "foundry → models_catalog_list", () => exec(90, "foundry", "models_catalog_list", { foundryAccountResourceId: "/subscriptions/" + SUB + "/resourceGroups/srepan-rg/providers/Microsoft.CognitiveServices/accounts/srepan-ai" }));

// ======== KUSTO / ADX ========
q(91, "kusto → kusto_cluster_list", () => exec(91, "kusto", "kusto_cluster_list", { subscription: SUB }));

// ======== APP CONFIG ========
q(92, "appconfig → appconfig_list", () => exec(92, "appconfig", "appconfig_list", { subscription: SUB }));

// ======== GRAFANA ========
q(93, "grafana → grafana_list", () => exec(93, "grafana", "grafana_list", { subscription: SUB }));

// ======== LOAD TESTING ========
q(94, "loadtesting → loadtesting_list", () => exec(94, "loadtesting", "loadtesting_list", { subscription: SUB }));

// ======== DOCUMENTATION ========
q(95, "documentation (search)", () => send(95, "documentation", { query: "How to deploy Azure OpenAI models" }));

// ======== CLI GENERATE ========
q(96, "extension_cli_generate (cost query)", () => send(96, "extension_cli_generate", { intent: "show Azure cost breakdown for last 7 days by service for subscription " + SUB, "cli-type": "az" }));
q(97, "extension_cli_generate (list AOAI deployments)", () => send(97, "extension_cli_generate", { intent: "list all Azure OpenAI model deployments in subscription " + SUB, "cli-type": "az" }));

// ======== BEST PRACTICES ========
q(98, "get_azure_bestpractices", () => send(98, "get_azure_bestpractices", { intent: "best practices for deploying AI agents on Azure" }));

// ======== CLOUD ARCHITECT ========
q(99, "cloudarchitect → suggest_architecture", () => exec(99, "cloudarchitect", "suggest_architecture", { description: "I need to deploy a RAG-based AI agent that uses Azure OpenAI and AI Search, serving 1000 concurrent users" }));

// ======== WELL ARCHITECTED FRAMEWORK ========
q(100, "wellarchitectedframework → review", () => exec(100, "wellarchitectedframework", "review", { description: "Web app on Container Apps with Cosmos DB backend" }));

// ======== FILE SHARES ========
q(101, "fileshares → fileshares_list", () => exec(101, "fileshares", "fileshares_list", { subscription: SUB }));

// ======== VIRTUAL DESKTOP ========
q(102, "virtualdesktop → virtualdesktop_hostpool_list", () => exec(102, "virtualdesktop", "virtualdesktop_hostpool_list", { subscription: SUB }));

// ======== STORAGE SYNC ========
q(103, "storagesync → storagesync_list", () => exec(103, "storagesync", "storagesync_list", { subscription: SUB }));

// ======== WORKBOOKS ========
q(104, "workbooks → workbooks_list", () => exec(104, "workbooks", "workbooks_list", { subscription: SUB }));

// ======== AZD ========
q(105, "azd → azd_env_list", () => exec(105, "azd", "azd_env_list", {}));

// ======== DEPLOY ========
q(106, "deploy → deploy_list", () => exec(106, "deploy", "deploy_list", { subscription: SUB, "resource-group": RG }));

// ======== EXTENSION AZQR ========
q(107, "extension_azqr (compliance scan)", () => send(107, "extension_azqr", { subscription: SUB }));

// ======== COMMUNICATION ========
q(108, "communication → communication_service_list", () => exec(108, "communication", "communication_service_list", { subscription: SUB }));

// ======== SPEECH ========
q(109, "speech → speech_list", () => exec(109, "speech", "speech_list", { subscription: SUB }));

// ======== MARKETPLACE ========
q(110, "marketplace → marketplace_search", () => exec(110, "marketplace", "marketplace_search", { query: "Azure OpenAI" }));

// ======== BACKUP ========
q(111, "azurebackup → azurebackup_vault_list", () => exec(111, "azurebackup", "azurebackup_vault_list", { subscription: SUB }));

// ======== MIGRATE ========
q(112, "azuremigrate → azuremigrate_project_list", () => exec(112, "azuremigrate", "azuremigrate_project_list", { subscription: SUB }));

// ======== TERRAFORM ========
q(113, "azureterraform → azureterraform_validate", () => exec(113, "azureterraform", "azureterraform_validate", { directory: "/tmp" }));

// ======== BICEP ========
q(114, "bicepschema → bicepschema_get", () => exec(114, "bicepschema", "bicepschema_get", { "resource-type": "Microsoft.CognitiveServices/accounts" }));

// ======== TERRAFORM BEST PRACTICES ========
q(115, "azureterraformbestpractices", () => send(115, "azureterraformbestpractices", { query: "best practices for Azure OpenAI terraform deployment" }));

// ======== APPLENS ========
q(116, "applens → applens_diagnostic_list", () => exec(116, "applens", "applens_diagnostic_list", { subscription: SUB }));

// ======== DATADOG ========
q(117, "datadog → datadog_monitor_list", () => exec(117, "datadog", "datadog_monitor_list", { subscription: SUB }));

// ======== SERVICE FABRIC ========
q(118, "servicefabric → servicefabric_cluster_list", () => exec(118, "servicefabric", "servicefabric_cluster_list", { subscription: SUB }));

// ======== FOUNDRY EXTENSIONS ========
q(119, "foundryextensions → foundryextensions_list", () => exec(119, "foundryextensions", "foundryextensions_list", { subscription: SUB }));

// ======== DEVICE REGISTRY ========
q(120, "deviceregistry → deviceregistry_list", () => exec(120, "deviceregistry", "deviceregistry_list", { subscription: SUB }));

// ======== MANAGED LUSTRE ========
q(121, "managedlustre → managedlustre_list", () => exec(121, "managedlustre", "managedlustre_list", { subscription: SUB }));

// ======== CONFIDENTIAL LEDGER ========
q(122, "confidentialledger → confidentialledger_list", () => exec(122, "confidentialledger", "confidentialledger_list", { subscription: SUB }));

// ======== FUNCTIONS ========
q(123, "functions → learn (no list cmd)", () => send(123, "functions", { command: "learn" }));

// ======== EXTENSION CLI INSTALL ========
q(124, "extension_cli_install → learn", () => send(124, "extension_cli_install", { command: "learn" }));

// Final summary
setTimeout(() => {
  console.log('\n\n====== EXECUTE-ALL SUMMARY ======\n');
  const cats = {SUCCESS:0, BAD_REQUEST:0, FORBIDDEN:0, NOT_FOUND:0, MISSING_PARAMS:0, LEARN_FALLBACK:0, OTHER:0, SERVER_ERROR:0};
  for (const v of Object.values(results)) cats[v.status] = (cats[v.status]||0)+1;
  const total = Object.keys(results).length;
  console.log(`Total: ${total}`);
  for (const [k,v] of Object.entries(cats)) if(v>0) console.log(`  ${k}: ${v}`);
  console.log('\nPer-tool:');
  for (const [id, r] of Object.entries(results).sort((a,b) => Number(a[0]) - Number(b[0]))) {
    console.log(`  [${id}] ${r.status} (${r.length} chars)`);
  }
  fs.writeFileSync('/root/mcp_execute_all_results.json', JSON.stringify(results, null, 2));
  console.log('\nSaved to /root/mcp_execute_all_results.json');
  console.log('====== DONE ======');
  server.kill();
  process.exit(0);
}, t + 10000);
