# Meeting Agent Customer Start Here

This package contains the source, locked dependencies, synthetic meeting examples, editable PowerPoint template, tests, and customer runbook for the local Windows Meeting Agent.

## Supported End-to-End Path

Use native Windows PowerShell. The complete path is:

`Meeting JSON -> local browser UI -> Azure OpenAI GPT-5.4 -> six-card mind map/PPTX -> unsent New Outlook draft`

### Prerequisites

- Windows 11 with New Outlook
- Python 3.12
- Node.js 22 or newer
- An existing Azure OpenAI endpoint, deployment name, and API key
- The Azure OpenAI resource must have local authentication enabled

### Start

```powershell
Set-Location .\Meeting-Agent
.\scripts\start-ui-key.ps1 `
	-Endpoint "https://<your-resource>.openai.azure.com/" `
	-Deployment "gpt-5.4"
```

Paste the API key into the hidden prompt and press Enter. The key is not displayed, stored in a file, or sent to the browser.

Open `http://127.0.0.1:4173`, choose **Meeting JSON**, upload `examples/meeting-record-stargate.json`, and select **Generate meeting package**.

Accept the result only when the page shows Azure OpenAI, `gpt-5.4 · reasoning medium · key auth`, six completed stages, the six-card mind map, an editable six-slide PowerPoint, and an unsent New Outlook draft with the same inline map. Email transmission always requires a human to select **Send**.

If the launcher returns `403 AuthenticationTypeDisabled`, ask the Azure resource administrator to set `disableLocalAuth=false`. Key mode uses an existing resource and does not deploy Azure infrastructure.

See [README.md](README.md) for the complete runbook, architecture, validation evidence, troubleshooting, and Linux/macOS backend-only path.