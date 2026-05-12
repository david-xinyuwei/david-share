/**
 * FINAL: Execute ALL 63 MCP tools with CORRECT parameter format.
 * Key fix: composite tools MUST use parameters: JSON.stringify({...})
 * NOT parameters as a flat object alongside command.
 *
 * Personal subscription: 08f95cfd (Owner, rich resources)
 */
const { spawn } = require('child_process');
const fs = require('fs');

const SUB = "08f95cfd-64fe-4187-99bb-7b3e661c4cde";

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
                       text.includes('"status":500') ? 'SERVER_ERROR' :
                       text.includes('Missing Required') ? 'MISSING_PARAMS' :
                       text.includes('"learn"') || text.includes('available command') ? 'LEARN_FALLBACK' : 'OTHER';
        results[msg.id] = { status, length: text.length, text: text.substring(0, 2000) };
        console.log(`[${msg.id}] ${status} (${text.length} chars)`);
      }
    } catch(e) {}
  }
});

// Simple tool: flat args
function simple(id, name, args) {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0", id, method:"tools/call", params:{name, arguments:args}}) + '\n');
}

// Composite tool: command + parameters as JSON STRING (the key fix!)
function composite(id, tool, subcmd, params) {
  simple(id, tool, { command: subcmd, parameters: JSON.stringify(params) });
}

// Init
setTimeout(() => {
  server.stdin.write(JSON.stringify({jsonrpc:"2.0",id:0,method:"initialize",params:{protocolVersion:"2024-11-05",capabilities:{},clientInfo:{name:"final-all",version:"1.0"}}}) + '\n');
}, 2000);

let t = 4000;
const D = 4000;
function q(id, label, fn) {
  setTimeout(() => { console.log(`>>> [${id}] ${label}`); fn(); }, t);
  t += D;
}

// ============= SIMPLE TOOLS =============
q(1, "subscription_list", () => simple(1, "subscription_list", {}));
q(2, "group_list", () => simple(2, "group_list", {subscription: SUB}));
q(3, "group_resource_list (winvm)", () => simple(3, "group_resource_list", {subscription: SUB, "resource-group": "winvm"}));
q(4, "group_resource_list (stargate)", () => simple(4, "group_resource_list", {subscription: SUB, "resource-group": "stargate"}));
q(5, "group_resource_list (rg-aifoundry6206)", () => simple(5, "group_resource_list", {subscription: SUB, "resource-group": "rg-aifoundry6206"}));

// ============= COMPUTE =============
q(10, "compute/compute_vm_get (H100VM_group)", () => composite(10, "compute", "compute_vm_get", {subscription: SUB, "resource-group": "H100VM_group"}));
q(11, "compute/compute_vm_get (winvm)", () => composite(11, "compute", "compute_vm_get", {subscription: SUB, "resource-group": "winvm"}));
q(12, "compute/compute_vm_get (A100VM_group)", () => composite(12, "compute", "compute_vm_get", {subscription: SUB, "resource-group": "A100VM_group"}));

// ============= PRICING =============
q(20, "pricing/pricing_get (VM D2ads_v5)", () => composite(20, "pricing", "pricing_get", {sku: "Standard_D2ads_v5", region: "eastus"}));
q(21, "pricing/pricing_get (VM NC24ads_A100)", () => composite(21, "pricing", "pricing_get", {sku: "Standard_NC24ads_A100_v4", region: "eastus"}));

// ============= QUOTA =============
q(30, "quota/quota_usage_check (CogSvc eastus)", () => composite(30, "quota", "quota_usage_check", {subscription: SUB, region: "eastus", "resource-types": "Microsoft.CognitiveServices/accounts"}));
q(31, "quota/quota_usage_check (Compute koreacentral)", () => composite(31, "quota", "quota_usage_check", {subscription: SUB, region: "koreacentral", "resource-types": "Microsoft.Compute/virtualMachines"}));
q(32, "quota/quota_region_availability (gpt-4o)", () => composite(32, "quota", "quota_region_availability_list", {subscription: SUB, "resource-types": "Microsoft.CognitiveServices/accounts", "cognitive-service-model-name": "gpt-4o"}));

