"""Platform sign-in: create-query-identity.sh and query-gpu-hours.sh against fake `az` and `curl`."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_scripts import _bash  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
import gpu_hours_client as client  # noqa: E402

CREATE = ROOT / "scripts" / "create-query-identity.sh"
QUERY = ROOT / "scripts" / "query-gpu-hours.sh"
SECRET = "s3cret-value-never-printed"

FAKE_AZ = r"""#!/bin/bash
echo "$*" >> "$AZ_LOG"
case "$*" in
  *"--query customerId"*) echo "workspace-guid" ;;
  "monitor log-analytics workspace show"*) echo "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.OperationalInsights/workspaces/law" ;;
  "account show"*) echo "tenant-guid" ;;
  "ad app list"*) printf '%s' "${FAKE_APPS:-}" ;;
  "ad app create"*) echo "app-new" ;;
  "ad sp list"*) echo "${FAKE_SP:-}" ;;
  "ad sp create"*) echo "sp-new" ;;
  "role assignment list"*) echo "${FAKE_ASSIGNED:-0}" ;;
  "role assignment create"*) exit "${FAKE_ROLE_FAIL:-0}" ;;
  "ad app credential reset"*) echo "$FAKE_SECRET" ;;
  "ad app credential list"*) echo "2030-01-01T00:00:00Z" ;;
