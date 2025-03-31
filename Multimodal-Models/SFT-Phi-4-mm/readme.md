## SFT Phi-4-multimodal-instruct Audio and Vision Encoders

***Refer to**: https://huggingface.co/microsoft/Phi-4-multimodal-instruct*



Phi-4-multimodal-instruct is a multimodal model capable of processing text input, audio input, and image input. Its architecture is as follows: 

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/SFT-Phi-4-mm/images/1.png)

Next, in this repo, I will separately demonstrate the fine-tuning of the Audio encoder and the model's VQA capabilities (Vision encoder).  In addition, I will also verify the fine-tuning results through a program. 

Before officially starting the training, let's first take a look at the actual performance of the Audio Encoder after training. After training, the model is able to translate English into Slovenian, a capability it did not have before training. 

***Please click below pictures to see my demo video on Youtube***:

[![Phi-4-mm-demo1](https://raw.githubusercontent.com/xinyuwei-david/david-share/refs/heads/master/IMAGES/6.webp)](https://youtu.be/IGaANDJhRLM)

In the SFT process, I used a single H100 GPU, and the resource consumption is approximately as follows: 

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/SFT-Phi-4-mm/images/3.png)

### SFT Audio encoder on Azure NC H100 VM

This section focuses on training the speech translation capability of phi-4-mm. The goal of the training is to enable phi-4-mm to have the following ability: when you input English speech, the model can translate your speech into a minor language and display it in text form. Therefore, when running the script, you need to specify the source and target languages for translation, the number of training epochs, and the location where the trained model will be stored.

In the training script mentioned above, the data dictionaries include three options: `en_zh-CN`, `en_id`, and `en_sl`. However, this does not mean that the script can only train translation capabilities for these few languages. The range of supported languages depends on the `facebook/covost2` in the training script.

It is important to note that `facebook/covost2` is not an actual dataset; it is merely a processing script for corpus data. The true source corpus is derived from the Common Voice Corpus 4 available at: *https://commonvoice.mozilla.org/en/datasets.* 

Install required packages:

```
# pip install -r requires.txt
```

```
# cat requires.txt
flash_attn==2.7.4.post1
torch==2.6.0
transformers==4.48.2
accelerate==1.3.0
soundfile==0.13.1
pillow==11.1.0
scipy==1.15.2
torchvision==0.21.0
backoff==2.2.1
peft==0.13.2
```



Run SFT script:

```
(base) root@h100vm:~/phi4-mm# cat 3.py 
"""
finetune Phi-4-multimodal-instruct on an speech task

scipy==1.15.1
peft==0.13.2
backoff==2.2.1
transformers==4.46.1
accelerate==1.3.0
"""

import argparse
import json
import os
from pathlib import Path

import torch
import sacrebleu
from accelerate import Accelerator
from accelerate.utils import gather_object
from datasets import load_dataset
from torch.utils.data import Dataset
from tqdm import tqdm
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    BatchFeature,
    Trainer,
    TrainingArguments,
    StoppingCriteria,
    StoppingCriteriaList,
)


INSTSRUCTION = {
    "en_zh-CN": "Translate the audio to Mandarin.",
    "en_id": "Translate the audio to Indonesian.",
    "en_sl": "Translate the audio to Slovenian.",
}
TOKENIZER = {
    "en_zh-CN": "zh",
    "en_ja": "ja-mecab",
}
ANSWER_SUFFIX = "<|end|><|endoftext|>"
_IGNORE_INDEX = -100
_TRAIN_SIZE = 50000
_EVAL_SIZE = 200

class MultipleTokenBatchStoppingCriteria(StoppingCriteria):
    """Stopping criteria capable of receiving multiple stop-tokens and handling batched inputs."""

    def __init__(self, stop_tokens: torch.LongTensor, batch_size: int = 1) -> None:
        """Initialize the multiple token batch stopping criteria.

        Args:
            stop_tokens: Stop-tokens.
            batch_size: Batch size.

        """

        self.stop_tokens = stop_tokens
        self.max_stop_tokens = stop_tokens.shape[-1]
        self.stop_tokens_idx = torch.zeros(batch_size, dtype=torch.long, device=stop_tokens.device)

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor, **kwargs) -> bool:
        # Only gather the maximum number of inputs compatible with stop tokens
        # and checks whether generated inputs are equal to `stop_tokens`
        generated_inputs = torch.eq(input_ids[:, -self.max_stop_tokens :].unsqueeze(1), self.stop_tokens)
        equal_generated_inputs = torch.all(generated_inputs, dim=2)

        # Mark the position where a stop token has been produced for each input in the batch,
        # but only if the corresponding entry is not already set
        sequence_idx = torch.any(equal_generated_inputs, dim=1)
        sequence_set_mask = self.stop_tokens_idx == 0
        self.stop_tokens_idx[sequence_idx & sequence_set_mask] = input_ids.shape[-1]

        return torch.all(self.stop_tokens_idx)

class CoVoSTDataset(Dataset):
    def __init__(self, processor, data_dir, split, 
                 lang="en_zh-CN", rank=0, world_size=1):

        self.data = load_dataset("facebook/covost2", 
                           lang, 
                           data_dir=data_dir, 
                           split=split,
                           trust_remote_code=True
                           )
        self.training = "train" in split
        self.processor = processor
        self.instruction = INSTSRUCTION[lang]
        
        if world_size > 1:
            self.data = self.data.shard(world_size, rank) 

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        """
        {'client_id': '0013037a1d45cc33460806cc3f8ecee9d536c45639ba4cbbf1564f1c051f53ff3c9f89ef2f1bf04badf55b3a2e7654c086f903681a7b6299616cff6f67598eff',
        'file': '{data_dir}/clips/common_voice_en_699711.mp3',
        'audio': {'path': '{data_dir}/clips/common_voice_en_699711.mp3',
        'array': array([-1.28056854e-09, -1.74622983e-09, -1.16415322e-10, ...,
                3.92560651e-10,  6.62794264e-10, -3.89536581e-09]),
        'sampling_rate': 16000},
        'sentence': '"She\'ll be all right."',
        'translation': '她会没事的。',
        'id': 'common_voice_en_699711'}
        """
        data = self.data[idx]
        user_message = {
            'role': 'user',
            'content': '<|audio_1|>\n' + self.instruction,
        }
        prompt = self.processor.tokenizer.apply_chat_template(
            [user_message], tokenize=False, add_generation_prompt=True
        )
        inputs = self.processor(text=prompt, audios=[(data["audio"]["array"], data["audio"]["sampling_rate"])], return_tensors='pt')
        
        answer = f"{data['translation']}{ANSWER_SUFFIX}"
        answer_ids = self.processor.tokenizer(answer, return_tensors='pt').input_ids
        if  self.training:
            input_ids = torch.cat([inputs.input_ids, answer_ids], dim=1)
            labels = torch.full_like(input_ids, _IGNORE_INDEX)
            labels[:, -answer_ids.shape[1] :] = answer_ids
        else:
            input_ids = inputs.input_ids
            labels = answer_ids

        return {
            'input_ids': input_ids,
            'labels': labels,
            'input_audio_embeds': inputs.input_audio_embeds,
            'audio_embed_sizes': inputs.audio_embed_sizes,
        }

def pad_sequence(sequences, padding_side='right', padding_value=0):
    """
    Pad a list of sequences to the same length.
    sequences: list of tensors in [seq_len, *] shape
    """
    assert padding_side in ['right', 'left']
    max_size = sequences[0].size()
    trailing_dims = max_size[1:]
    max_len = max(len(seq) for seq in sequences)
    batch_size = len(sequences)
    output = sequences[0].new_full((batch_size, max_len) + trailing_dims, padding_value)
    for i, seq in enumerate(sequences):
        length = seq.size(0)
        if padding_side == 'right':
            output.data[i, :length] = seq
        else:
            output.data[i, -length:] = seq
    return output


def cat_with_pad(tensors, dim, padding_value=0):
    """
    cat along dim, while pad to max for all other dims
    """
    ndim = tensors[0].dim()
    assert all(
        t.dim() == ndim for t in tensors[1:]
    ), 'All tensors must have the same number of dimensions'

    out_size = [max(t.shape[i] for t in tensors) for i in range(ndim)]
    out_size[dim] = sum(t.shape[dim] for t in tensors)
    output = tensors[0].new_full(out_size, padding_value)

    index = 0
    for t in tensors:
        # Create a slice list where every dimension except dim is full slice
        slices = [slice(0, t.shape[d]) for d in range(ndim)]
        # Update only the concat dimension slice
        slices[dim] = slice(index, index + t.shape[dim])

        output[slices] = t
        index += t.shape[dim]

    return output


def covost_collate_fn(batch):
    input_ids_list = []
    labels_list = []
    input_audio_embeds_list = []
    audio_embed_sizes_list = []
    audio_attention_mask_list = []
    for inputs in batch:
        input_ids_list.append(inputs['input_ids'][0])
        labels_list.append(inputs['labels'][0])
        input_audio_embeds_list.append(inputs['input_audio_embeds'])
        audio_embed_sizes_list.append(inputs['audio_embed_sizes'])
        audio_attention_mask_list.append(
            inputs['input_audio_embeds'].new_full((inputs['input_audio_embeds'].size(1),), True, dtype=torch.bool)
        )

    try:
        input_ids = pad_sequence(input_ids_list, padding_side='left', padding_value=0)
        labels = pad_sequence(labels_list, padding_side='left', padding_value=0)
        audio_attention_mask = (
            pad_sequence(audio_attention_mask_list, padding_side='right', padding_value=False)
            if len(audio_attention_mask_list) > 1
            else None
        )
    except Exception as e:
        print(e)
        print(input_ids_list)
        print(labels_list)
        raise
    attention_mask = (input_ids != 0).long()
    input_audio_embeds = cat_with_pad(input_audio_embeds_list, dim=0)
    audio_embed_sizes = torch.cat(audio_embed_sizes_list)

    return BatchFeature(
        {
            'input_ids': input_ids,
            'labels': labels,
            'attention_mask': attention_mask,
            'input_audio_embeds': input_audio_embeds,
            'audio_embed_sizes': audio_embed_sizes,
            'audio_attention_mask': audio_attention_mask,
            'input_mode': 2,  # speech mode
        }
    )



def create_model(model_name_or_path, use_flash_attention=False):
    model = AutoModelForCausalLM.from_pretrained(
        model_name_or_path,
        torch_dtype=torch.bfloat16 if use_flash_attention else torch.float32,
        _attn_implementation='flash_attention_2' if use_flash_attention else 'sdpa',
        trust_remote_code=True,
    ).to('cuda')

    return model


@torch.no_grad()
def evaluate(
    model, processor, eval_dataset, save_path=None, disable_tqdm=False, eval_batch_size=1
):
    rank = int(os.environ.get('RANK', 0))
    local_rank = int(os.environ.get('LOCAL_RANK', 0))

    model.eval()
    all_generated_texts = []
    all_labels = []

    eval_dataloader = torch.utils.data.DataLoader(
        eval_dataset,
        batch_size=eval_batch_size,
        collate_fn=covost_collate_fn,
        shuffle=False,
        drop_last=False,
        num_workers=8,
        prefetch_factor=2,
        pin_memory=True,
    )
    stop_tokens = ["<|end|>", processor.tokenizer.eos_token]
    stop_tokens_ids = processor.tokenizer(stop_tokens, add_special_tokens=False, padding="longest", return_tensors="pt")["input_ids"]
    stop_tokens_ids = stop_tokens_ids.to(f'cuda:{local_rank}')

    for inputs in tqdm(
        eval_dataloader, disable=(rank != 0) or disable_tqdm, desc='running eval'
    ):
        stopping_criteria=StoppingCriteriaList([MultipleTokenBatchStoppingCriteria(stop_tokens_ids, batch_size=inputs.input_ids.size(0))])
        inputs = inputs.to(f'cuda:{local_rank}')
        generated_ids = model.generate(
            **inputs, eos_token_id=processor.tokenizer.eos_token_id, max_new_tokens=64,
            stopping_criteria=stopping_criteria,
        )

        stop_tokens_idx = stopping_criteria[0].stop_tokens_idx.reshape(inputs.input_ids.size(0), -1)[:, 0]

        stop_tokens_idx = torch.where(
            stop_tokens_idx > 0,
            stop_tokens_idx - stop_tokens_ids.shape[-1],
            generated_ids.shape[-1],
        )
        generated_text = [
            processor.decode(_pred_ids[inputs["input_ids"].shape[1] : _stop_tokens_idx], skip_special_tokens=True, clean_up_tokenization_spaces=False)
            for _pred_ids, _stop_tokens_idx in zip(generated_ids, stop_tokens_idx)
        ]
        all_generated_texts.extend(generated_text)
        labels = [processor.decode(_label_ids[_label_ids != 0]).removesuffix(ANSWER_SUFFIX) for _label_ids in inputs["labels"]]
        all_labels.extend(labels)

    all_generated_texts = gather_object(all_generated_texts)
    all_labels = gather_object(all_labels)
    
    if rank == 0:
        assert len(all_generated_texts) == len(all_labels)
        bleu = sacrebleu.corpus_bleu(all_generated_texts, [all_labels])
        print(bleu)
        if save_path:
            with open(save_path, 'w') as f:
                save_dict = {
                    'all_generated_texts': all_generated_texts,
                    'all_labels': all_labels,
                    'score': bleu.score,
                }
                json.dump(save_dict, f)

        return bleu.score
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--model_name_or_path',
        type=str,
        default='microsoft/Phi-4-multimodal-instruct',
        help='Model name or path to load from',
    )
    parser.add_argument(
        "--common_voice_dir",
        type=str,
        default="CommonVoice/EN",
        help="Unzipped Common Voice Audio dataset directory, refer to https://commonvoice.mozilla.org/en/datasets, version 4.0",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="en_sl",
        help="Language pair for translation.",
    )
    parser.add_argument('--use_flash_attention', action='store_true', help='Use Flash Attention')
    parser.add_argument('--output_dir', type=str, default='./output/', help='Output directory')
    parser.add_argument('--batch_size', type=int, default=128, help='Batch size')
    parser.add_argument(
        '--batch_size_per_gpu',
        type=int,
        default=32,
        help='Batch size per GPU (adjust this to fit in GPU memory)',
    )
    parser.add_argument(
        '--num_train_epochs', type=int, default=3, help='Number of training epochs'
    )
    parser.add_argument('--learning_rate', type=float, default=4.0e-5, help='Learning rate')
    parser.add_argument('--wd', type=float, default=0.01, help='Weight decay')
    parser.add_argument('--no-tqdm', dest='tqdm', action='store_false', help='Disable tqdm')
    args = parser.parse_args()

    accelerator = Accelerator()

    with accelerator.local_main_process_first():
        processor = AutoProcessor.from_pretrained(
            args.model_name_or_path,
            trust_remote_code=True,
        )
        model = create_model(
            args.model_name_or_path,
            use_flash_attention=args.use_flash_attention,
        )

    model.set_lora_adapter('speech')


    rank = int(os.environ.get('RANK', 0))
    world_size = int(os.environ.get('WORLD_SIZE', 1))

    eval_dataset = CoVoSTDataset(processor,
                                 data_dir=args.common_voice_dir,
                                 split=f'test[:{_EVAL_SIZE}]',
                                 lang=args.lang,
                                 rank=rank,
                                 world_size=world_size)
    
    train_dataset = CoVoSTDataset(processor,
                                  data_dir=args.common_voice_dir,
                                  split=f'train[:{_TRAIN_SIZE}]',
                                  lang=args.lang)

    num_gpus = accelerator.num_processes
    print(f'training on {num_gpus} GPUs')
    assert (
        args.batch_size % (num_gpus * args.batch_size_per_gpu) == 0
    ), 'Batch size must be divisible by the number of GPUs'
    gradient_accumulation_steps = args.batch_size // (num_gpus * args.batch_size_per_gpu)

    if args.use_flash_attention:
        fp16 = False
        bf16 = True
    else:
        fp16 = True
        bf16 = False

    # hard coded training args
    training_args = TrainingArguments(
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.batch_size_per_gpu,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        gradient_accumulation_steps=gradient_accumulation_steps,
        optim='adamw_torch',
        adam_beta1=0.9,
        adam_beta2=0.95,
        adam_epsilon=1e-7,
        learning_rate=args.learning_rate,
        weight_decay=args.wd,
        max_grad_norm=1.0,
        lr_scheduler_type='linear',
        warmup_steps=50,
        logging_steps=10,
        output_dir=args.output_dir,
        save_strategy='no',
        save_total_limit=10,
        save_only_model=True,
        bf16=bf16,
        fp16=fp16,
        remove_unused_columns=False,
        report_to='none',
        deepspeed=None,
        disable_tqdm=not args.tqdm,
        dataloader_num_workers=4,
        ddp_find_unused_parameters=True,  # for unused SigLIP layers
    )

    # eval before fine-tuning
    out_path = Path(training_args.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    score = evaluate(
        model,
        processor,
        eval_dataset,
        save_path=out_path / 'eval_before.json',
        disable_tqdm=not args.tqdm,
        eval_batch_size=args.batch_size_per_gpu,
    )
    if accelerator.is_main_process:
        print(f'BLEU Score before finetuning: {score}')

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=covost_collate_fn,
        train_dataset=train_dataset,
    )

    trainer.train()
    trainer.save_model()
    if accelerator.is_main_process:
        processor.save_pretrained(training_args.output_dir)
    accelerator.wait_for_everyone()

    # eval after fine-tuning (load saved checkpoint)
    # first try to clear GPU memory
    del model
    del trainer
    __import__('gc').collect()
    torch.cuda.empty_cache()

    # reload the model for inference
    model = AutoModelForCausalLM.from_pretrained(
        training_args.output_dir,
        torch_dtype=torch.bfloat16 if args.use_flash_attention else torch.float32,
        trust_remote_code=True,
        _attn_implementation='flash_attention_2' if args.use_flash_attention else 'sdpa',
    ).to('cuda')

    score = evaluate(
        model,
        processor,
        eval_dataset,
        save_path=out_path / 'eval_after.json',
        disable_tqdm=not args.tqdm,
        eval_batch_size=args.batch_size_per_gpu,
    )
    if accelerator.is_main_process:
        print(f'BLEU Score after finetuning: {score}')


if __name__ == '__main__':
    main()
```

If you want to train the model's ability to translate from English to Chinese, you can execute a CLI command similar to the one below.

```
#(phi4-mm) root@h100vm:~/phi4-mm# python 3.py --common_voice_dir ./ --lang en_zh-CN --output_dir ./english2chinese
```

 Likewise, if you want to train the model's ability to translate from English to Slovenian, you can execute a CLI command similar to the one below.

```
(phi4-mm) root@h100vm:~/phi4-mm# python 3.py --common_voice_dir ./ --lang en_sl
```

During the training process, I have tried and validated both approaches, and they can achieve the expected results. 

Part of training process log:

```
{'loss': 0.146, 'grad_norm': 0.9118049740791321, 'learning_rate': 6.607142857142858e-06, 'epoch': 2.53}                                               
{'loss': 0.1389, 'grad_norm': 0.837959885597229, 'learning_rate': 6.25e-06, 'epoch': 2.56}                                                            
{'loss': 0.1363, 'grad_norm': 1.0479446649551392, 'learning_rate': 5.892857142857144e-06, 'epoch': 2.58}                                              
{'loss': 0.1374, 'grad_norm': 1.0098387002944946, 'learning_rate': 5.535714285714286e-06, 'epoch': 2.61}                                              
{'loss': 0.1394, 'grad_norm': 1.225515604019165, 'learning_rate': 5.1785714285714296e-06, 'epoch': 2.64}                                              
{'loss': 0.1534, 'grad_norm': 1.0256006717681885, 'learning_rate': 4.821428571428572e-06, 'epoch': 2.66}                                              
{'loss': 0.132, 'grad_norm': 0.9518683552742004, 'learning_rate': 4.464285714285715e-06, 'epoch': 2.69}                                               
{'loss': 0.131, 'grad_norm': 1.0464595556259155, 'learning_rate': 4.107142857142857e-06, 'epoch': 2.71}                                               
{'loss': 0.1331, 'grad_norm': 1.1919609308242798, 'learning_rate': 3.7500000000000005e-06, 'epoch': 2.74}                                             
{'loss': 0.1409, 'grad_norm': 1.0631661415100098, 'learning_rate': 3.3928571428571435e-06, 'epoch': 2.76}                                             
{'loss': 0.1447, 'grad_norm': 1.0956666469573975, 'learning_rate': 3.0357142857142856e-06, 'epoch': 2.79}                                             
{'loss': 0.1467, 'grad_norm': 0.8845125436782837, 'learning_rate': 2.6785714285714285e-06, 'epoch': 2.82}                                             
{'loss': 0.1333, 'grad_norm': 1.3615254163742065, 'learning_rate': 2.321428571428572e-06, 'epoch': 2.84}                                              
{'loss': 0.1428, 'grad_norm': 0.9020084142684937, 'learning_rate': 1.9642857142857144e-06, 'epoch': 2.87}                                             
{'loss': 0.1473, 'grad_norm': 1.2402637004852295, 'learning_rate': 1.6071428571428574e-06, 'epoch': 2.89}                                             
{'loss': 0.1513, 'grad_norm': 1.408486008644104, 'learning_rate': 1.25e-06, 'epoch': 2.92}                                                            
{'loss': 0.1483, 'grad_norm': 0.9543040990829468, 'learning_rate': 8.928571428571429e-07, 'epoch': 2.94}                                              
{'loss': 0.14, 'grad_norm': 1.1580735445022583, 'learning_rate': 5.357142857142857e-07, 'epoch': 2.97}                                                
{'loss': 0.1429, 'grad_norm': 0.8998173475265503, 'learning_rate': 1.7857142857142858e-07, 'epoch': 2.99}                                             
{'train_runtime': 4835.1682, 'train_samples_per_second': 31.023, 'train_steps_per_second': 0.242, 'train_loss': 0.44810804087891537, 'epoch': 2.99}   
100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████| 1170/1170 [1:20:35<00:00,  4.13s/it]
/root/anaconda3/envs/phi4-mm/lib/python3.12/site-packages/transformers/models/auto/image_processing_auto.py:520: FutureWarning: The image_processor_class argument is deprecated and will be removed in v4.42. Please use `slow_image_processor_class`, or `fast_image_processor_class` instead
                                          warnings.warn(
/root/.cache/huggingface/modules/transformers_modules/english2chinese/speech_conformer_encoder.py:2774: FutureWarning: Please specify CheckpointImpl.NO_REENTRANT as CheckpointImpl.REENTRANT will soon be removed as the default and eventually deprecated.
                                          lambda i: encoder_checkpoint_wrapper(
Loading checkpoint shards: 100%|████████████████████████████████████████████████████████████████████████████████████████| 5/5 [00:01<00:00,  4.09it/s]
running eval:   0%|                                                                                                             | 0/7 [00:00<?, ?it/s]huggingface/tokenizers: The current process just got forked, after parallelism has already been used. Disabling parallelism to avoid deadlocks...
To disable this warning, you can either:
 
running eval: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████| 7/7 [00:22<00:00,  3.16s/it]
BLEU = 5.03 7.3/5.6/5.6/4.2 (BP = 0.908 ratio = 0.912 hyp_len = 218 ref_len = 239)
BLEU Score after finetuning: 5.033743737529671
```

After the training is completed, execute the following script to load the model: 

Fine-tuned adapter:

```
(base) root@h100vm:~/phi4-mm/output# pwd
/root/phi4-mm/output
(base) root@h100vm:~/phi4-mm/output# ls
added_tokens.json        model-00001-of-00004.safetensors  special_tokens_map.json
chat_template.json       model-00002-of-00004.safetensors  speech_conformer_encoder.py
config.json              model-00003-of-00004.safetensors  tokenizer.json
configuration_phi4mm.py  model-00004-of-00004.safetensors  tokenizer_config.json
eval_after.json          model.safetensors.index.json      training_args.bin
eval_before.json         modeling_phi4mm.py                vision_siglip_navit.py
generation_config.json   preprocessor_config.json          vocab.json
merges.txt               processing_phi4mm.py
```

Load SFT adapter and base model:

```
import gradio as gr
import torch
import requests
import io
import os
import soundfile as sf
from PIL import Image
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoProcessor, GenerationConfig


max_new_tokens = 256
orig_model_path = "microsoft/Phi-4-multimodal-instruct"
ft_model_path = "/root/phi4-mm/output"
generation_config = GenerationConfig.from_pretrained(ft_model_path, 'generation_config.json')
processor = AutoProcessor.from_pretrained(orig_model_path, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    ft_model_path,
    trust_remote_code=True,
    torch_dtype='auto',
    _attn_implementation='eager',
).cuda()

user_prompt = '<|user|>'
assistant_prompt = '<|assistant|>'
prompt_suffix = '<|end|>'
```

Run following code to start a UI:

```
import gradio as gr  
import soundfile as sf  
from PIL import Image  
  
# ---------------------------------------------------------------------------- #  
# Please ensure that you have the following variables defined in your code:  
#   model             = the Phi-4 multimodal model (AutoModelForCausalLM)  
#   processor         = the corresponding AutoProcessor instance  
#   generation_config = an instance of GenerationConfig for inference  
#  
# And make sure you have installed:  
#   pip install gradio soundfile  
# ---------------------------------------------------------------------------- #  
  
def clean_response(response, instruction_keywords):  
    """  
    Remove the leading prompt text based on instruction keywords.  
    This function can be customized to strip out any unnecessary  
    prompt-related text so that the final answer is cleaner.  
    """  
    for keyword in instruction_keywords:  
        if response.lower().startswith(keyword.lower()):  
            response = response[len(keyword):].strip()  
    return response  
  
# The following user_prompt, assistant_prompt, and prompt_suffix are just examples.  
user_prompt = "<|user|>"  
assistant_prompt = "<|assistant|>"  
prompt_suffix = "<|end|>"  
  
# Example prompts for audio tasks, kept here for reference:  
asr_prompt = f'{user_prompt}<|audio_1|>Transcribe the audio clip into text.{prompt_suffix}{assistant_prompt}'  
ast_ko_prompt = f'{user_prompt}<|audio_1|>Translate the audio to Chinese.{prompt_suffix}{assistant_prompt}'  
ast_cot_ko_prompt = f'{user_prompt}<|audio_1|>Transcribe the audio to text, and then translate the audio to Chinese. Use <sep> as a separator between the original transcript and the translation.{prompt_suffix}{assistant_prompt}'  
ast_en_prompt = f'{user_prompt}<|audio_1|>Translate the audio to English.{prompt_suffix}{assistant_prompt}'  
ast_cot_en_prompt = f'{user_prompt}<|audio_1|>Transcribe the audio to text, and then translate the audio to English. Use <sep> as a separator between the original transcript and the translation.{prompt_suffix}{assistant_prompt}'  
  
  
def process_input(file, input_type, question):  
    """  
    This function processes general inputs for Text or Audio type.  
    The 'Image' branch is excluded here and handled separately in 'process_pmc_image'.  
    """  
    user_prompt = "<|user|>"  
    assistant_prompt = "<|assistant|>"  
    prompt_suffix = "<|end|>"  
  
    if input_type == "Audio":  
        # Build an audio prompt  
        prompt = f'{user_prompt}<|audio_1|>{question}{prompt_suffix}{assistant_prompt}'  
        audio, samplerate = sf.read(file)  
        inputs = processor(text=prompt, audios=[(audio, samplerate)], return_tensors='pt').to(model.device)  
  
    elif input_type == "Text":  
        # Build a text prompt  
        prompt = f'{user_prompt}{question} "{file}"{prompt_suffix}{assistant_prompt}'  
        inputs = processor(text=prompt, return_tensors='pt').to(model.device)  
  
    else:  
        return "Invalid input type or not supported in this function."  
  
    generate_ids = model.generate(  
        **inputs,  
        max_new_tokens=1000,  
        generation_config=generation_config  
    )  
    response = processor.batch_decode(generate_ids, skip_special_tokens=True)[0]  
    return clean_response(response, [question])  
  
  
def process_text_translate(text, target_language):  
    """  
    Example function for translating text to a given language.   
    It uses 'process_input' under the "Text" input_type.  
    """  
    prompt = f'Transcribe the audio to text, and then Translate the following text to {target_language}: "{text}"'  
    return process_input(text, "Text", prompt)  
  
  
def process_text_grammar(text):  
    """  
    Example function for grammar checking.   
    It uses 'process_input' under the "Text" input_type.  
    """  
    prompt = f'Check the grammar and provide corrections if needed for the following text: "{text}"'  
    return process_input(text, "Text", prompt)  
  
  
def process_pmc_image(  
    image_path,  
    question,  
    choiceA,  
    choiceB,  
    choiceC,  
    choiceD,  
    instruction  
):  
    """  
    This function handles an image query in a way similar to the PMC-VQA multi-choice style.  
    The user can provide a question, four choices, and a specific instruction.  
    The prompt is constructed to mirror the style used in training.  
    """  
    user_prompt = "<|user|>"  
    assistant_prompt = "<|assistant|>"  
    prompt_suffix = "<|end|>"  
  
    prompt = (  
        f"{user_prompt}<|image_1|>\n"  
        f"{question}\n"  
        f"{choiceA}\n"  
        f"{choiceB}\n"  
        f"{choiceC}\n"  
        f"{choiceD}\n"  
        f"{instruction}"  
        f"{prompt_suffix}"  
        f"{assistant_prompt}"  
    )  
  
    image = Image.open(image_path)  
    inputs = processor(text=prompt, images=image, return_tensors='pt').to(model.device)  
  
    generate_ids = model.generate(  
        **inputs,  
        max_new_tokens=64,  
        generation_config=generation_config  
    )  
    response = processor.batch_decode(generate_ids, skip_special_tokens=True)[0]  
    return clean_response(response, [question])  
  
  
def gradio_interface():  
    """  
    Define a simple Gradio interface with three tabs:  
    1) Text-Based Learning  
    2) Image-Based Learning (multi-choice style)  
    3) Audio-Based Learning  
    """  
    with gr.Blocks() as demo:  
        gr.Markdown("# Phi-4 Powered - Multimodal Language Tutor")  
  
        # -------------------------  
        # 1) Text-Based Learning  
        # -------------------------  
        with gr.Tab("Text-Based Learning"):  
            text_input = gr.Textbox(label="Enter Text")  
            language_input = gr.Textbox(label="Target Language", value="Korean")  
            text_output = gr.Textbox(label="Response")  
            text_translate_btn = gr.Button("Translate")  
            text_grammar_btn = gr.Button("Check Grammar")  
            text_clear_btn = gr.Button("Clear")  
  
            text_translate_btn.click(  
                process_text_translate,  
                inputs=[text_input, language_input],  
                outputs=text_output  
            )  
            text_grammar_btn.click(  
                process_text_grammar,  
                inputs=[text_input],  
                outputs=text_output  
            )  
            text_clear_btn.click(  
                fn=lambda: ("", "", ""),  
                outputs=[text_input, language_input, text_output]  
            )  
  
        # -------------------------  
        # 2) Image-Based Learning  
        # -------------------------  
        with gr.Tab("Image-Based Learning"):  
            gr.Markdown("Test multi-choice questions similar to PMC-VQA")  
  
            image_input = gr.Image(type="filepath", label="Upload Image")  
            question_input = gr.Textbox(  
                label="Question",  
                value="What color is used to label the Golgi complexes in the image?"  
            )  
            choiceA_input = gr.Textbox(label="Choice A", value="A: Green")  
            choiceB_input = gr.Textbox(label="Choice B", value="B: Red")  
            choiceC_input = gr.Textbox(label="Choice C", value="C: Light blue")  
            choiceD_input = gr.Textbox(label="Choice D", value="D: Yellow")  
            instruction_input = gr.Textbox(  
                label="Instruction",  
                value="Answer with the option's letter from the given choices directly."  
            )  
            image_output = gr.Textbox(label="Response (Model's Predicted Answer)")  
  
            image_submit_btn = gr.Button("Ask")  
            image_clear_btn = gr.Button("Clear")  
  
            image_submit_btn.click(  
                fn=process_pmc_image,  
                inputs=[  
                    image_input,  
                    question_input,  
                    choiceA_input,  
                    choiceB_input,  
                    choiceC_input,  
                    choiceD_input,  
                    instruction_input  
                ],  
                outputs=image_output  
            )  
            image_clear_btn.click(  
                fn=lambda: (  
                    None,  
                    "What color is used to label the Golgi complexes in the image?",  
                    "A: Green",  
                    "B: Red",  
                    "C: Light blue",  
                    "D: Yellow",  
                    "Answer with the option's letter from the given choices directly.",  
                    ""  
                ),  
                outputs=[  
                    image_input,  
                    question_input,  
                    choiceA_input,  
                    choiceB_input,  
                    choiceC_input,  
                    choiceD_input,  
                    instruction_input,  
                    image_output  
                ]  
            )  
  
        # -------------------------  
        # 3) Audio-Based Learning  
        # -------------------------  
        with gr.Tab("Audio-Based Learning"):  
            audio_input = gr.Audio(type="filepath", label="Upload Audio")  
            language_input_audio = gr.Textbox(label="Target Language for Translation", value="English")  
            transcript_output = gr.Textbox(label="Transcribed Text")  
            translated_output = gr.Textbox(label="Translated Text")  
            audio_clear_btn = gr.Button("Clear")  
            audio_transcribe_btn = gr.Button("Transcribe & Translate")  
  
            # First click: transcribe the audio  
            audio_transcribe_btn.click(  
                fn=process_input,  
                inputs=[  
                    audio_input,  
                    gr.Textbox(value="Audio", visible=False),  
                    gr.Textbox(value="Transcribe this audio", visible=False)  
                ],  
                outputs=transcript_output  
            )  
            # Second click: reuse the same button to also perform translation  
            audio_transcribe_btn.click(  
                fn=process_input,  
                inputs=[  
                    audio_input,  
                    gr.Textbox(value="Audio", visible=False),  
                    language_input_audio  
                ],  
                outputs=translated_output  
            )  
            audio_clear_btn.click(  
                fn=lambda: (None, "", "", ""),  
                outputs=[audio_input, language_input_audio, transcript_output, translated_output]  
            )  
  
        demo.launch(debug=True, share=True)  
  
if __name__ == "__main__":  
    gradio_interface()  
```



### SFT Vision encoder on Azure NC H100 VM

The training corpus for the vision encoder follows the style below：

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/SFT-Phi-4-mm/images/2.png)

