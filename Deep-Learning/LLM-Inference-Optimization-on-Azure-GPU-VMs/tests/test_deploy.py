"""Tests for the deployment path: container start script, readiness check, settings template and README order."""
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_launch  # noqa: E402

RUN_ROLE = (ROOT / "docker" / "run-role.sh").read_text(encoding="utf-8")
WAIT_READY = (ROOT / "docker" / "wait-ready.sh").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / "docker" / "mimo.env.example").read_text(encoding="utf-8")


def _code(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


class DeployTests(unittest.TestCase):
    def test_service_is_the_container_main_process(self):
        code = _code(RUN_ROLE)
        self.assertNotIn("sleep infinity", code)
        self.assertNotIn("docker exec", code)
        self.assertIn("bash /opt/mimo/launch.sh", code)
        for flag in ("--restart on-failure", "--log-opt max-size", "--env-file", "/models:ro", "launch.sh:ro"):
            self.assertIn(flag, code, flag)

    def test_only_gpu_roles_get_host_privileges(self):
        code = _code(RUN_ROLE)
        router = code.split('if [ "$ROLE" = router ]', 1)[1].split("\nfi\n", 1)[0]
        bench = code.split('if [ "$ROLE" = bench ]', 1)[1].split("\nfi\n", 1)[0]
        for block in (router, bench):
            self.assertNotIn("--privileged", block)
            self.assertNotIn("/dev/", block)
        gpu = code.split('if [ "$ROLE" = router ]', 1)[1].split("\nfi\n", 1)[1]
        for flag in ("--privileged", "/dev/kfd", "/dev/dri", "/dev/mem", "CAP_SYS_ADMIN"):
            self.assertIn(flag, gpu, flag)

    def test_rendered_scripts_exec_the_server(self):
        for profile, role in (("rocm-mi300x-pd", "prefill"), ("rocm-mi300x-pd", "decode"), ("rocm-mi300x-pd", "router"),
                              ("rocm-mi300x-single", "server")):
            with self.subTest(profile=profile, role=role):
                out = render_launch.render(render_launch.load_profile(profile), role, [])
                command = [l for l in out.splitlines() if not l.startswith(("#", "export ", "  "))]
                self.assertEqual(len(command), 1, command)
                self.assertTrue(command[0].startswith("exec "), command[0])

    def test_serving_renders_carry_no_benchmark_switch(self):
        """The commands the README deploys: real MTP acceptance, no fixed-acceptance variables."""
        cases = [("rocm-mi300x-pd", "prefill", ["simulated-acceptance"]), ("rocm-mi300x-pd", "decode", ["simulated-acceptance"]),
                 ("rocm-mi300x-single", "server", [])]
        for profile, role, ablate in cases:
            with self.subTest(profile=profile, role=role):
                env, argv, _ = render_launch.compose(render_launch.load_profile(profile), role, ablate)
                self.assertFalse([k for k in env if k.startswith("SGLANG_SIMULATE_ACC")])
                self.assertNotIn("--disable-cuda-graph", argv) if role != "prefill" else None

    def test_readiness_uses_a_non_generating_endpoint(self):
        code = _code(WAIT_READY)
        self.assertIn("/server_info", code)
        self.assertNotIn("/health", code)

    def test_env_template_defines_every_variable_the_serving_scripts_read(self):
        defined = set(re.findall(r"^([A-Z_]+)=", ENV_EXAMPLE, re.M))
        for profile, role in (("rocm-mi300x-pd", "prefill"), ("rocm-mi300x-pd", "decode"), ("rocm-mi300x-pd", "router"),
                              ("rocm-mi300x-single", "server")):
            out = render_launch.render(render_launch.load_profile(profile), role, [])
            used = set(re.findall(r"\$\{([A-Z_]+)\}", out))
            self.assertEqual(used - defined, set(), (profile, role))

    def test_reproduction_leads_with_deployment_not_self_checks(self):
        for name, heading in (("README.md", "## Reproduce in Your Environment"), ("README_CN.md", "## 客户如何复现")):
            text = (ROOT / name).read_text(encoding="utf-8")
            section = text.split(heading, 1)[1].split("\n## ", 1)[0]
            blocks = re.findall(r"```bash\n(.*?)```", section, re.S)
            self.assertTrue(blocks, name)
            joined = "\n".join(blocks)
            self.assertNotIn("unittest", joined, name)
            self.assertNotIn("--check", joined, name)
            self.assertNotIn("sleep infinity", joined, name)
            self.assertIn("docker buildx build", joined, name)
            self.assertIn("run-role.sh", joined, name)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "runs the script with a fake docker (Linux/macOS CI)")
    def test_run_role_builds_the_expected_docker_command(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake = tmp / "docker"
            fake.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$ARGV_OUT"\n', encoding="utf-8")
            fake.chmod(0o755)
            env_file = tmp / "mimo.env"
            env_file.write_text("IMAGE=registry.example/mimo@sha256:abc\nMODEL_PATH=/models/m\n", encoding="utf-8")
            script = tmp / "launch.sh"
            script.write_text("exec true\n", encoding="utf-8")
            (tmp / "models").mkdir()
            base = dict(os.environ, PATH=f"{tmp}:{os.environ['PATH']}", ENV_FILE=str(env_file), MODELS=str(tmp / "models"))
            base.pop("IMAGE", None)

            def run(role):
                out = tmp / f"{role}.argv"
                done = subprocess.run(["bash", str(ROOT / "docker" / "run-role.sh"), role, str(script)],
                                      env=dict(base, ARGV_OUT=str(out)), capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                return out.read_text(encoding="utf-8").splitlines()

            for role in ("server", "prefill", "decode", "router", "bench"):
                with self.subTest(role=role):
                    argv = run(role)
                    self.assertEqual(argv[0], "run")
                    self.assertEqual(argv[-3:], ["registry.example/mimo@sha256:abc", "bash", "/opt/mimo/launch.sh"])
                    flags = argv[:-3]
                    self.assertIn(f"{script}:/opt/mimo/launch.sh:ro", flags)
                    self.assertIn("--env-file", flags)
                    gpu = role in ("server", "prefill", "decode")
                    self.assertEqual("--privileged" in flags, gpu)
                    self.assertEqual("/dev/kfd" in flags, gpu)
                    self.assertEqual(any(f.endswith(":/models:ro") for f in flags), role != "router")
                    self.assertEqual("--rm" in flags, role == "bench")
                    if role != "bench":
                        self.assertIn(f"mimo-{role}", flags)
                        self.assertIn("on-failure:3", flags)

            env_file.write_text("IMAGE=\n", encoding="utf-8")
            done = subprocess.run(["bash", str(ROOT / "docker" / "run-role.sh"), "router", str(script)],
                                  env=dict(base, ARGV_OUT=str(tmp / "x")), capture_output=True, text=True)
            self.assertEqual(done.returncode, 2)
            self.assertIn("IMAGE is empty", done.stderr)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash") and shutil.which("curl"), "needs bash and curl (Linux/macOS CI)")
    def test_wait_ready_requires_json_and_reports_capacity(self):
        import http.server
        import json
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            payload = b"{}"

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(Handler.payload)

            def log_message(self, *args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = str(server.server_address[1])
        try:
            Handler.payload = json.dumps({"internal_states": [{"max_total_num_tokens": 1442464}]}).encode()
            done = subprocess.run(["bash", str(ROOT / "docker" / "wait-ready.sh"), "127.0.0.1", port, "5"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("max_total_num_tokens=1442464", done.stdout)
            Handler.payload = b"<html>not json</html>"
            done = subprocess.run(["bash", str(ROOT / "docker" / "wait-ready.sh"), "127.0.0.1", port, "1"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 1)
            self.assertIn("NOT READY", done.stderr)
        finally:
            server.shutdown()
            server.server_close()

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "bash -n runs on Linux and macOS (CI)")
    def test_shell_scripts_parse(self):
        for name in ("run-role.sh", "wait-ready.sh"):
            with self.subTest(script=name):
                done = subprocess.run(["bash", "-n", str(ROOT / "docker" / name)], capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