// ============= STORAGE =============
q(40, "storage/storage_account_list", () => composite(40, "storage", "storage_account_list", {subscription: SUB}));
q(41, "storage/storage_container_list", () => composite(41, "storage", "storage_container_list", {subscription: SUB, "resource-group": "rg-llm-memory-new", "account-name": "llmmemorypgstorage"}));

// ============= KEYVAULT =============
q(50, "keyvault/keyvault_list", () => composite(50, "keyvault", "keyvault_list", {subscription: SUB}));

// ============= COSMOS =============
q(51, "cosmos/cosmos_account_list", () => composite(51, "cosmos", "cosmos_account_list", {subscription: SUB}));

// ============= SQL =============
q(52, "sql/sql_server_list", () => composite(52, "sql", "sql_server_list", {subscription: SUB}));

// ============= REDIS =============
q(53, "redis/redis_list", () => composite(53, "redis", "redis_list", {subscription: SUB}));

// ============= MYSQL =============
q(54, "mysql/mysql_server_list", () => composite(54, "mysql", "mysql_server_list", {subscription: SUB}));

// ============= POSTGRES =============
q(55, "postgres/postgres_server_list", () => composite(55, "postgres", "postgres_server_list", {subscription: SUB}));

// ============= ACR =============
q(56, "acr/acr_list", () => composite(56, "acr", "acr_list", {subscription: SUB}));

// ============= AKS =============
q(60, "aks/aks_list", () => composite(60, "aks", "aks_list", {subscription: SUB}));

// ============= CONTAINER APPS =============
q(61, "containerapps/containerapps_list", () => composite(61, "containerapps", "containerapps_list", {subscription: SUB}));

// ============= APP SERVICE =============
q(62, "appservice/appservice_list", () => composite(62, "appservice", "appservice_list", {subscription: SUB}));

// ============= FUNCTION APP =============
q(63, "functionapp/functionapp_list", () => composite(63, "functionapp", "functionapp_list", {subscription: SUB}));

// ============= EVENT HUBS =============
q(64, "eventhubs/eventhubs_namespace_list", () => composite(64, "eventhubs", "eventhubs_namespace_list", {subscription: SUB}));

// ============= SERVICE BUS =============
q(65, "servicebus/servicebus_namespace_list", () => composite(65, "servicebus", "servicebus_namespace_list", {subscription: SUB}));

// ============= EVENT GRID =============
q(66, "eventgrid/eventgrid_topic_list", () => composite(66, "eventgrid", "eventgrid_topic_list", {subscription: SUB}));

// ============= SIGNALR =============
q(67, "signalr/signalr_list", () => composite(67, "signalr", "signalr_list", {subscription: SUB}));

// ============= SEARCH =============
q(68, "search/search_service_list", () => composite(68, "search", "search_service_list", {subscription: SUB}));

// ============= MONITOR =============
q(70, "monitor/monitor_workspace_list", () => composite(70, "monitor", "monitor_workspace_list", {subscription: SUB}));

// ============= ROLE =============
q(71, "role/role_assignment_list", () => composite(71, "role", "role_assignment_list", {subscription: SUB, scope: "/subscriptions/"+SUB}));

// ============= APP INSIGHTS =============
q(72, "applicationinsights/applicationinsights_list", () => composite(72, "applicationinsights", "applicationinsights_list", {subscription: SUB}));

// ============= RESOURCE HEALTH =============
q(73, "resourcehealth/resourcehealth_list", () => composite(73, "resourcehealth", "resourcehealth_list", {subscription: SUB}));

// ============= ADVISOR =============
q(74, "advisor/advisor_recommendation_list", () => composite(74, "advisor", "advisor_recommendation_list", {subscription: SUB}));

// ============= POLICY =============
q(75, "policy/policy_assignment_list", () => composite(75, "policy", "policy_assignment_list", {subscription: SUB}));

