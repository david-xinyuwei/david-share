# Fine-tuning the STT Model Whisper

 In this article, we will explore how to fine-tune OpenAI's Whisper speech-to-text (STT) model using a specialized medical speech recognition dataset available on Huggingface. We will demonstrate how to make Whisper better understand and transcribe medical terminology, thereby making it more useful for medical-related speech recognition. The steps outlined in this article are not intended for any form of clinical use, medical diagnosis, or patient care, nor do they provide or support any commercial use.

#### 

#### **Overview of the Fine-tuning Process**

 

1. Select an appropriate dataset
2. Fine-tune the Whisper model
3. Evaluate the fine-tuned model
4. Demonstrate the model using a web application

#### Step 0: Prepare the Environment

 
Before starting the fine-tuning process, ensure you have the following:

**Hardware Requirements:**

- GPU: Required for fine-tuning, with a recommended memory of 24GB or more.

  **Software and Accounts:**

- Huggingface account: Needed to access models and datasets.

- Weights & Biases (wandb) account: Recommended for experiment tracking.

#### 

#### **Step 1: Select the Dataset**

 
We will use a specific medical speech recognition dataset available on Huggingface:

- Dataset Name: `yashtiwari/PaulMooney-Medical-ASR-Data`
- Dataset Features: Contains audio recordings and their corresponding transcriptions, focusing on medical terminology.

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVkls1zIviaJzB6ZOOgkG2tyNzTbnVqGOhTTuufZH9sGPc4WqIqCqVvDvtyVqzuYKMTQTYj4adiaH0w/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

####  

#### **Overview of ASR Components**

 
ASR involves three main components:

1. **Feature Extractor**: Processes raw audio input.
2. **Tokenizer**: Post-processes the model output into text.
3. **Model**: Performs the sequence-to-sequence mapping.

#### **Fine-tuning Steps**

 

1. **Feature Extractor**: Prepare the audio data, ensuring a 16kHz sampling rate, and convert the audio into log-Mel spectrograms.
2. **Tokenizer**: Process the text, converting it into token IDs that the model can understand.
3. **Data Preparation**: Use the WhisperProcessor to simplify the use of the feature extractor and tokenizer.
4. **Data Collation**: Use a custom data collator to prepare the training data.
5. **Evaluation Metrics**: Use Word Error Rate (WER) to evaluate model performance.
6. **Training Setup**: Define training parameters and start the training process.

#### Training and Evaluation

 
We will use Seq2SeqTrainer for training and periodically evaluate the model's performance during the training process. Once training is complete, the model can be pushed to the Huggingface Hub for easy sharing and usage.



**Resource Overhead During Training**

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVkls1zIviaJzB6ZOOgkG2tyyKGqgqNK2wFco68RxsEktrBicJVugcXqLk7Hzj84aydTceWNibibpJMdQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

**Loss Function During Training**

**Word Error Rate (WER)** is a metric used to measure the performance of an Automatic Speech Recognition (ASR) system. It calculates the difference between the system-generated transcription and the reference text. The formula for WER is as follows:

[ \text{WER} = \frac{\text{Number of Substitutions} + \text{Number of Deletions} + \text{Number of Insertions}}{\text{Total Number of Words in the Reference Text}} ]

Specifically:

- **Number of Substitutions**: The count of words in the system transcription that do not match the words in the reference text.

- **Number of Deletions**: The count of words that are present in the reference text but missing in the system transcription.

- **Number of Insertions**: The count of words that are present in the system transcription but not in the reference text.

- **Total Number of Words in the Reference Text**: The total word count in the reference text.

  A lower WER indicates higher transcription accuracy of the model. The WER values shown in the image reflect the model's word error rate at different training steps (Step).

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVkls1zIviaJzB6ZOOgkG2tyoSXJUdFP2wasNJIKZXPent3ZyDibaicdprhnfWheheVvKviatLuicZaRbQ/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

From the above figure, it can be observed that the relationship between the loss functions (Training Loss and Validation Loss) and Word Error Rate (WER) during training is not always linear. Here are some possible reasons explaining why the loss function decreases while WER increases:

1. **Overfitting**: The model performs well on the training set (loss function decreases) but poorly on the validation set (WER increases). This could be because the model is overfitting the training data and cannot generalize well to unseen data.

2. **Difference Between Loss Function and Evaluation Metric**: The loss function and WER are different evaluation standards. The loss function is usually based on the model's predicted probabilities, while WER is based on the final transcription results. The model might be optimizing the loss function without directly optimizing WER.

3. **Data Imbalance**: There might be an imbalance between the training and validation datasets, causing the model to perform well on certain types of data but poorly on others.

4. **Randomness and Fluctuations**: The model's performance can fluctuate at different stages of training. Even if the overall trend is a decreasing loss function, WER might temporarily increase at certain steps.

5. **Hyperparameter Settings**: The settings of hyperparameters such as learning rate and batch size can affect the training process. If the learning rate is too high, the model might become unstable during training.

   To further analyze, consider the following measures:

- Check the distribution of the training and validation datasets to ensure consistency.

- Adjust hyperparameters such as learning rate and batch size.

- Use early stopping strategies to prevent overfitting.

- Monitor additional evaluation metrics to gain a comprehensive understanding of the model's performance.

  The experimental results are quite promising:

![图片](https://mmbiz.qpic.cn/mmbiz_png/akGXyic486nVkls1zIviaJzB6ZOOgkG2tyK5JRgLuCbGnuunaF6R50icB1bVZrJWwAo04qcunMmcxqg7zFe2Ocl2Q/640?wx_fmt=png&from=appmsg&tp=webp&wxfrom=5&wx_lazy=1&wx_co=1)

## Code

In code.ipynb


*Refer to*：

*https://medium.com/@mahendra0203/fine-tuning-an-ai-speech-to-text-model-for-medical-transcription-b05397e0e1e1*

*https://github.com/mahendra0203/whisper-finetuning/tree/main*
