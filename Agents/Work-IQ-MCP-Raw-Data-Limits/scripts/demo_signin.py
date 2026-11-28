"""Sign the Interactive Demo in for Live mode by clicking the account tile Windows offers.

No password is typed. A password, MFA or consent page stops the script with NEEDS_USER:
finish that page yourself in the automation Edge window, then run the script again.
"""
import argparse
import json
import sys
import time
import urllib.parse

import edge_cdp as ec

DEMO = "interactivedemo.microsoft.com"
CLICK_SIGNIN = r"""(() => {
  const b = [...document.querySelectorAll('button')].find(x => /Sign in to go live/i.test(x.innerText));
  if (!b) return 'NOT_FOUND';
  b.click();
  return 'CLICKED';
})()"""
DEMO_STATE = r"""(() => {
  const t = document.body ? document.body.innerText.replace(/\s+/g, ' ') : '';
  const acct = [...document.querySelectorAll('button')].map(b => b.getAttribute('aria-label') || '').find(x => /account menu/i.test(x)) || '';
  return {demo: /Demo account:/.test(t), account: acct.slice(0, 160), head: t.slice(0, 260)};
})()"""
LOGIN_STATE = r"""(() => {
  const vis = e => !!(e && (e.offsetWidth || e.offsetHeight || e.getClientRects().length));
  const t = document.body ? document.body.innerText.replace(/\s+/g, ' ') : '';
  const tiles = [...document.querySelectorAll('[data-test-id]')].map(e => e.getAttribute('data-test-id')).filter(x => x && x.includes('@'));
  return {text: t.slice(0, 300), tiles,
          hasPassword: [...document.querySelectorAll('input[type=password]')].some(vis),
          kmsi: !!document.querySelector('#idBtn_Back') && /保持登录|Stay signed in/i.test(t),
          consent: /Permissions requested|请求的权限|需要权限|Need admin approval|需要管理员/i.test(t)};
})()"""
CLICK_TILE = r"""(acct => {
  const t = [...document.querySelectorAll('[data-test-id]')].find(e => (e.getAttribute('data-test-id') || '').toLowerCase() === acct.toLowerCase());
  if (!t) return 'NOT_FOUND';
  t.click();
  return 'CLICKED';
})(%s)"""


def live(state):
    # A page that is still loading has no text at all, so "no Demo banner" alone proves nothing.
    return bool(state and state.get("account")) and not state.get("demo") and "Demo account" not in state["account"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--account", required=True, help="UPN of the account tile to click")
    ap.add_argument("--port", type=int, default=ec.DEFAULT_PORT)
    ap.add_argument("--wait", type=int, default=150, help="seconds to wait for the sign-in")
    a = ap.parse_args()

    demo = ec.find(a.port, DEMO)
    on_login = any((urllib.parse.urlparse(t.get("url", "")).hostname or "") in ec.LOGIN_HOSTS for t in ec.targets(a.port))
    if not demo and not on_login:
        print("NO_DEMO_PAGE: run edge_cdp.py start --url https://interactivedemo.microsoft.com/work-iq/mcp first")
        return 3
    if demo:
        state = ec.evaluate(a.port, demo["id"], DEMO_STATE)
        if live(state):
            print("SIGNIN=ALREADY_LIVE", state["account"])
            return 0
        print("click 'Sign in to go live':", ec.evaluate(a.port, demo["id"], CLICK_SIGNIN))

    end, picked, last, quiet_since = time.time() + a.wait, set(), None, time.time()
    while time.time() < end:
        time.sleep(2)
        for t in ec.targets(a.port):
            host = urllib.parse.urlparse(t.get("url", "")).hostname or ""
            if host not in ec.LOGIN_HOSTS:
                continue
            try:
                p = ec.evaluate(a.port, t["id"], LOGIN_STATE) or {}
            except Exception:
                continue
            key = (t["url"][:90], p.get("text", "")[:80])
            if key != last:
                last = key
                print("sign-in page:", key[0], "|", key[1])
            if p.get("consent"):
                print("NEEDS_USER (consent): a permission page is open in the automation Edge window; decide there yourself.")
                print("  page:", p.get("text", ""))
                return 4
            if p.get("kmsi"):
                ec.evaluate(a.port, t["id"], "document.querySelector('#idBtn_Back').click()")
                print("'stay signed in?' answered No")
                quiet_since = time.time()
                continue
            tiles = [x.lower() for x in p.get("tiles", [])]
            if a.account.lower() in tiles and t["url"] not in picked:
                picked.add(t["url"])
                print("account tile:", ec.evaluate(a.port, t["id"], CLICK_TILE % json.dumps(a.account)), a.account, "(no password typed)")
                quiet_since = time.time()
                continue
            # A sign-in page without text is single sign-on at work (it took about 25 s on the test day): keep waiting.
            waited = time.time() - quiet_since
            if (p.get("hasPassword") and waited > 10) or (p.get("text") and waited > 60):
                need = "password" if p.get("hasPassword") else "action"
                print(f"NEEDS_USER ({need}): finish the sign-in in the automation Edge window, then run this script again.")
                print("  page:", p.get("text", ""))
                return 4
        demo = ec.find(a.port, DEMO)
        if demo:
            try:
                state = ec.evaluate(a.port, demo["id"], DEMO_STATE)
            except Exception:
                continue
            if live(state):
                print("SIGNIN=OK", state["account"])
                print("  page:", state["head"])
                return 0
    print("SIGNIN=TIMEOUT: still in Demo mode after", a.wait, "s")
    return 5


if __name__ == "__main__":
    sys.exit(main())
