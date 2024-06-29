用GPT做机器翻译，比传统的翻译工具如何呢？这方面有很多测试报告，但大多数是2023年上半年做的，而GPT的能力提升很快，因此不进行列举。

从我实测的效果看，可以得出如下的结论。

1. GPT-4翻译段落比翻译句子和词的优势更明显。
2. GPT-4+Prompt可以实现很多传统翻译工具不能完成的任务。



第一条比较容易理解，因此段落具有上下文，翻译出来的内容更精准。就像我用机器翻译工具，经常把LLM翻译成法学博士。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bibAYO9hCcRBpmXn2JhfU2iawPr3YfOKmZ1aWJsBiaBaRiaEZmOgo3XIlFg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

有上下文，机器翻译工具会好些，起码知道LLM不用直译，但也没翻译：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bTPFjeUPib2s3CRsDJmXTf8eiabcHQT5FUeWOicfChnYXXn4uiadYsEXs8w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

使用GPT-4，在没有任何prompt的前提下，翻译的显然比上面的好得多。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bHTXH2f5CPAdtnn6g3jDSUo0BstV7VFqreSrjqAX2Iu4CSg5GBOpaSQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)



针对上面第二条，我们举个例子。

做一个翻译机器人，可以帮着学生把文言文翻译成现代白话文。

首先传统翻译工具无法把文言文翻译成现代中文白话文。

通过google搜索尝试。

比如：解释凌波微步是什么意思

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bex0JicFsgVUHptxZaykTNrEymibcc8JxRne74lMZ8mAxt1l6OUVhG9KA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

结果跑偏。

优化下搜索：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bpTPoPCP4YXcCXof70sJFAWbrv6NpGbsMIEz03s3AnlAou3Orbjdl4g/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

结果准确，但不是翻译出来的，是搜索出来的。在应用中通过调用搜索引擎API实现翻译显然不现实。



GPT4-1106没有任何prompt的前提下尝试：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2b5PCu8Bmopqw0F1tKPgiajUljP956BDt9lyzpd7vicchLR2dAKqmfoASw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

解释基本正确，但格式不理想，至于《射雕》这段描述，也是跑偏。



GPT4-1106使用Prompt：

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bNEPB4xOeibjicy8ykOvlLrzE4xZxjlZFXS8bulLTsnPJianvHwD6xITZw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

我们看到结果就比较理想了。

此外，通过GPT4+Prompt的方式，还可以做一些特殊词的指定。比如，将“大魏”特定解释为“魏新宇”。然后翻译：大魏心振荡而不怡。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bRs0NfDtZs19uUJpUFD1JagblQN7rZUON2DcWeS3vic196iaUCWlPQCKg/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

效果符合预期。



如果我们进行英文句子翻译，也能达到类似的效果。

中文句子用google翻译：大魏说它居然都打不过他

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bicFd7UjVo5AiahfKxYDd9AQEawJt6Gq63ropAEfblmDJkXEjKgDAL0jw/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

不能睡说翻译的不对，但属于直译，不带上下文理解。



使用GPT4+Prompt的方式翻译：大魏说它居然都打不过他。

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nWW0ECeaNkTAkwblDBwwd2bZy82tlOLjzhIxySibca0oKnTCtftwFdYibm7FF26KktCibBjichC5mkhRA/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

效果很理想。

如果是段落，那么GPT4+Prompt的方式优势更加明显。

此外，在处理一些词的翻译时，最好也加上上下文。