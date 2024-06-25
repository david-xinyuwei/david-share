# Chinese-PII-With-Azure-Speech-Service
Reference Link：

*https://github.com/microsoft/presidio*

*https://huggingface.co/spaces/presidio/presidio_demo/tree/main*

## 需求描述

在生成式AI中，数据脱敏是一个很关键的步骤，而PII是最核心的部分。也就是说，我们发给LLM云服务的信息，应该是不包含敏感和隐私信息的。

*In generative AI, data anonymization is a critical step, with PII (Personally Identifiable Information) being the most essential aspect. This means that the information we send to cloud-based LLM (Large Language Model) services should not contain any sensitive or private information.*

个人可识别信息(Personally Identifiable Information，PII) 是可以用来识别某人的任何数据。所有直接或间接与个人相关的信息都被视为PII，例如，一个人的姓名、电子邮件地址、电话号码、银行账号和政府颁发的身份证号码等。如今，许多组织收集、存储和处理PII。

*Personally Identifiable Information (PII) refers to any data that can be used to identify an individual. All information that is directly or indirectly related to a person is considered PII, such as a person's name, email address, telephone number, bank account numbers, and government-issued identification numbers, among others. Nowadays, many organizations collect, store, and process PII.*

Azure Language Service可以实现PII的信息过滤（LLM处理后的信息发回到本地后，有可能需要还原成脱敏之前以便业务使用），但无法实现LLM处理后的敏感信息还原。但借助于微软的presidio开源项目，可以实现PII的过滤和还原。

*The Azure Language Service is capable of filtering PII (after the LLM has processed the information and it is sent back locally, it may be necessary to revert it back to its pre-anonymized state for business use), but it cannot restore sensitive information after LLM processing. However, with the help of Microsoft's Presidio open-source project, it is possible to both filter and restore PII.*

![Image text](https://github.com/davidsajare/Chinese-PII-With-Azure-Speech-Service/blob/main/3.png)

presidio可以对接多种开源模型实现PII。但针对中文，经过验证，使用presidio+Azure Language效果是最好的，其他开源模型存在各种各样的不足（英文没有这个问题）。Azure Language可以部署到China 21V和Azure Global。

*Presidio is capable of integrating with various open-source models for PII detection and anonymization. However, for Chinese, it has been verified that the combination of Presidio and Azure Language yields the best results (this issue does not exist with English). Azure Language can be deployed to both China 21Vianet and Azure Global.*

## presidio+Azure Language效果

输入:

我叫孙悟空，其实我是一只好猴，名字叫如来的人说我是坏猴，其实他才是个坏人，我的电话是1234456768，银行卡是31212122112。我的邮箱wukong.sun@xiyouji.com。有取经业务欢迎电话或者邮件联系我。

![Image text](https://github.com/davidsajare/david-share/blob/master/LLMs/Chinese-PII-With-Azure-Speech-Service/1.webp)

*The presidio+Azure Language effect is as follows:*

*Input*

*My name is Sun Wukong, in fact, I am a good monkey, the name of Rudra said I am a bad monkey, in fact, he is the bad guy, my phone number is 1234456768, the bank card is 31212122112. My email wukongsun@journey2thewest.com. There is the business of fetching the scriptures welcome to contact me by phone or email.*

![Image text](https://github.com/davidsajare/david-share/blob/master/LLMs/Chinese-PII-With-Azure-Speech-Service/2.webp)

## 运行demo

下载code目录所有的文件到本地：

*Download all the files in the code directory*


执行命令

*Run the demo:*
pip install -r requirements

streamlit run --server.address 0.0.0.0 presidio_streamlit.py

然后浏览器访问VM的域名加端口号

*Then the browser accesses the VM's domain name plus port number*
