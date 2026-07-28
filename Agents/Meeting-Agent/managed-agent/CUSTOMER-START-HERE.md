# Managed Meeting Agent Customer Start Here

This package contains the Foundry-managed implementation path of the Meeting Agent product. The Classic implementation remains available from the same product home.

## Supported Path

`Meeting events -> local Windows UI -> Foundry Managed Agent -> mind map and editable PPTX -> unsent New Outlook draft`

## Prerequisites

- Windows 11 and New Outlook
- Python 3.12
- Node.js 22 or newer
- Azure CLI signed in through a dedicated `AZURE_CONFIG_DIR`
- Foundry access to the deployed `managed-meeting-agent`

## Start

Run in native Windows PowerShell:

```powershell
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.azure-<tenant>-<subscription>"
az account show

.\scripts\start-ui.ps1 `
  -ManagedAgentEndpoint "https://<account>.services.ai.azure.com/api/projects/<project>/openai/v1/responses" `
  -ManagedAgentName "managed-meeting-agent" `
  -ManagedAgentVersion "<active-version>" `
  -RequireDeckPlan $true `
  -AzureConfigDir $env:AZURE_CONFIG_DIR
```

Use the active version returned by the deployment/reconciliation output; do not
copy a historical version number from dated evidence.
Current reconciled versions must keep `-RequireDeckPlan $true`; the launcher also
uses this strict default when the switch is omitted. Set it to false only for an
intentional replay of the historical v6 compatibility path.

Open `http://127.0.0.1:4173`, select **Meeting JSON**, upload `examples/meeting-record-stargate.json`, and choose **Generate meeting package**.

## Acceptance

Accept the run only when:

1. The header shows **Foundry Managed Agent** and **entra auth**.
2. All six actual processing stages complete.
3. The page displays a mind map and downloads valid JSON, Mermaid, PNG, PPTX, and EML artifacts.
4. The PowerPoint opens as an editable six-slide deck.
5. New Outlook opens an editable draft with `X-Unsent: 1`, the inline mind map, and PNG/PPTX attachments.
6. The user must select **Send** manually.

The customer path uses no AOAI API key and has no automatic-send capability. See [Managed implementation details](docs/MANAGED-IMPLEMENTATION.md) for architecture, evidence, tests, and boundaries, or return to the [product home](https://github.com/david-xinyuwei/david-share/tree/master/Agents/Meeting-Agent).
