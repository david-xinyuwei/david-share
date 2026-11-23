"""Send one chat request to a deployment. Standard library only; a starting point for your own client.

  python examples/chat.py <chat URL printed by up.py> <deployment name> "your question"

`model` is a deployment name: the target deployment answers as the base model, an adapter deployment answers with its
LoRA adapter. The request carries a Microsoft Entra token for https://ai.azure.com (here taken from the Azure CLI;
an application would use its managed identity). No key and no api-version are needed.
"""
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request


def entra_token() -> str:
    az = shutil.which("az") or shutil.which("az.cmd")
    if az is None:
        sys.exit("Azure CLI not found: install it and run `az login`.")
    r = subprocess.run([az, "account", "get-access-token", "--resource", "https://ai.azure.com", "--query", "accessToken", "-o", "tsv"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Could not get a token. Run `az login` first.\n" + r.stderr.strip()[-300:])
    return r.stdout.strip()


def main() -> int:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    url, model, question = sys.argv[1:]
    # "reasoning_effort": "none" asks for the answer directly. Remove it to let the model reason first; reasoning tokens
    # count against max_tokens, so raise max_tokens when you do.
    body = {"model": model, "messages": [{"role": "user", "content": question}], "max_tokens": 800, "temperature": 0,
            "reasoning_effort": "none"}
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Authorization": "Bearer " + entra_token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            reply = json.loads(response.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}", file=sys.stderr)
        return 1
    message = reply["choices"][0]["message"]
    print(message.get("content") or "")
    print(f"\n[served model {reply.get('model')}; {reply['usage']['completion_tokens']} completion tokens]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
