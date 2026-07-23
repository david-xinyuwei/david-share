This project uses a Microsoft Foundry Managed Agent through the Responses API with Entra authentication. Read the relevant Foundry guidance before changing this path.

The customer path is the local Windows browser UI plus a local Python artifact backend calling the deployed `managed-meeting-agent`. The cloud Agent owns model orchestration and the `meeting-package` Skill; the local application owns strict event validation, artifacts, and Outlook handoff. Keep the Python CLI as a validation and recovery interface. Do not add an AOAI API-key fallback.

Email output must remain a human-controlled draft. Do not add Graph `sendMail`, SMTP, EWS, Outlook `.Send`, Send-button automation, or any equivalent transmission path.