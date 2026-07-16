This project uses Azure OpenAI Responses API with key authentication. Read the relevant Azure AI guidance before changing this path.

The customer path is the local Windows browser UI plus a local Python backend calling GPT-5.4 through the AOAI Responses API with medium reasoning. Keep the Python CLI as a validation and recovery interface.

Email output must remain a human-controlled draft. Do not add Graph `sendMail`, SMTP, EWS, Outlook `.Send`, Send-button automation, or any equivalent transmission path.