// ============= KUSTO =============
q(76, "kusto/kusto_cluster_list", () => composite(76, "kusto", "kusto_cluster_list", {subscription: SUB}));

// ============= APPCONFIG =============
q(77, "appconfig/appconfig_list", () => composite(77, "appconfig", "appconfig_list", {subscription: SUB}));

// ============= GRAFANA =============
q(78, "grafana/grafana_list", () => composite(78, "grafana", "grafana_list", {subscription: SUB}));

// ============= LOAD TESTING =============
q(79, "loadtesting/loadtesting_list", () => composite(79, "loadtesting", "loadtesting_list", {subscription: SUB}));

// ============= SPEECH =============
q(80, "speech/speech_list", () => composite(80, "speech", "speech_list", {subscription: SUB}));

// ============= FILE SHARES =============
q(81, "fileshares/fileshares_list", () => composite(81, "fileshares", "fileshares_list", {subscription: SUB}));

// ============= VIRTUAL DESKTOP =============
q(82, "virtualdesktop/virtualdesktop_hostpool_list", () => composite(82, "virtualdesktop", "virtualdesktop_hostpool_list", {subscription: SUB}));

// ============= STORAGE SYNC =============
q(83, "storagesync/storagesync_list", () => composite(83, "storagesync", "storagesync_list", {subscription: SUB}));

// ============= WORKBOOKS =============
q(84, "workbooks/workbooks_list", () => composite(84, "workbooks", "workbooks_list", {subscription: SUB}));

// ============= FOUNDRY =============
q(90, "foundry/models_deployments_list", () => composite(90, "foundry", "models_deployments_list", {foundryAccountResourceId: "/subscriptions/"+SUB+"/resourceGroups/rg-aifoundry6206/providers/Microsoft.CognitiveServices/accounts/aifoundry6206"}));
q(91, "foundry/models_catalog_list", () => composite(91, "foundry", "models_catalog_list", {foundryAccountResourceId: "/subscriptions/"+SUB+"/resourceGroups/rg-aifoundry6206/providers/Microsoft.CognitiveServices/accounts/aifoundry6206"}));

// ============= DEPLOY =============
q(92, "deploy/deploy_list", () => composite(92, "deploy", "deploy_list", {subscription: SUB, "resource-group": "stargate"}));

// ============= COMMUNICATION =============
q(93, "communication/communication_service_list", () => composite(93, "communication", "communication_service_list", {subscription: SUB}));

// ============= MARKETPLACE =============
q(94, "marketplace/marketplace_search", () => composite(94, "marketplace", "marketplace_search", {query: "Azure OpenAI"}));

// ============= BACKUP =============
q(95, "azurebackup/azurebackup_vault_list", () => composite(95, "azurebackup", "azurebackup_vault_list", {subscription: SUB}));

// ============= MIGRATE =============
q(96, "azuremigrate/azuremigrate_project_list", () => composite(96, "azuremigrate", "azuremigrate_project_list", {subscription: SUB}));

// ============= CONFIDENTIAL LEDGER =============
q(97, "confidentialledger/confidentialledger_list", () => composite(97, "confidentialledger", "confidentialledger_list", {subscription: SUB}));

// ============= MANAGED LUSTRE =============
q(98, "managedlustre/managedlustre_list", () => composite(98, "managedlustre", "managedlustre_list", {subscription: SUB}));

// ============= SERVICE FABRIC =============
q(99, "servicefabric/servicefabric_cluster_list", () => composite(99, "servicefabric", "servicefabric_cluster_list", {subscription: SUB}));

// ============= DATADOG =============
q(100, "datadog/datadog_monitor_list", () => composite(100, "datadog", "datadog_monitor_list", {subscription: SUB}));

// ============= DEVICE REGISTRY =============
q(101, "deviceregistry/deviceregistry_list", () => composite(101, "deviceregistry", "deviceregistry_list", {subscription: SUB}));

