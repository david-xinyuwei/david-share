"""
GSM8K evaluation *without* vLLM.
依赖：transformers, torch, tqdm, datasets
用法：
    python gsm8k-eval-tf.py --model_dir gemma-grpo-only
"""

import argparse, re, json, torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForCausalLM
from config import init, close, get_gsm8k_questions, Config


def find_number(txt: str):
    m = re.findall(r"-?[\d,]*\.?\d+", txt)
    return m[-1] if m else ""


def extract_last_xml_answer(txt):
    m = re.findall(r"<answer>(.*?)</answer>", txt, re.S)
    ans = m[-1] if m else ""
    return re.sub(r"[%$,]", "", ans).strip()


@torch.inference_mode()
def sampler(model, tok, prompt, max_prompt_len, max_gen_len):
    inputs = tok(prompt, return_tensors="pt", truncation=True,
                 max_length=max_prompt_len).to(model.device)
    out_ids = model.generate(
        **inputs,
        max_new_tokens=max_gen_len,
        temperature=0.0,
        top_p=1.0
    )[0]
    text = tok.decode(out_ids[len(inputs["input_ids"][0]):],
                      skip_special_tokens=True)
    return text


if __name__ == "__main__":
    init()
    cfg = Config()

    parser = argparse.ArgumentParser()
    parser.add_argument("--model_dir", required=True)
    args = parser.parse_args()

    print(f"Evaluating {args.model_dir}  (pure HF generate)")
    tok = AutoTokenizer.from_pretrained(args.model_dir)
    tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        args.model_dir,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        device_map="auto",
    )
    model.eval()

    test_ds = get_gsm8k_questions("test")

    records = {}
    in_tok, out_tok = [], []
    ok_format = plaus_ok = exact_ok = 0

    for i, sample in tqdm(enumerate(test_ds), total=len(test_ds)):
        prompt = sample["prompt"][0]["content"]
        gt     = sample["answer"]

        resp = sampler(model, tok, prompt,
                       cfg.max_prompt_length,
                       cfg.max_completion_length)

        in_tok.append(len(tok(prompt)["input_ids"]))
        out_tok.append(len(tok(resp)["input_ids"]))

        num_plain = re.sub(r"[%,\s$]", "", find_number(resp))
        num_xml   = extract_last_xml_answer(resp)

        fmt_good = bool(re.match(
            r"^<reasoning>[\s\S]*?</reasoning>\s*<answer>[\s\S]*?</answer>$",
            resp.strip()))
        if fmt_good: ok_format += 1
        if num_plain == gt or num_xml == gt: plaus_ok += 1
        if num_xml == gt: exact_ok += 1

        records[i] = dict(
            prompt=prompt, answer=gt, response=resp,
            numeric=num_plain, xml_answer=num_xml, fmt=fmt_good
        )

    # 保存 JSON
    with open("records_tf.json", "w") as f:
        json.dump(records, f, indent=2)

    n = len(test_ds)
    print("-" * 40)
    print(f"Input tokens  avg={sum(in_tok)/n:.1f}  max={max(in_tok)}")
    print(f"Output tokens avg={sum(out_tok)/n:.1f}  max={max(out_tok)}")
    print(f"Correct format     : {ok_format}/{n} ({ok_format/n*100:.1f}%)")
    print(f"Plausibly correct  : {plaus_ok}/{n} ({plaus_ok/n*100:.1f}%)")
    print(f"Exact correct      : {exact_ok}/{n} ({exact_ok/n*100:.1f}%)")
    print("=" * 40)

    close()
