"""Tests for tools/render_launch.py and the launch profiles."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import render_launch  # noqa: E402


class LaunchTests(unittest.TestCase):
    def test_every_profile_role_renders(self):
        for path in (ROOT / "profiles").glob("*.json"):
            if path.name == "techniques.json":
                continue
            profile = json.loads(path.read_text(encoding="utf-8"))
            for role in profile["roles"]:
                with self.subTest(profile=profile["profile"], role=role):
                    out = render_launch.render(profile, role, [])
                    self.assertIn(f"profile={profile['profile']}", out)

    def test_measured_mi300x_decode_matches_the_measured_script(self):
        env, argv, _ = render_launch.compose(render_launch.load_profile("rocm-mi300x-pd"), "decode", [])
        for key, value in {"SGLANG_USE_AITER": "1", "SGLANG_AITER_UNIFIED_VERIFY": "1",
                           "SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE": "1", "SGLANG_SIMULATE_ACC_LEN": "3"}.items():
            self.assertEqual(env[key], value)
        joined = " ".join(argv)
        for fragment in ("--attention-backend aiter", "--kv-cache-dtype fp8_e4m3", "--page-size 32",
                         "--chunked-prefill-size 32768", "--disaggregation-mode decode",
                         "--speculative-num-steps 3", "--enable-multi-layer-eagle"):
            self.assertIn(fragment, joined)

    def test_final_single_vm_runtime_enables_flydsl_and_5d(self):
        env, argv, _ = render_launch.compose(render_launch.load_profile("rocm-mi300x-single"), "decode", [])
        self.assertEqual(env["SGLANG_AITER_PA_DECODE_IMPL"], "flydsl")
        self.assertEqual(env["SGLANG_FLYDSL_PA_NUM_PARTITIONS"], "16")
        self.assertEqual(env["SGLANG_AITER_KV_CACHE_LAYOUT"], "vectorized_5d")
        joined = " ".join(argv)
        self.assertIn("--page-size 64", joined)
        self.assertIn("--disaggregation-transfer-backend fake", joined)

    def test_ablation_removes_exactly_one_technique(self):
        profile = render_launch.load_profile("rocm-mi300x-pd")
        env_on, argv_on, _ = render_launch.compose(profile, "decode", [])
        env_off, argv_off, _ = render_launch.compose(profile, "decode", ["ck-a8w8-gemm"])
        self.assertNotIn("SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE", env_off)
        self.assertEqual(argv_on, argv_off)
        self.assertEqual({k: v for k, v in env_on.items() if k != "SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE"}, env_off)

    def test_ablating_graph_capture_disables_it_on_decode_only(self):
        profile = render_launch.load_profile("rocm-mi300x-pd")
        _, on, _ = render_launch.compose(profile, "decode", [])
        _, off, _ = render_launch.compose(profile, "decode", ["decode-graph-capture"])
        self.assertNotIn("--disable-cuda-graph", on)
        self.assertEqual(off, on + ["--disable-cuda-graph"])
        _, prefill, _ = render_launch.compose(profile, "prefill", [])
        self.assertIn("--disable-cuda-graph", prefill)

    def test_ablating_tuned_moe_sets_the_bypass_switch(self):
        env, _, _ = render_launch.compose(render_launch.load_profile("rocm-mi300x-pd"), "prefill", ["tuned-fused-moe"])
        self.assertEqual(env["AITER_BYPASS_TUNE_CONFIG"], "1")

    def test_cuda_template_uses_no_rocm_switches(self):
        profile = render_launch.load_profile("cuda-hopper-pd")
        self.assertEqual(profile["status"], "TEMPLATE_NOT_MEASURED")
        for role in profile["roles"]:
            env, argv, _ = render_launch.compose(profile, role, [])
            text = " ".join(argv) + " " + " ".join(env)
            self.assertNotRegex(text, r"AITER|ROCM|HSA_|aiter|flydsl", role)

    def test_int8_quick_reduce_is_explicit_and_ablatable(self):
        profile = render_launch.load_profile("rocm-mi300x-pd")
        env_on, _, _ = render_launch.compose(profile, "decode", [])
        env_off, _, _ = render_launch.compose(profile, "decode", ["int8-quick-reduce"])
        self.assertEqual(env_on["ROCM_QUICK_REDUCE_QUANTIZATION"], "INT8")
        self.assertEqual(env_off["ROCM_QUICK_REDUCE_QUANTIZATION"], "NONE")

    def test_accuracy_role_runs_real_acceptance_and_full_precision_reduce(self):
        env, _, _ = render_launch.compose(render_launch.load_profile("rocm-mi300x-single"), "server", [])
        self.assertEqual(env["ROCM_QUICK_REDUCE_QUANTIZATION"], "NONE")
        self.assertNotIn("SGLANG_SIMULATE_ACC_LEN", env)
        self.assertEqual(env["SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY"], "1")

    def test_ablating_fp8_kv_requires_ablating_flydsl(self):
        profile = render_launch.load_profile("rocm-mi300x-single")
        with self.assertRaises(SystemExit):
            render_launch.compose(profile, "server", ["fp8-kv-5d"])
        env, argv, _ = render_launch.compose(profile, "server", ["fp8-kv-5d", "flydsl-pa-decode"])
        self.assertNotIn("--kv-cache-dtype", argv)
        self.assertNotIn("SGLANG_AITER_PA_DECODE_IMPL", env)

    def test_unknown_technique_and_role_are_rejected(self):
        profile = render_launch.load_profile("rocm-mi300x-pd")
        with self.assertRaises(SystemExit):
            render_launch.compose(profile, "decode", ["no-such-technique"])
        with self.assertRaises(SystemExit):
            render_launch.compose(profile, "no-such-role", [])
        with self.assertRaises(SystemExit):
            render_launch.compose(profile, "decode", ["flydsl-pa-decode"])

    def test_profiles_keep_hosts_and_paths_as_variables(self):
        for path in (ROOT / "profiles").glob("*.json"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\b(?!0\.0\.0\.0\b)(?!127\.0\.0\.1\b)(?:\d{1,3}\.){3}\d{1,3}\b", path.name)
            self.assertNotRegex(text, r"\"/(?:data|home|root)/", path.name)


if __name__ == "__main__":
    unittest.main()
