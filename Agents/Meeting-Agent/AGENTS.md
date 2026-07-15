This project uses Azure OpenAI and retains an optional Microsoft Foundry adapter. Read the relevant Azure AI guidance before changing either path.

The customer path is the local Windows browser UI plus a local Python backend calling GPT-5.4 through the AOAI Responses API with medium reasoning. Keep the optional Hosted adapter and Python CLI as compatibility, validation, and recovery interfaces.

Email output must remain a human-controlled draft. Do not add Graph `sendMail`, SMTP, EWS, Outlook `.Send`, Send-button automation, or any equivalent transmission path.