esac
exit 0
"""

FAKE_CURL = r"""#!/bin/bash
out=""; url=""; previous=""; stdin_secret=0
for arg in "$@"; do
  [[ "$previous" == "-o" ]] && out="$arg"
  [[ "$arg" == https://* ]] && url="$arg"
  [[ "$arg" == "client_secret@-" ]] && stdin_secret=1
  previous="$arg"
done
echo "$*" >> "$CURL_LOG"
if [[ "$url" == *login.microsoftonline.com* ]]; then
  secret=""; (( stdin_secret )) && secret=$(cat)
  if [[ "$secret" == "$GOOD_SECRET" ]]; then echo '{"access_token":"tok-123"}' > "$out"; printf 200
  else echo '{"error":"invalid_client","error_description":"AADSTS7000215: Invalid client secret provided."}' > "$out"; printf 401; fi
else
  for arg in "$@"; do [[ "$arg" == @*auth.header ]] && cat "${arg#@}" >> "$CURL_LOG"; done
  if [[ "${FAKE_QUERY:-ok}" == forbidden ]]; then
    echo '{"error":{"code":"InsufficientAccessError","message":"insufficient access"}}' > "$out"; printf 403
  else
    echo '{"tables":[{"columns":[{"name":"Computer"},{"name":"BusyGpuHours"}],"rows":[["vm-a",1.5]]}]}' > "$out"; printf 200
  fi
fi
"""


@unittest.skipUnless(_bash(), "bash not available")
class AuthScriptTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = Path(holder.name)
        stub = self.tmp / "bin"
        stub.mkdir()
        for name, body in (("az", FAKE_AZ), ("curl", FAKE_CURL)):
            (stub / name).write_bytes(body.encode())
            (stub / name).chmod(0o755)
        self.env = {**os.environ, "AZ_LOG": str(self.tmp / "az.log"), "CURL_LOG": str(self.tmp / "curl.log"),
                    "FAKE_SECRET": SECRET, "GOOD_SECRET": SECRET, "GPUHOURS_CURL": str(stub / "curl").replace("\\", "/"), "PATH": str(stub) + os.pathsep + os.environ["PATH"]}

    def run_script(self, script, *args, **env):
        res = subprocess.run([_bash(), str(script).replace("\\", "/"), *args], cwd=self.tmp,
                             env={**self.env, **env}, capture_output=True, text=True, encoding="utf-8", timeout=120)
        return res

    def log(self, name):
        path = self.tmp / name
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_first_run_creates_app_role_and_secret_file_without_printing_the_secret(self):
        res = self.run_script(CREATE, "-g", "rg")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn(SECRET, res.stdout + res.stderr)
        az = self.log("az.log")
        self.assertIn("ad app create --display-name gpu-hours-query --sign-in-audience AzureADMyOrg", az)
        self.assertIn("ad sp create --id app-new", az)
        self.assertIn('--assignee-object-id sp-new --assignee-principal-type ServicePrincipal --role Log Analytics Reader', az)
        self.assertNotIn("Contributor", az)
        text = (self.tmp / "gpu-hours.query.env").read_text(encoding="utf-8")
        for line in ("AZURE_TENANT_ID=tenant-guid", "AZURE_CLIENT_ID=app-new", f"AZURE_CLIENT_SECRET={SECRET}",
                     "WORKSPACE_GUID=workspace-guid"):
            self.assertIn(line, text)
        if os.name != "nt":
            self.assertEqual((self.tmp / "gpu-hours.query.env").stat().st_mode & 0o777, 0o600)

    def test_rerun_reuses_app_role_and_secret(self):
        self.assertEqual(self.run_script(CREATE, "-g", "rg", FAKE_APPS="app-1\n", FAKE_SP="sp-1",
                                         FAKE_ASSIGNED="0").returncode, 0)
        before = (self.tmp / "gpu-hours.query.env").read_text(encoding="utf-8")
        (self.tmp / "az.log").unlink()
        res = self.run_script(CREATE, "-g", "rg", FAKE_APPS="app-1\n", FAKE_SP="sp-1", FAKE_ASSIGNED="1",
                              FAKE_SECRET="another-secret")
        self.assertEqual(res.returncode, 0, res.stderr)
        az = self.log("az.log")
        for call in ("ad app create", "ad sp create", "role assignment create", "credential reset"):
            self.assertNotIn(call, az)
        self.assertIn("kept the secret", res.stdout)
        self.assertEqual((self.tmp / "gpu-hours.query.env").read_text(encoding="utf-8"), before)

    def test_rotate_adds_a_secret_without_removing_the_old_one(self):
        self.run_script(CREATE, "-g", "rg", FAKE_APPS="app-1\n", FAKE_SP="sp-1", FAKE_ASSIGNED="1")
        res = self.run_script(CREATE, "-g", "rg", "-r", FAKE_APPS="app-1\n", FAKE_SP="sp-1", FAKE_ASSIGNED="1",
                              FAKE_SECRET="rotated-secret")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("credential reset --id app-1 --append", self.log("az.log"))
        self.assertIn("AZURE_CLIENT_SECRET=rotated-secret", (self.tmp / "gpu-hours.query.env").read_text(encoding="utf-8"))

    def test_ambiguous_app_name_stops_before_any_change(self):
        res = self.run_script(CREATE, "-g", "rg", FAKE_APPS="app-1\napp-2\n")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("several app registrations", res.stderr)
        self.assertNotIn("role assignment create", self.log("az.log"))
        self.assertFalse((self.tmp / "gpu-hours.query.env").exists())

    def write_settings(self, secret=SECRET):
        (self.tmp / "q.env").write_bytes(
            f"AZURE_TENANT_ID=tenant-guid\r\nAZURE_CLIENT_ID=app-1\r\nAZURE_CLIENT_SECRET={secret}\r\n"
            "WORKSPACE_GUID=workspace-guid\r\n".encode())
        (self.tmp / "v.kql").write_text("GpuMetrics_CL | take 1\n", encoding="utf-8")

    def test_query_signs_in_with_client_credentials_and_returns_objects(self):
        self.write_settings()
        res = self.run_script(QUERY, "-c", "q.env", "-q", "v.kql", "-t", "PT1H")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn('"Computer": "vm-a"', res.stdout)
        self.assertIn('"BusyGpuHours": 1.5', res.stdout)
        curl = self.log("curl.log")
        self.assertIn("https://login.microsoftonline.com/tenant-guid/oauth2/v2.0/token", curl)
        self.assertIn("grant_type=client_credentials", curl)
        self.assertIn("scope=https://api.loganalytics.io/.default", curl)
        self.assertIn("https://api.loganalytics.azure.com/v1/workspaces/workspace-guid/query", curl)
        self.assertIn("Authorization: Bearer tok-123", curl)
        self.assertNotIn(SECRET, curl, "the secret must not appear on a curl command line")

    def test_wrong_secret_exits_4(self):
        self.write_settings(secret="wrong")
        res = self.run_script(QUERY, "-c", "q.env", "-q", "v.kql")
        self.assertEqual(res.returncode, 4, res.stderr)
        self.assertIn("sign-in rejected (HTTP 401) invalid_client", res.stderr)

    def test_missing_role_exits_5(self):
        self.write_settings()
        res = self.run_script(QUERY, "-c", "q.env", "-q", "v.kql", FAKE_QUERY="forbidden")
        self.assertEqual(res.returncode, 5, res.stderr)
        self.assertIn("query rejected (HTTP 403) InsufficientAccessError", res.stderr)

    def test_missing_key_fails_before_any_request(self):
        (self.tmp / "q.env").write_text("AZURE_TENANT_ID=t\nAZURE_CLIENT_ID=c\n", encoding="utf-8")
        (self.tmp / "v.kql").write_text("x\n", encoding="utf-8")
        res = self.run_script(QUERY, "-c", "q.env", "-q", "v.kql")
        self.assertEqual(res.returncode, 1)
        self.assertIn("AZURE_CLIENT_SECRET is missing", res.stderr)
        self.assertEqual(self.log("curl.log"), "")


class PythonCredentialTests(unittest.TestCase):
    def test_credentials_file_gives_a_client_secret_credential(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.env"
            path.write_text("# comment\nAZURE_TENANT_ID=tenant-guid\nAZURE_CLIENT_ID=app-1\n"
                            f"AZURE_CLIENT_SECRET={SECRET}\nWORKSPACE_GUID=workspace-guid\n", encoding="utf-8")
            values = client.read_credentials(path)
        self.assertEqual(values["WORKSPACE_GUID"], "workspace-guid")
        from azure.identity import ClientSecretCredential
        self.assertIsInstance(client.credential_from(values), ClientSecretCredential)

    def test_incomplete_credentials_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "q.env"
            path.write_text("AZURE_TENANT_ID=t\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                client.read_credentials(path)


if __name__ == "__main__":
    unittest.main()
