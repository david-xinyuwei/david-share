之前看过一些Prompt Engineer优化的文档，理论结合实践试一下。**本文中使用的数据是我造出来的，不是客户数据。**

假设我是微软的800工程师，我要针对客户提的各种问题进行处理，生成的一个excel表格，表格的列包含Case ID、keywords、Summary、Category。

我们先看原始数据，一共十条：

1. “我无法登录我的帐户。它一直说有服务器错误。”
2. “你能提供有关产品及如何使用它的更多信息吗？”
3. “我的Azure OpenAI应用程序的状态是什么？”
4. “Je ne suis pas sûr si c’est le bon endroit pour demander, mais j’ai une question sur la facturation.”
5. “¿Hay alguna manera de restablecer mi contraseña? No puedo encontrar la opción.”
6. “Ich erhalte eine Fehlermeldung beim Versuch, eine Datei hochzuladen. Können Sie helfen?”
7. “どのくらいの時間がかかりますか、アプリケーションが承認されるまで？”
8. “我不确定这是不是一个错误，但界面似乎出现了故障。”
9. “Can you provide more details about the different subscription options?”
10. “هل هناك طريقة لاستعادة الملفات المحذوفة؟”



我们先看第一个Prompt：

```
Your task is to review customer questions and feedback.The review steps are as follows, please perform step by step.Please categorize the customer’s questions and feedback first. 
If you cannot determine the category, please use “unknown” as Category.
Then, please extract the three keywordsfrom the customer questions and feedback.Please concatenate the three keywords withcommas to make it a complete JSON value.
Then, Please summarize the customer’squestions and feedback in 10 more words.Provide them in JSON format with thefollowing keys: case id; Category; Key-words; Summary.
```

执行：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWf6Iogb0ScBpSFibiavMUk2TJG5vBCwHIENev6nOZFmjf8aqiaVX2W8jCjXCQdrWbMeYVEUibwAor7hQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

执行结果：

```
[{"case_id": 1,"Category": "Login","Key-words": "无法登录, 帐户, 服务器错误","Summary": "Unable to login, server error"},{"case_id": 2,"Category": "Product Information","Key-words": "产品, 使用信息","Summary": "Request for more product and usage information"},{"case_id": 3,"Category": "Azure OpenAI","Key-words": "Azure OpenAI, 应用程序, 状态","Summary": "Inquiry about the status of Azure OpenAI application"},{"case_id": 4,"Category": "Billing","Key-words": "facturation, question, unsure","Summary": "Question about billing, unsure if right place to ask"},{"case_id": 5,"Category": "Password Reset","Key-words": "restablecer contraseña, opción","Summary": "Request for password reset option"},{"case_id": 6,"Category": "File Upload","Key-words": "Fehlermeldung, Datei hochladen, helfen","Summary": "Error message while trying to upload a file, need help"},{"case_id": 7,"Category": "Application Approval","Key-words": "時間, アプリケーション, 承認","Summary": "Inquiry about application approval time"},{"case_id": 8,"Category": "Interface Issue","Key-words": "界面, 故障, 不确定","Summary": "Possible interface issue, unsure if an error"},{"case_id": 9,"Category": "Subscription Options","Key-words": "details, subscription options","Summary": "Request for more details about subscription options"},{"case_id": 10,"Category": "File Recovery","Key-words": "استعادة, الملفات المحذوفة","Summary": "Inquiry about file recovery options"}]
```

感觉输出结果有待提升，结果各种语言都有，分类也很混乱。

看第二个Prompt：

