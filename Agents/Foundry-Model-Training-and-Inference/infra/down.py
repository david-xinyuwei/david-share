"""Remove what up.py created.

  python infra/down.py --resource-group <name>
      Deletes the adapter deployments, then the target deployment. The hourly GPU charge stops.
      The Foundry account, the project, the uploaded files and the trained adapters stay (no hourly charge),
      so `up.py --deploy` can serve the same adapters again later.

  python infra/down.py --resource-group <name> --all
      Then deletes the project and the Foundry account and purges the soft-deleted account. The resource group is
      deleted too when up.py created it and nothing else is in it.

Every deletion is read back until the resource is gone. The account accepts one write at a time, so deletions run one
after another. Receipt: ~/.foundry-lora/<resource group>/down-receipt.json   Exit code: 0 = nothing is left, 1 = something is.
"""
from __future__ import annotations

import argparse
import json
import time

import foundry as f


def parse_args():
    p = argparse.ArgumentParser(description="Delete the adapter and target deployments; with --all also the account and resource group.")
    p.add_argument("--resource-group", required=True)
    p.add_argument("--subscription")
    p.add_argument("--target", default=f.DEFAULT_TARGET)
    p.add_argument("--all", action="store_true", help="also delete the Foundry account, its project and, when it is ours and empty, the resource group")
    return p.parse_args()


def delete_and_wait(url: str, label: str, minutes: int = 40) -> bool:
    """DELETE one ARM resource and poll until GET returns 404. Retries while the account is busy (HTTP 409)."""
    started, accepted = time.time(), False
    while time.time() - started < minutes * 60:
        code, _, body = f.http("GET", url)
        if code == 404:
            f.log(f"{label}: gone ({time.time() - started:.0f} s)")
            return True
        if f.state_of(body) != "Deleting":
            code, _, reply = f.http("DELETE", url)
            if code in (200, 202, 204) and not accepted:
                accepted = True
                f.log(f"{label}: deletion accepted (HTTP {code})")
            elif code not in (200, 202, 204, 404, 409):
                f.log(f"{label}: DELETE answered HTTP {code} {f.brief(reply, 200)}")
        time.sleep(20)
    return False


def names(url: str) -> list[dict]:
    code, _, body = f.http("GET", url)
    return body.get("value", []) if code == 200 and isinstance(body, dict) else []


def main() -> int:
    args = parse_args()
    sub = f.use_subscription(args.subscription)["id"]
    rg = args.resource_group
    receipt = f.Receipt(f.state_dir(rg) / "down-receipt.json", resourceGroup=rg, all=args.all)
    sol = f.find_solution(sub, rg, args.target)
    if sol is None:
        receipt.add("Find the deployment", "PASS", f"no Foundry account created by this repository in resource group {rg}: nothing to remove")
        print(f"\nRESULT: {receipt.close()}   receipt: {receipt.path}")
        return 0

    t0 = time.time()
    adapters = [a["name"] for a in names(sol.adapter_url())
                if args.all or a["properties"].get("targetDeploymentName") == sol.target]
    targets = [t["name"] for t in names(sol.target_url(collection=True)) if args.all or t["name"] == sol.target]
    f.log(f"to delete: adapter deployments {adapters or 'none'}, managed compute deployments {targets or 'none'}")
    left = [n for n in adapters if not delete_and_wait(sol.adapter_url(n), f"adapter deployment {n}")]
    left += [n for n in targets if not delete_and_wait(sol.target_url(n), f"managed compute deployment {n}")]
    if targets:
        state = f.load_state(rg)
        state["lastTeardown"] = f.now()
        f.save_state(rg, state)
    remaining = [t["name"] for t in names(sol.target_url(collection=True)) if args.all or t["name"] == sol.target]
    receipt.add("GPU deployments removed", "PASS" if not left and not remaining else "FAIL",
                f"deleted {len(adapters)} adapter deployment(s) and {len(targets)} managed compute deployment(s); "
                f"still present: {left + remaining or 'none'}", time.time() - t0)

    if args.all and not left and not remaining:
        t0 = time.time()
        for proj in names(f"{sol.account_id}/projects?api-version={f.API_ACCOUNT}"):
            delete_and_wait(f"{proj['id']}?api-version={f.API_ACCOUNT}", f"project {proj['name']}", 20)
        gone = delete_and_wait(f"{sol.account_id}?api-version={f.API_ACCOUNT}", f"Foundry account {sol.account}", 30)
        purge = (f"/subscriptions/{sub}/providers/Microsoft.CognitiveServices/locations/{sol.location}/resourceGroups/{rg}"
                 f"/deletedAccounts/{sol.account}?api-version={f.API_ACCOUNT}")
        purged = gone and delete_and_wait(purge, f"soft-deleted account {sol.account} (purge)", 20)
        receipt.add("Foundry account removed and purged", "PASS" if gone and purged else "FAIL",
                    f"account {sol.account}: deleted={gone}, purged={purged}", time.time() - t0)

        t0 = time.time()
        group = json.loads(f.az(['group', 'show', '--name', rg, '-o', 'json']))
        others = json.loads(f.az(['resource', 'list', '--resource-group', rg, '--query', '[].id', '-o', 'json']))
        ours = (group.get("tags") or {}).get("solution") == f.SOLUTION_TAG
        if ours and not others:
            f.az(['group', 'delete', '--name', rg, '--yes'])
            exists = f.az(['group', 'exists', '--name', rg]).strip()
            receipt.add("Resource group removed", "PASS" if exists == "false" else "FAIL", f"az group exists: {exists}", time.time() - t0)
        else:
            reason = f"it holds {len(others)} other resource(s)" if others else "up.py did not create it"
            receipt.add("Resource group kept", "PASS", f"{rg} is left in place because {reason}", time.time() - t0)

    status = receipt.close()
    print(f"\nRESULT: {status}   receipt: {receipt.path}")
    if status == "PASS" and not args.all:
        print(f"The hourly GPU charge has stopped. Account {sol.account} and its trained adapters are kept; "
              f"`python infra/down.py --resource-group {rg} --all` removes them too.")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    f.main_guard(main)