Code is as following:

```
"""
finetune Phi-4-multimodal-instruct on an image task

scipy==1.15.1
peft==0.13.2
backoff==2.2.1
transformers==4.47.0
accelerate==1.3.0
"""

import argparse
import json
import os
import tempfile
import zipfile
from pathlib import Path

import torch
from accelerate import Accelerator
from accelerate.utils import gather_object
from datasets import load_dataset
from huggingface_hub import hf_hub_download
from PIL import Image
from torch.utils.data import Dataset
from tqdm import tqdm
from transformers import (
    AutoModelForCausalLM,
    AutoProcessor,
    BatchFeature,
    Trainer,
    TrainingArguments,
)

DEFAULT_INSTSRUCTION = "Answer with the option's letter from the given choices directly."
_IGNORE_INDEX = -100
_TRAIN_SIZE = 8000
_EVAL_SIZE = 500
_MAX_TRAINING_LENGTH = 8192


class PmcVqaTrainDataset(Dataset):
    def __init__(self, processor, data_size, instruction=DEFAULT_INSTSRUCTION):
        # Download the file
        file_path = hf_hub_download(
            repo_id='xmcmic/PMC-VQA',  # repository name
            filename='images_2.zip',  # file to download
            repo_type='dataset',  # specify it's a dataset repo
        )

        # file_path will be the local path where the file was downloaded
        print(f'File downloaded to: {file_path}')

        # unzip to temp folder
        self.image_folder = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(self.image_folder)

        data_files = {
            'train': 'https://huggingface.co/datasets/xmcmic/PMC-VQA/resolve/main/train_2.csv',
        }
        split = 'train' if data_size is None else f'train[:{data_size}]'
        self.annotations = load_dataset('xmcmic/PMC-VQA', data_files=data_files, split=split)
        self.processor = processor
        self.instruction = instruction

    def __len__(self):
        return len(self.annotations)

    def __getitem__(self, idx):
        """
        {'index': 35,
         'Figure_path': 'PMC8253797_Fig4_11.jpg',
         'Caption': 'A slightly altered cell . (c-c‴) A highly altered cell as seen from 4 different angles . Note mitochondria/mitochondrial networks (green), Golgi complexes (red), cell nuclei (light blue) and the cell outline (yellow).',
         'Question': ' What color is used to label the Golgi complexes in the image?',
         'Choice A': ' A: Green ',
         'Choice B': ' B: Red ',
         'Choice C': ' C: Light blue ',
         'Choice D': ' D: Yellow',
         'Answer': 'B',
         'split': 'train'}
        """
        annotation = self.annotations[idx]
        image = Image.open(self.image_folder / 'figures' / annotation['Figure_path'])
        question = annotation['Question']
        choices = [annotation[f'Choice {chr(ord("A") + i)}'] for i in range(4)]
        user_message = {
            'role': 'user',
            'content': '<|image_1|>' + '\n'.join([question] + choices + [self.instruction]),
        }
        prompt = self.processor.tokenizer.apply_chat_template(
            [user_message], tokenize=False, add_generation_prompt=True
        )
        answer = f'{annotation["Answer"]}<|end|><|endoftext|>'
        inputs = self.processor(prompt, images=[image], return_tensors='pt')

        answer_ids = self.processor.tokenizer(answer, return_tensors='pt').input_ids

        input_ids = torch.cat([inputs.input_ids, answer_ids], dim=1)
        labels = torch.full_like(input_ids, _IGNORE_INDEX)
        labels[:, -answer_ids.shape[1] :] = answer_ids

        if input_ids.size(1) > _MAX_TRAINING_LENGTH:
            input_ids = input_ids[:, :_MAX_TRAINING_LENGTH]
            labels = labels[:, :_MAX_TRAINING_LENGTH]
            if torch.all(labels == _IGNORE_INDEX).item():
                # workaround to make sure loss compute won't fail
                labels[:, -1] = self.processor.tokenizer.eos_token_id

        return {
            'input_ids': input_ids,
            'labels': labels,
            'input_image_embeds': inputs.input_image_embeds,
            'image_attention_mask': inputs.image_attention_mask,
            'image_sizes': inputs.image_sizes,
        }

    def __del__(self):
        __import__('shutil').rmtree(self.image_folder)


class PmcVqaEvalDataset(Dataset):
    def __init__(
        self, processor, data_size, instruction=DEFAULT_INSTSRUCTION, rank=0, world_size=1
    ):
        # Download the file
        file_path = hf_hub_download(
            repo_id='xmcmic/PMC-VQA',  # repository name
            filename='images_2.zip',  # file to download
            repo_type='dataset',  # specify it's a dataset repo
        )

        # file_path will be the local path where the file was downloaded
        print(f'File downloaded to: {file_path}')

        # unzip to temp folder
        self.image_folder = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(self.image_folder)

        data_files = {
            'test': 'https://huggingface.co/datasets/xmcmic/PMC-VQA/resolve/main/test_2.csv',
        }
        split = 'test' if data_size is None else f'test[:{data_size}]'
        self.annotations = load_dataset(
            'xmcmic/PMC-VQA', data_files=data_files, split=split
        ).shard(num_shards=world_size, index=rank)
        self.processor = processor
        self.instruction = instruction

    def __len__(self):
        return len(self.annotations)

    def __getitem__(self, idx):
        """
        {'index': 62,
         'Figure_path': 'PMC8253867_Fig2_41.jpg',
         'Caption': 'CT pulmonary angiogram reveals encasement and displacement of the left anterior descending coronary artery ( blue arrows ).',
         'Question': ' What is the name of the artery encased and displaced in the image? ',
         'Choice A': ' A: Right Coronary Artery ',
         'Choice B': ' B: Left Anterior Descending Coronary Artery ',
         'Choice C': ' C: Circumflex Coronary Artery ',
         'Choice D': ' D: Superior Mesenteric Artery ',
         'Answer': 'B',
         'split': 'test'}
        """
        annotation = self.annotations[idx]
        image = Image.open(self.image_folder / 'figures' / annotation['Figure_path'])
        question = annotation['Question']
        choices = [annotation[f'Choice {chr(ord("A") + i)}'] for i in range(4)]
        user_message = {
            'role': 'user',
            'content': '<|image_1|>' + '\n'.join([question] + choices + [self.instruction]),
        }
        prompt = self.processor.tokenizer.apply_chat_template(
            [user_message], tokenize=False, add_generation_prompt=True
        )
        answer = annotation['Answer']
        inputs = self.processor(prompt, images=[image], return_tensors='pt')

        unique_id = f'{annotation["index"]:010d}'
        return {
            'id': unique_id,
            'input_ids': inputs.input_ids,
            'input_image_embeds': inputs.input_image_embeds,
            'image_attention_mask': inputs.image_attention_mask,
            'image_sizes': inputs.image_sizes,
            'answer': answer,
        }

    def __del__(self):
        __import__('shutil').rmtree(self.image_folder)


def pad_sequence(sequences, padding_side='right', padding_value=0):
    """
    Pad a list of sequences to the same length.
    sequences: list of tensors in [seq_len, *] shape
    """
    assert padding_side in ['right', 'left']
    max_size = sequences[0].size()
    trailing_dims = max_size[1:]
    max_len = max(len(seq) for seq in sequences)
    batch_size = len(sequences)
    output = sequences[0].new_full((batch_size, max_len) + trailing_dims, padding_value)
    for i, seq in enumerate(sequences):
        length = seq.size(0)
        if padding_side == 'right':
            output.data[i, :length] = seq
        else:
            output.data[i, -length:] = seq
    return output


def cat_with_pad(tensors, dim, padding_value=0):
    """
    cat along dim, while pad to max for all other dims
    """
    ndim = tensors[0].dim()
    assert all(
        t.dim() == ndim for t in tensors[1:]
    ), 'All tensors must have the same number of dimensions'

    out_size = [max(t.shape[i] for t in tensors) for i in range(ndim)]
    out_size[dim] = sum(t.shape[dim] for t in tensors)
    output = tensors[0].new_full(out_size, padding_value)

    index = 0
    for t in tensors:
        # Create a slice list where every dimension except dim is full slice
        slices = [slice(0, t.shape[d]) for d in range(ndim)]
        # Update only the concat dimension slice
        slices[dim] = slice(index, index + t.shape[dim])

        output[slices] = t
        index += t.shape[dim]

    return output


def pmc_vqa_collate_fn(batch):
    input_ids_list = []
    labels_list = []
    input_image_embeds_list = []
    image_attention_mask_list = []
    image_sizes_list = []
    for inputs in batch:
        input_ids_list.append(inputs['input_ids'][0])
        labels_list.append(inputs['labels'][0])
        input_image_embeds_list.append(inputs['input_image_embeds'])
        image_attention_mask_list.append(inputs['image_attention_mask'])
        image_sizes_list.append(inputs['image_sizes'])

    input_ids = pad_sequence(input_ids_list, padding_side='right', padding_value=0)
    labels = pad_sequence(labels_list, padding_side='right', padding_value=0)
    attention_mask = (input_ids != 0).long()
    input_image_embeds = cat_with_pad(input_image_embeds_list, dim=0)
    image_attention_mask = cat_with_pad(image_attention_mask_list, dim=0)
    image_sizes = torch.cat(image_sizes_list)

    return BatchFeature(
        {
            'input_ids': input_ids,
            'labels': labels,
            'attention_mask': attention_mask,
            'input_image_embeds': input_image_embeds,
            'image_attention_mask': image_attention_mask,
            'image_sizes': image_sizes,
            'input_mode': 1,  # vision mode
        }
    )


def pmc_vqa_eval_collate_fn(batch):
    input_ids_list = []
    input_image_embeds_list = []
    image_attention_mask_list = []
    image_sizes_list = []
    all_unique_ids = []
    all_answers = []
    for inputs in batch:
        input_ids_list.append(inputs['input_ids'][0])
        input_image_embeds_list.append(inputs['input_image_embeds'])
        image_attention_mask_list.append(inputs['image_attention_mask'])
        image_sizes_list.append(inputs['image_sizes'])
        all_unique_ids.append(inputs['id'])
        all_answers.append(inputs['answer'])

    input_ids = pad_sequence(input_ids_list, padding_side='left', padding_value=0)
    attention_mask = (input_ids != 0).long()
    input_image_embeds = cat_with_pad(input_image_embeds_list, dim=0)
    image_attention_mask = cat_with_pad(image_attention_mask_list, dim=0)
    image_sizes = torch.cat(image_sizes_list)

    return (
        all_unique_ids,
        all_answers,
        BatchFeature(
            {
                'input_ids': input_ids,
                'attention_mask': attention_mask,
                'input_image_embeds': input_image_embeds,
                'image_attention_mask': image_attention_mask,
                'image_sizes': image_sizes,
                'input_mode': 1,  # vision mode
            }
        ),
    )


def create_model(model_name_or_path, use_flash_attention=False):
    model = AutoModelForCausalLM.from_pretrained(
        model_name_or_path,
        torch_dtype=torch.bfloat16 if use_flash_attention else torch.float32,
        _attn_implementation='flash_attention_2' if use_flash_attention else 'sdpa',
        trust_remote_code=True,
    ).to('cuda')
    # remove parameters irrelevant to vision tasks
    del model.model.embed_tokens_extend.audio_embed  # remove audio encoder
    for layer in model.model.layers:
        # remove audio lora
        del layer.mlp.down_proj.lora_A.speech
        del layer.mlp.down_proj.lora_B.speech
        del layer.mlp.gate_up_proj.lora_A.speech
        del layer.mlp.gate_up_proj.lora_B.speech
        del layer.self_attn.o_proj.lora_A.speech
        del layer.self_attn.o_proj.lora_B.speech
        del layer.self_attn.qkv_proj.lora_A.speech
        del layer.self_attn.qkv_proj.lora_B.speech

    # TODO remove unused vision layers?

    return model


@torch.no_grad()
def evaluate(
    model, processor, eval_dataset, save_path=None, disable_tqdm=False, eval_batch_size=1
):
    rank = int(os.environ.get('RANK', 0))
    local_rank = int(os.environ.get('LOCAL_RANK', 0))

    model.eval()
    all_answers = []
    all_generated_texts = []

    eval_dataloader = torch.utils.data.DataLoader(
        eval_dataset,
        batch_size=eval_batch_size,
        collate_fn=pmc_vqa_eval_collate_fn,
        shuffle=False,
        drop_last=False,
        num_workers=4,
        prefetch_factor=2,
        pin_memory=True,
    )
    for ids, answers, inputs in tqdm(
        eval_dataloader, disable=(rank != 0) or disable_tqdm, desc='running eval'
    ):
        all_answers.extend({'id': i, 'answer': a.strip().lower()} for i, a in zip(ids, answers))

        inputs = inputs.to(f'cuda:{local_rank}')
        generated_ids = model.generate(
            **inputs, eos_token_id=processor.tokenizer.eos_token_id, max_new_tokens=64
        )

        input_len = inputs.input_ids.size(1)
        generated_texts = processor.batch_decode(
            generated_ids[:, input_len:],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        all_generated_texts.extend(
            {'id': i, 'generated_text': g.strip().lower()} for i, g in zip(ids, generated_texts)
        )

    # gather outputs from all ranks
    all_answers = gather_object(all_answers)
    all_generated_texts = gather_object(all_generated_texts)

    if rank == 0:
        assert len(all_answers) == len(all_generated_texts)
        acc = sum(
            a['answer'] == g['generated_text'] for a, g in zip(all_answers, all_generated_texts)
        ) / len(all_answers)
        if save_path:
            with open(save_path, 'w') as f:
                save_dict = {
                    'answers_unique': all_answers,
                    'generated_texts_unique': all_generated_texts,
                    'accuracy': acc,
                }
                json.dump(save_dict, f)

        return acc
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--model_name_or_path',
        type=str,
        default='microsoft/Phi-4-multimodal-instruct',
        help='Model name or path to load from',
    )
    parser.add_argument('--use_flash_attention', action='store_true', help='Use Flash Attention')
    parser.add_argument('--output_dir', type=str, default='./output/', help='Output directory')
    parser.add_argument('--batch_size', type=int, default=16, help='Batch size')
    parser.add_argument(
        '--batch_size_per_gpu',
        type=int,
        default=1,
        help='Batch size per GPU (adjust this to fit in GPU memory)',
    )
    parser.add_argument(
        '--dynamic_hd',
        type=int,
        default=36,
        help='Number of maximum image crops',
    )
    parser.add_argument(
        '--num_train_epochs', type=int, default=1, help='Number of training epochs'
    )
    parser.add_argument('--learning_rate', type=float, default=4.0e-5, help='Learning rate')
    parser.add_argument('--wd', type=float, default=0.01, help='Weight decay')
    parser.add_argument('--no_tqdm', dest='tqdm', action='store_false', help='Disable tqdm')
    parser.add_argument('--full_run', action='store_true', help='Run the full training and eval')
    args = parser.parse_args()

    accelerator = Accelerator()

    with accelerator.local_main_process_first():
        processor = AutoProcessor.from_pretrained(
            args.model_name_or_path,
            trust_remote_code=True,
            dynamic_hd=args.dynamic_hd,
        )
        model = create_model(
            args.model_name_or_path,
            use_flash_attention=args.use_flash_attention,
        )
    # tune vision encoder and lora
    model.set_lora_adapter('vision')
    for param in model.model.embed_tokens_extend.image_embed.parameters():
        param.requires_grad = True

    rank = int(os.environ.get('RANK', 0))
    world_size = int(os.environ.get('WORLD_SIZE', 1))

    train_dataset = PmcVqaTrainDataset(processor, data_size=None if args.full_run else _TRAIN_SIZE)
    eval_dataset = PmcVqaEvalDataset(
        processor,
        data_size=None if args.full_run else _EVAL_SIZE,
        rank=rank,
        world_size=world_size,
    )

    num_gpus = accelerator.num_processes
    print(f'training on {num_gpus} GPUs')
    assert (
        args.batch_size % (num_gpus * args.batch_size_per_gpu) == 0
    ), 'Batch size must be divisible by the number of GPUs'
    gradient_accumulation_steps = args.batch_size // (num_gpus * args.batch_size_per_gpu)

    if args.use_flash_attention:
        fp16 = False
        bf16 = True
    else:
        fp16 = True
        bf16 = False

    # hard coded training args
    training_args = TrainingArguments(
        num_train_epochs=args.num_train_epochs,
        per_device_train_batch_size=args.batch_size_per_gpu,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={'use_reentrant': False},
        gradient_accumulation_steps=gradient_accumulation_steps,
        optim='adamw_torch',
        adam_beta1=0.9,
        adam_beta2=0.95,
        adam_epsilon=1e-7,
        learning_rate=args.learning_rate,
        weight_decay=args.wd,
        max_grad_norm=1.0,
        lr_scheduler_type='linear',
        warmup_steps=50,
        logging_steps=10,
        output_dir=args.output_dir,
        save_strategy='no',
        save_total_limit=10,
        save_only_model=True,
        bf16=bf16,
        fp16=fp16,
        remove_unused_columns=False,
        report_to='none',
        deepspeed=None,
        disable_tqdm=not args.tqdm,
        dataloader_num_workers=4,
        ddp_find_unused_parameters=True,  # for unused SigLIP layers
    )

    # eval before fine-tuning
    out_path = Path(training_args.output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    acc = evaluate(
        model,
        processor,
        eval_dataset,
        save_path=out_path / 'eval_before.json',
        disable_tqdm=not args.tqdm,
        eval_batch_size=args.batch_size_per_gpu,
    )
    if accelerator.is_main_process:
        print(f'Accuracy before finetuning: {acc}')

    trainer = Trainer(
        model=model,
        args=training_args,
        data_collator=pmc_vqa_collate_fn,
        train_dataset=train_dataset,
    )
    trainer.train()
    trainer.save_model()
    accelerator.wait_for_everyone()

    # eval after fine-tuning (load saved checkpoint)
    # first try to clear GPU memory
    del model
    del trainer
    __import__('gc').collect()
    torch.cuda.empty_cache()

    # reload the model for inference
    model = AutoModelForCausalLM.from_pretrained(
        training_args.output_dir,
        torch_dtype=torch.bfloat16 if args.use_flash_attention else torch.float32,
        trust_remote_code=True,
        _attn_implementation='flash_attention_2' if args.use_flash_attention else 'sdpa',
    ).to('cuda')

    acc = evaluate(
        model,
        processor,
        eval_dataset,
        save_path=out_path / 'eval_after.json',
        disable_tqdm=not args.tqdm,
        eval_batch_size=args.batch_size_per_gpu,
    )
    if accelerator.is_main_process:
        print(f'Accuracy after finetuning: {acc}')


if __name__ == '__main__':
    main()
```

