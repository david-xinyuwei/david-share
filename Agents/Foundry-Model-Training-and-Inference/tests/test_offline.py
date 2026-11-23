"""Offline tests of the deployment scripts' own logic. No Azure sign-in, no network, no cost.

    python -m unittest discover -s tests -v

They cover the decisions the scripts make from service responses: which training jobs have a deployable adapter,
which project models named with --adapter-model are deployed, how adapter deployments are named, how the saved
checkpoint and the metrics of a Programmed Training session are read, how held-out answers are scored, and how a
run is recorded. They do not call Azure; `infra/verify.py` is the check of a real deployment.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "infra"))

import foundry as f  # noqa: E402
import verify  # noqa: E402

BASE_V3 = f.BASE_MODEL_FAMILY + "3"


def job(job_id, status="succeeded", source=None, created=100, **extra):
    return {"id": job_id, "status": status, "created_at": created, "training_file": "file-train",
            "metadata": {"deployment_options": [
                {"format": "ManagedCompute", "base_model_asset_id": BASE_V3, "source_model_id": source},
                {"format": "Fireworks", "source_model_id": None}]}, **extra}


def model(name, base=BASE_V3, weight="LoRA"):
    return {"id": f"azureai://accounts/a/projects/p/models/{name}/versions/1", "name": name, "weightType": weight,
            "derivedModelInformation": {"baseModel": base}}


class DeployableAdapters(unittest.TestCase):
    def test_job_without_registered_adapter_is_not_deployable(self):
        """A job can succeed without registering an adapter in the project: its source_model_id stays empty."""
        self.assertEqual(f.deployable_adapters([job("ftjob-1", source=None, suffix="gsm8k")], [], "t"), [])

    def test_registered_adapter_is_found_through_the_job(self):
        m = model("model_ab-final")
        got = f.deployable_adapters([job("ftjob-1", source=m["id"], display_name="gsm8k")], [m], "qwen38-lora")
        self.assertEqual([(a["name"], a["sourceModelId"], a["baseModel"]) for a in got], [("qwen38-lora-gsm8k", m["id"], BASE_V3)])

    def test_job_pointing_to_a_model_missing_from_the_project_is_skipped(self):
        self.assertEqual(f.deployable_adapters([job("ftjob-1", source="azureai://accounts/a/projects/p/models/x/versions/1")], [], "t"), [])

    def test_running_and_failed_jobs_are_skipped(self):
        m = model("m1")
        jobs = [job("ftjob-1", status="running", source=m["id"]), job("ftjob-2", status="failed", source=m["id"])]
        self.assertEqual(f.deployable_adapters(jobs, [m], "t"), [])

    def test_newest_job_wins_for_one_name(self):
        old, new = model("old"), model("new")
        jobs = [job("ftjob-1", source=old["id"], created=1, suffix="gsm8k"), job("ftjob-2", source=new["id"], created=2, suffix="gsm8k")]
        got = f.deployable_adapters(jobs, [old, new], "t")
        self.assertEqual([a["sourceModelId"] for a in got], [new["id"]])

    def test_adapter_of_another_base_model_is_excluded(self):
        other = model("other", base="azureml://registries/azure-huggingface/models/qwen--qwen3.6-35b-a3b/versions/2")
        self.assertEqual(f.deployable_adapters([job("ftjob-1", source=other["id"])], [other], "t"), [])

    def test_at_most_eight_adapters_per_target(self):
        models = [model(f"m{i}") for i in range(10)]
        jobs = [job(f"ftjob-{i}", source=models[i]["id"], created=i, suffix=f"s{i}") for i in range(10)]
        self.assertEqual(len(f.deployable_adapters(jobs, models, "t")), f.MAX_ADAPTERS_PER_TARGET)


class AdapterNames(unittest.TestCase):
    def test_portal_display_name_is_preferred_over_suffix(self):
        self.assertEqual(f.adapter_name("qwen38-lora", {"id": "ftjob-1", "display_name": "support", "suffix": "x"}), "qwen38-lora-support")

    def test_characters_outside_the_allowed_set_are_replaced(self):
        self.assertEqual(f.adapter_name("t", {"id": "ftjob-1", "suffix": "my adapter/v2!"}), "t-my-adapter-v2")

    def test_name_falls_back_to_the_job_id_and_fits_64_characters(self):
        self.assertEqual(f.adapter_name("t", {"id": "ftjob-0123456789abcdef"}), "t-89abcdef")
        long = f.adapter_name("t", {"id": "ftjob-1", "suffix": "x" * 100})
        self.assertLessEqual(len(long), 64)
        self.assertRegex(long, r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class NamedAdapters(unittest.TestCase):
    """--adapter-model: a LoRA model of the project that no training job points to, such as a Programmed Training checkpoint."""

    def test_named_model_is_deployed_under_its_label(self):
        m = model("model_ab12-final")
        got = f.adapters_to_deploy([], [m], "qwen38-lora", ["model_ab12-final=gsm8k-pt"])
        self.assertEqual([(a["name"], a["sourceModelId"], a["baseModel"], a["job"]) for a in got],
                         [("qwen38-lora-gsm8k-pt", m["id"], BASE_V3, None)])

    def test_label_defaults_to_the_model_name(self):
        got = f.named_adapters(["model_ab12-final"], [model("model_ab12-final")], "t")
        self.assertEqual([a["name"] for a in got], ["t-ab12-final"])

    def test_unknown_model_and_full_weights_stop(self):
        with self.assertRaisesRegex(f.Stop, "no LoRA model with this name"):
            f.named_adapters(["model_missing"], [model("model_ab12-final")], "t")
        with self.assertRaisesRegex(f.Stop, "no LoRA model with this name"):
            f.named_adapters(["full"], [model("full", weight="FullWeight")], "t")

    def test_model_of_another_base_model_stops(self):
        other = model("other", base="azureml://registries/azure-huggingface/models/qwen--qwen3.6-35b-a3b/versions/2")
        with self.assertRaisesRegex(f.Stop, "not on qwen3.8-27b"):
            f.named_adapters(["other"], [other], "t")

    def test_named_adapters_come_before_the_adapters_of_jobs(self):
        from_job, saved = model("model_job-final"), model("model_ab12-final")
        jobs = [job("ftjob-1", source=from_job["id"], display_name="gsm8k")]
        got = f.adapters_to_deploy(jobs, [from_job, saved], "t", ["model_ab12-final=gsm8k-pt"])
        self.assertEqual([a["name"] for a in got], ["t-gsm8k-pt", "t-gsm8k"])

    def test_model_named_on_the_command_line_is_listed_once(self):
        m = model("model_job-final")
        got = f.adapters_to_deploy([job("ftjob-1", source=m["id"], display_name="gsm8k")], [m], "t", ["model_job-final=other"])
        self.assertEqual([a["name"] for a in got], ["t-other"])

    def test_two_adapters_with_one_deployment_name_stop(self):
        from_job, saved = model("model_job-final"), model("model_ab12-final")
        jobs = [job("ftjob-1", source=from_job["id"], display_name="gsm8k")]
        with self.assertRaisesRegex(f.Stop, "Two adapters would get the deployment name t-gsm8k"):
            f.adapters_to_deploy(jobs, [from_job, saved], "t", ["model_ab12-final=gsm8k"])


class Sessions(unittest.TestCase):
    """What training/programmed_training_sft.py reads after its session: the saved checkpoint and the metrics file."""

    def test_final_checkpoint_of_the_session_is_found_by_its_tag(self):
        def tagged(name, session):
            return {**model(name), "tags": {"session": session}}
        models = [tagged("model_ab12-28", "session_ab12"), tagged("model_ab12-final", "session_ab12"),
                  tagged("model_cd34-final", "session_cd34")]
        self.assertEqual(f.session_adapter(models, "session_ab12")["name"], "model_ab12-final")
        self.assertIsNone(f.session_adapter(models, "session_ef56"))
        self.assertIsNone(f.session_adapter([model("model_ab12-final")], "session_ab12"))  # no tag: not this session's model

    def test_summary_counts_steps_tokens_and_validation_passes(self):
        rows = [{"step": 0, "train_mean_nll": 0.9, "num_tokens": 100, "test/nll": 0.91},
                {"step": 1, "train_mean_nll": 0.5, "num_tokens": 120},
                {"step": 1, "test/nll": 0.42}]
        self.assertEqual(f.session_summary(rows),
                         {"steps": 2, "trainingTokens": 220, "trainingLoss": [0.9, 0.5], "validationLoss": [0.91, 0.42]})


class Scoring(unittest.TestCase):
    def test_marker_wins_over_later_numbers(self):
        self.assertEqual(verify.final_number("162*2=324\n#### 324\nThe answer is: 324"), (324.0, True))

    def test_last_number_is_used_without_marker(self):
        self.assertEqual(verify.final_number("Tom has **8** apples."), (8.0, False))
        self.assertEqual(verify.final_number("It costs $12,000 in total."), (12000.0, False))

    def test_last_number_scorer_misses_a_right_answer_followed_by_another_number(self):
        """The known limit of this scorer: 'It will take 8 days ... into 16 amoebae' is right, but the last number is 16."""
        row = verify.score_row("... after 8 days.\n#### 8!!!", "It will take **8** days for one amoeba to divide into 16 amoebae.")
        self.assertEqual((row["gold"], row["predicted"], row["correct"]), (8.0, 16.0, False))

    def test_reference_format_of_the_sample_data(self):
        row = verify.score_row("Natalia sold 48+24 = <<48+24=72>>72 clips altogether.\n#### 72!!!", "48/2=24\n48+24=72\n#### 72")
        self.assertTrue(row["correct"] and row["marker"])

    def test_no_number_is_not_correct(self):
        self.assertFalse(verify.score_row("#### 5!!!", "I cannot tell.")["correct"])


class Receipts(unittest.TestCase):
    def test_receipt_is_pass_only_when_every_step_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = f.Receipt(Path(tmp) / "r.json")
            r.add("1 Preflight", "PASS")
            r.add("4 Trained adapter", "INFO", "none yet")
            self.assertEqual(r.close(), "PASS")
            r.add("5 Target deployment", "FAIL", "quota")
            self.assertEqual(r.close(), "FAIL")
            doc = json.loads((Path(tmp) / "r.json").read_text(encoding="utf-8"))
            self.assertEqual([s["status"] for s in doc["steps"]], ["PASS", "INFO", "FAIL"])

    def test_empty_receipt_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(f.Receipt(Path(tmp) / "r.json").close(), "FAIL")


class Endpoints(unittest.TestCase):
    def setUp(self):
        self.sol = f.Solution("sub", "rg", "acct", "proj", "eastus2", "https://acct.example.invalid/api/projects/proj/", "qwen38-lora")

    def test_chat_route_is_on_the_account_endpoint(self):
        self.assertEqual(self.sol.chat_url, "https://acct.example.invalid/openai/v1/chat/completions")
        self.assertEqual(self.sol.openai, "https://acct.example.invalid/api/projects/proj/openai/v1")

    def test_arm_urls_use_the_tested_api_versions(self):
        self.assertTrue(self.sol.target_url().endswith("/accounts/acct/managedComputeDeployments/qwen38-lora?api-version=2026-11-01"))
        self.assertTrue(self.sol.adapter_url("a1").endswith("/accounts/acct/adapterDeployments/a1?api-version=2026-09-15-preview"))
        self.assertTrue(self.sol.target_url(collection=True).endswith("/managedComputeDeployments?api-version=2026-11-01"))

    def test_source_model_id_reads_the_managed_compute_option(self):
        self.assertEqual(f.source_model_id(job("j", source="azureai://x")), "azureai://x")
        self.assertIsNone(f.source_model_id({"id": "j", "metadata": {}}))


if __name__ == "__main__":
    unittest.main()