// ============= FOUNDRY EXTENSIONS =============
q(102, "foundryextensions/foundryextensions_list", () => composite(102, "foundryextensions", "foundryextensions_list", {subscription: SUB}));

// ============= BICEP SCHEMA =============
q(110, "bicepschema/bicepschema_get (CognitiveServices)", () => composite(110, "bicepschema", "bicepschema_get", {"resource-type": "Microsoft.CognitiveServices/accounts"}));

// ============= TERRAFORM =============
q(111, "azureterraform/azureterraform_validate", () => composite(111, "azureterraform", "azureterraform_validate", {configuration: "resource \"azurerm_resource_group\" \"test\" { name = \"test\" location = \"eastus\" }"}));

// ============= DOCUMENTATION =============
q(112, "documentation (search)", () => simple(112, "documentation", {query: "Azure OpenAI provisioned throughput PTU deployment"}));

// ============= CLI GENERATE =============
q(113, "extension_cli_generate (cost)", () => simple(113, "extension_cli_generate", {intent: "show Azure cost for last 7 days grouped by service for subscription "+SUB, "cli-type": "az"}));
q(114, "extension_cli_generate (AOAI)", () => simple(114, "extension_cli_generate", {intent: "list all Azure OpenAI model deployments in subscription "+SUB, "cli-type": "az"}));
q(115, "extension_cli_generate (idle VMs)", () => simple(115, "extension_cli_generate", {intent: "find all deallocated VMs in subscription "+SUB, "cli-type": "az"}));

// ============= BEST PRACTICES =============
q(116, "get_azure_bestpractices", () => simple(116, "get_azure_bestpractices", {intent: "best practices for deploying production AI agents on Azure with high availability"}));

// ============= TERRAFORM BEST PRACTICES =============
q(117, "azureterraformbestpractices", () => simple(117, "azureterraformbestpractices", {query: "best practices for Azure OpenAI deployment with Terraform"}));

// ============= CLOUD ARCHITECT =============
q(118, "cloudarchitect/design", () => composite(118, "cloudarchitect", "design", {description: "RAG agent for 1000 users with AOAI, AI Search, Container Apps"}));

// ============= WELL ARCHITECTED =============
q(119, "wellarchitectedframework/review", () => composite(119, "wellarchitectedframework", "review", {description: "Container Apps + Cosmos DB web app"}));

// ============= AZD =============
q(120, "azd/azd_env_list", () => composite(120, "azd", "azd_env_list", {}));

// ============= EXTENSION AZQR =============
q(121, "extension_azqr", () => simple(121, "extension_azqr", {subscription: SUB}));

// ============= EXTENSION CLI INSTALL =============
q(122, "extension_cli_install/learn", () => simple(122, "extension_cli_install", {command: "learn"}));

// ============= FUNCTIONS =============
q(123, "functions/learn", () => simple(123, "functions", {command: "learn"}));

// ============= APPLENS =============
q(124, "applens/applens_diagnostic_list", () => composite(124, "applens", "applens_diagnostic_list", {subscription: SUB}));

// Final summary
setTimeout(() => {
  console.log('\n====== FINAL ALL-TOOLS SUMMARY ======');
  const cats = {};
  for (const v of Object.values(results)) cats[v.status] = (cats[v.status]||0)+1;
  console.log(`Total: ${Object.keys(results).length}`);
  for (const [k,v] of Object.entries(cats).sort((a,b)=>b[1]-a[1])) console.log(`  ${k}: ${v}`);
  console.log('\nPer-tool:');
  for (const [id, r] of Object.entries(results).sort((a,b)=>Number(a[0])-Number(b[0]))) {
    console.log(`  [${id}] ${r.status.padEnd(18)} ${String(r.length).padStart(7)} chars`);
  }
  fs.writeFileSync('/root/mcp_final_all.json', JSON.stringify(results, null, 2));
  console.log('\nSaved to /root/mcp_final_all.json');
  console.log('====== DONE ======');
  server.kill();
  process.exit(0);
}, t + 10000);