Run code:

```
(phi4-mm) root@h100vm:~/phi4-mm# python 10.py --num_train_epochs 3 --output_dir "./sft-vqa"
```

Part of training process log:

```
                                                                              {'loss': 0.144, 'grad_norm': 3.5261449813842773, 'learning_rate': 1.9862068965517244e-05, 'epoch': 1.56}                                                                                
{'loss': 0.0669, 'grad_norm': 3.100583791732788, 'learning_rate': 1.9586206896551725e-05, 'epoch': 1.58}                                                                                
{'loss': 0.1223, 'grad_norm': 3.2514164447784424, 'learning_rate': 1.931034482758621e-05, 'epoch': 1.6}                                                                                 
{'loss': 0.1376, 'grad_norm': 6.891955375671387, 'learning_rate': 1.903448275862069e-05, 'epoch': 1.62}                                                                                 
{'loss': 0.1201, 'grad_norm': 2.4741413593292236, 'learning_rate': 1.8758620689655173e-05, 'epoch': 1.64}                                                                               
{'loss': 0.0936, 'grad_norm': 3.800098180770874, 'learning_rate': 1.8482758620689657e-05, 'epoch': 1.66}                                                                                
{'loss': 0.1411, 'grad_norm': 5.591039657592773, 'learning_rate': 1.820689655172414e-05, 'epoch': 1.68}                                                                                 
{'loss': 0.1319, 'grad_norm': 1.7234206199645996, 'learning_rate': 1.7931034482758623e-05, 'epoch': 1.7}          
```

To verify the image inference capability of the code, you can achieve it by using the same inference code from the Audio training above. 

![images](https://github.com/xinyuwei-david/david-share/blob/master/Multimodal-Models/SFT-Phi-4-mm/images/4.png)