```
Your task is to review customer questions and feedback.
The review steps are as follows, please perform step by step:
1. Please categorize the customer’s questions and feedback first. Category list:    • Technical issue: customer is experiencing server-side issues, client errors or product limitations. Example: "I'm having trouble logging into my account. It keeps saying there's a server error."    • Product inquiry: customer would like to know more details about the product or is asking questions about how to use it. Example: "Can you provide more information about the product and how to use it?"    • Application status: customer is requesting to check the status of their Azure OpenAI, GPT-4 or DALLE application. Example: "What is the status of my Azure OpenAI application?"    • Unknown: if you only have a low confidence score to categorize. Example: "I'm not sure if this is the right place to ask, but I have a question about billing."
2. Then, please extract three keywords from customer questions and translate them into English. Please concatenate the three keywords with commas to make it a complete JSON value.
3. Then, please summarize the customer’s questions and feedback in 10 more words and in English.
运行：
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWf6Iogb0ScBpSFibiavMUk2T8d8RJ5m8vLnujc7eJzflsT7ZG5HpBtFcZoIiajedqF3jXrYtGzUMPibQ/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

执行结果：

```
Technical issueProduct inquiryApplication statusUnknownTechnical issueTechnical issueApplication statusTechnical issueProduct inquiryTechnical issue
["login, account, server error","product, information, how to use","Azure OpenAI, application, status","billing, question, unsure","reset password, option, cannot find","upload file, error message, help","application, approval time, how long","interface, malfunction, unsure","subscription options, details, provide","recover deleted files, method, exist"]
Trouble logging in due to server error.Request for more information and usage instructions about the product.Inquiry about the status of the Azure OpenAI application.Unsure about whether the question is relevant to billing.Request for assistance with resetting a password.Error message when trying to upload a file, seeking help.Question about the time required for application approval.Uncertain if there is a malfunction in the interface.Inquiring about detailed subscription options.Request for a method to recover deleted files.

```

效果比第一个prompt有进步，但输出格式和我们要求相差较大。
我们查看第三个prompt：

```
Your task is to review customer questions and categorize them into one of the following 4 types of problems.
The review steps are as follows, please perform step by step:
1. Extract three keywords from customer questions and translate them into English. Please connect the three keywords with commas to make it a complete JSON value.
2. Summarize the customer’s questions in 15 more words and in English.
3. Categorize the customer’s questions based on Review text and summary. Category list:    • Technical issue: customer is experiencing server-side issues, client errors or product limitations. Example: "I'm having trouble logging into my account. It keeps saying there's a server error."    • Product inquiry: customer would like to know more details about the product or is asking questions about how to use it. Example: "Can you provide more information about the product and how to use it?"    • Application status: customer is requesting to check the status of their Azure OpenAI, GPT-4 or DALLE application. Example: "What is the status of my Azure OpenAI application?"    • Unknown: if you only have a low confidence score to categorize. Example: "I'm not sure if this is the right place to ask, but I have a question about billing."
Provide them in JSON format with the following keys: Case id; Key-words; Summary; Category. Please generate only one JSON structure per review.
再次运行，查看结果：
```

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWf6Iogb0ScBpSFibiavMUk2TnVJGlVJm8yEVFJPNUbVUFdxIdkePgxm07JWFv8bngu59TflsqulWxw/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

```
[{"Case id": 1,"Key-words": "login, account, server error","Summary": "Having trouble logging into my account, server error message.","Category": "Technical issue"},{"Case id": 2,"Key-words": "product, information, how to use","Summary": "Requesting more information about the product and how to use it.","Category": "Product inquiry"},{"Case id": 3,"Key-words": "Azure OpenAI, application, status","Summary": "Checking the status of my Azure OpenAI application.","Category": "Application status"},{"Case id": 4,"Key-words": "not sure, right place, billing","Summary": "Uncertain if this is the right place, question about billing.","Category": "Unknown"},{"Case id": 5,"Key-words": "reset password, option","Summary": "Is there a way to reset my password, cannot find the option.","Category": "Technical issue"},{"Case id": 6,"Key-words": "error message, upload file, help","Summary": "Receiving an error message when trying to upload a file, need assistance.","Category": "Technical issue"},{"Case id": 7,"Key-words": "application, approval time","Summary": "How long does it take for an application to be approved?","Category": "Application status"},{"Case id": 8,"Key-words": "not sure, error, interface","Summary": "Not sure if it's an error, but the interface seems to be malfunctioning.","Category": "Unknown"},{"Case id": 9,"Key-words": "subscription options, details","Summary": "Requesting more details about the different subscription options.","Category": "Product inquiry"},{"Case id": 10,"Key-words": "recover deleted files, option","Summary": "Is there a way to recover deleted files?","Category": "Technical issue"}]
```

返回结果达到我们的要求。在第三个promot基础上最后增加一句：

Please show the output results - in a table, the table is divided into four columns: Case ID, keywords, Summary, Category.

输出的结果就是表格形式：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWf6Iogb0ScBpSFibiavMUk2TohHj9WylLC68Q6yDGOS8hG6PHWqiavicIVNbFbVCWYeKEBMDQ1eg3hRA/640?wx_fmt=png&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)