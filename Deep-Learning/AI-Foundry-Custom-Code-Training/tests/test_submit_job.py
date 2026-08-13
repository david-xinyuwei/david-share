"""Cloud-adapter failure-path tests using an in-memory SDK fake."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import job_status  # noqa: E402
import submit_job  # noqa: E402
from job_contract import ContractError, REQUIRED_SAMPLE_FILES  # noqa: E402


def valid_record() -> dict:
    return {
        "data_source": "synthetic_test_grader",
        "prompt": [{"role": "user", "content": "Resolve synthetic order TEST-001."}],
        "reward_model": {"ground_truth": "Action: synthetic pass."},
        "extra_info": {"fixture": True},
    }


def write_cloud_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    sample = root / "sample"
    for relative in REQUIRED_SAMPLE_FILES:
        path = sample / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".jsonl":
            path.write_text(json.dumps(valid_record()) + "\n", encoding="utf-8")
        elif path.suffix == ".yaml":
            path.write_text("tools: []\n", encoding="utf-8")
        else:
            path.write_text("# synthetic test fixture\n", encoding="utf-8")

    config = {
        "projectEndpoint": "https://account.services.ai.azure.com/api/projects/project",
        "computeId": (
            "/subscriptions/sub/resourcegroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/account/computes/cluster"
        ),
        "computeClusterSku": "STANDARD_NC96ADS_A100_V4",
        "uamiId": (
            "/subscriptions/sub/resourcegroups/rg/providers/"
            "Microsoft.ManagedIdentity/userAssignedIdentities/uami"
        ),
        "storageConnectionName": "storage",
        "environmentImage": "registry.example/verl:verified",
        "nodeCount": 1,
        "gpusPerNode": 4,
        "codeDatasetName": "test-code",
        "dataDatasetName": "test-data",
    }
    overrides = {
        "NCCL_P2P_DISABLE": "1",
        "NCCL_SHM_DISABLE": "1",
        "NCCL_DEBUG": "INFO",
        "ROLLOUT_GPU_MEMORY_UTILIZATION": "0.6",
        "TRAINER_LOGGER": '["console"]',
        "VERL_EXTRA_OVERRIDES": (
            "actor_rollout_ref.rollout.checkpoint_engine."
            "update_weights_bucket_megabytes=4096 "
            "actor_rollout_ref.actor.entropy_from_logits_with_chunking=True"
        ),
    }
    config_path = root / "config.json"
    overrides_path = root / "overrides.json"
    manifest_path = root / "input-manifest.jsonl"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    overrides_path.write_text(json.dumps(overrides), encoding="utf-8")
    rows = []
    for relative in REQUIRED_SAMPLE_FILES:
        path = sample / relative
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest_path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return config_path, overrides_path, sample, manifest_path


class FakeCredential:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        self.__class__.instances.append(self)

    def close(self) -> None:
        self.closed = True


class FakeValidation:
    def __init__(self, error: Exception | None):
        self.error = error

    def try_raise(self) -> None:
        if self.error is not None:
            raise self.error


class FakeJobs:
    def __init__(
        self,
        validation_error: Exception | None = None,
        creation_error: Exception | None = None,
    ):
        self.validation_error = validation_error
        self.creation_error = creation_error
        self.validated = []
        self.created = []

    def validate(self, job):
        self.validated.append(job)
        return FakeValidation(self.validation_error)

    def create_or_update(self, *, name, job):
        self.created.append((name, job))
        if self.creation_error is not None:
            raise self.creation_error
        return SimpleNamespace(
            name=name,
            id=f"azureai://jobs/{name}",
            status="Queued",
            foundry_portal_url="https://portal.example/job",
        )


class FakeDatasets:
    def __init__(
        self,
        *,
        fail_upload_number: int | None = None,
        after_code_upload=None,
        events: list[str] | None = None,
    ):
        self.fail_upload_number = fail_upload_number
        self.after_code_upload = after_code_upload
        self.events = events
        self.calls = []
        self.uploaded_contents = {}

    def upload_folder(self, *, name, version, folder, connection_name):
        call_number = len(self.calls) + 1
        if self.events is not None:
            self.events.append(f"upload:{call_number}")
        folder_path = Path(folder)
        self.calls.append(
            {
                "name": name,
                "version": version,
                "folder": folder,
                "connectionName": connection_name,
            }
        )
        self.uploaded_contents[name] = {
            path.relative_to(folder_path).as_posix(): path.read_bytes()
            for path in folder_path.rglob("*")
            if path.is_file()
        }
        if self.fail_upload_number == call_number:
            raise RuntimeError(f"synthetic upload {call_number} failure")
        result = SimpleNamespace(id=f"azureai://datasets/{name}/versions/{version}")
        if call_number == 1 and self.after_code_upload is not None:
            self.after_code_upload(folder_path.parent)
        return result


class FakeClient:
    def __init__(
        self,
        *,
        fail_upload_number: int | None = None,
        validation_error: Exception | None = None,
        creation_error: Exception | None = None,
        after_code_upload=None,
        events: list[str] | None = None,
        close_error: Exception | None = None,
    ):
        self.datasets = FakeDatasets(
            fail_upload_number=fail_upload_number,
            after_code_upload=after_code_upload,
            events=events,
        )
        self.jobs = FakeJobs(validation_error, creation_error)
        self.beta = SimpleNamespace(jobs=self.jobs)
        self.closed = False
        self.close_error = close_error

    def close(self) -> None:
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def fake_sdk(client: FakeClient) -> dict:
    def model(**kwargs):
        return SimpleNamespace(**kwargs)

    return {
        "AIProjectClient": lambda *, endpoint, credential: client,
        "AzureCliCredential": FakeCredential,
        "DefaultAzureCredential": FakeCredential,
        "CommandJob": model,
        "Input": model,
        "JobResourceConfiguration": model,
        "Output": model,
        "RayDistribution": model,
    }


def invoke(
    monkeypatch,
    tmp_path: Path,
    client: FakeClient,
    *,
    action: str = "validate",
    credential: str = "default",
    tenant_id: str | None = None,
) -> tuple[int, Path, Path]:
    config, overrides, sample, manifest = write_cloud_inputs(tmp_path)
    evidence = tmp_path / "evidence.json"
    monkeypatch.setattr(submit_job, "_sdk_imports", lambda: fake_sdk(client))
    argv = [
        "submit_job.py",
        "--action",
        action,
        "--config",
        str(config),
        "--overrides",
        str(overrides),
        "--sample-dir",
        str(sample),
        "--expected-input-manifest",
        str(manifest),
        "--evidence",
        str(evidence),
        "--credential",
        credential,
    ]
    if tenant_id is not None:
        argv.extend(("--tenant-id", tenant_id))
    monkeypatch.setattr(sys, "argv", argv)
    return submit_job.main(), evidence, sample


def test_records_first_upload_before_rpc_failure(monkeypatch, tmp_path):
    events = []
    client = FakeClient(fail_upload_number=1, events=events)
    original_write = submit_job.write_json_atomic

    def recording_write(path, value):
        code_status = value.get("datasets", {}).get("uploads", {}).get("code", {}).get("status")
        events.append(f"write:{code_status}")
        original_write(path, value)

    monkeypatch.setattr(submit_job, "write_json_atomic", recording_write)
    with pytest.raises(RuntimeError, match="synthetic upload 1 failure"):
        invoke(monkeypatch, tmp_path, client)

    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["datasets"]["uploads"]["code"]["status"] == "UPLOADING"
    assert evidence["datasets"]["uploads"]["data"]["status"] == "PENDING"
    assert events.index("write:UPLOADING") < events.index("upload:1")
    assert evidence["recovery"]["potentiallyCreatedDatasetVersions"] == [
        evidence["datasets"]["uploads"]["code"]
    ]


def test_records_code_asset_when_data_upload_fails(monkeypatch, tmp_path):
    client = FakeClient(fail_upload_number=2)
    with pytest.raises(RuntimeError, match="synthetic upload 2 failure"):
        invoke(monkeypatch, tmp_path, client)

    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    uploads = evidence["datasets"]["uploads"]
    assert evidence["status"] == "FAILED"
    assert uploads["code"]["status"] == "UPLOADED"
    assert uploads["code"]["id"] == evidence["datasets"]["code"]
    assert uploads["data"]["status"] == "UPLOADING"
    assert uploads["code"]["version"] == evidence["datasets"]["version"]
    assert uploads["data"]["version"] == evidence["datasets"]["version"]
    assert {row["name"] for row in evidence["recovery"]["potentiallyCreatedDatasetVersions"]} == {
        "test-code",
        "test-data",
    }
    assert evidence["datasets"]["failurePolicy"]["automaticDeletion"] is False
    assert client.jobs.created == []


def test_records_both_assets_when_sdk_validation_fails(monkeypatch, tmp_path):
    client = FakeClient(validation_error=RuntimeError("synthetic validation failure"))
    with pytest.raises(RuntimeError, match="synthetic validation failure"):
        invoke(monkeypatch, tmp_path, client)

    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert evidence["status"] == "FAILED"
    assert evidence["datasets"]["uploads"]["code"]["status"] == "UPLOADED"
    assert evidence["datasets"]["uploads"]["data"]["status"] == "UPLOADED"
    assert len(evidence["recovery"]["potentiallyCreatedDatasetVersions"]) == 2
    assert client.jobs.created == []


def test_validate_uses_snapshot_and_never_submits(monkeypatch, tmp_path):
    config, overrides, sample, manifest = write_cloud_inputs(tmp_path)
    original_data = (sample / "data/train.jsonl").read_bytes()

    def mutate_source(_snapshot: Path) -> None:
        (sample / "data/train.jsonl").write_text("source changed\n", encoding="utf-8")
        config.write_text("{}\n", encoding="utf-8")
        overrides.write_text("{}\n", encoding="utf-8")
        manifest.write_text("{}\n", encoding="utf-8")

    client = FakeClient(after_code_upload=mutate_source)
    evidence = tmp_path / "evidence.json"
    monkeypatch.setattr(submit_job, "_sdk_imports", lambda: fake_sdk(client))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "submit_job.py",
            "--action",
            "validate",
            "--config",
            str(config),
            "--overrides",
            str(overrides),
            "--sample-dir",
            str(sample),
            "--expected-input-manifest",
            str(manifest),
            "--evidence",
            str(evidence),
        ],
    )

    assert submit_job.main() == 0
    assert client.datasets.uploaded_contents["test-data"]["train.jsonl"] == original_data
    assert all(Path(call["folder"]).parent != sample for call in client.datasets.calls)
    assert client.jobs.created == []
    result = json.loads(evidence.read_text(encoding="utf-8"))
    assert result["status"] == "VALIDATED_NOT_SUBMITTED"
    assert result["preflight"]["sample"]["snapshot"]["ephemeral"] is True
    assert result["preflight"]["config"]["sha256"] != hashlib.sha256(b"{}\n").hexdigest()
    assert result["preflight"]["overrides"]["sha256"] != hashlib.sha256(b"{}\n").hexdigest()


def test_rejects_snapshot_mutation_before_second_upload(monkeypatch, tmp_path):
    def mutate_snapshot(snapshot: Path) -> None:
        (snapshot / "data/train.jsonl").write_text("tampered snapshot\n", encoding="utf-8")

    client = FakeClient(after_code_upload=mutate_snapshot)
    with pytest.raises(ContractError, match="staged upload payload changed.*train.jsonl"):
        invoke(monkeypatch, tmp_path, client)

    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert len(client.datasets.calls) == 1
    assert evidence["datasets"]["uploads"]["code"]["status"] == "UPLOADED"
    assert evidence["datasets"]["uploads"]["data"]["status"] == "PENDING"


def test_submit_uses_uploaded_assets_and_records_accepted_job(monkeypatch, tmp_path):
    client = FakeClient()
    result, evidence_path, _ = invoke(monkeypatch, tmp_path, client, action="submit")

    assert result == 0
    assert len(client.jobs.validated) == 1
    assert len(client.jobs.created) == 1
    submitted_name, submitted_job = client.jobs.created[0]
    assert submitted_job is client.jobs.validated[0]
    assert submitted_job.inputs["code_dataset"].path.startswith("azureai://datasets/test-code/")
    assert submitted_job.inputs["train_data"].path.startswith("azureai://datasets/test-data/")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert evidence["status"] == "SUBMITTED"
    assert evidence["submission"] == {
        "name": submitted_name,
        "requestStatus": "ACCEPTED",
        "requestedAt": evidence["submission"]["requestedAt"],
        "id": f"azureai://jobs/{submitted_name}",
        "status": "Queued",
        "portalUrl": "https://portal.example/job",
        "submittedAt": evidence["submission"]["submittedAt"],
    }


def test_submit_timeout_records_potential_job_before_retry(monkeypatch, tmp_path):
    client = FakeClient(creation_error=TimeoutError("synthetic submit timeout"))
    with pytest.raises(TimeoutError, match="synthetic submit timeout"):
        invoke(monkeypatch, tmp_path, client, action="submit")

    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    submitted_name = client.jobs.created[0][0]
    assert evidence["submission"]["name"] == submitted_name
    assert evidence["submission"]["requestStatus"] == "SUBMITTING"
    assert evidence["recovery"]["potentiallyCreatedJobs"] == [
        {"name": submitted_name, "status": "SUBMISSION_RESULT_UNKNOWN"}
    ]
    assert "before retrying" in evidence["recovery"]["nextAction"]


def test_tenant_id_requires_azure_cli_before_reading_inputs(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "submit_job.py",
            "--action",
            "validate",
            "--config",
            "missing-config.json",
            "--overrides",
            "missing-overrides.json",
            "--sample-dir",
            "missing-sample",
            "--tenant-id",
            "tenant",
        ],
    )
    assert submit_job.main() == 1
    assert "--tenant-id requires --credential azure-cli" in capsys.readouterr().out


def test_azure_cli_credential_receives_tenant():
    credential = submit_job.make_credential(
        {
            "AzureCliCredential": FakeCredential,
            "DefaultAzureCredential": FakeCredential,
        },
        "azure-cli",
        "tenant",
    )
    assert credential.kwargs == {"process_timeout": 120, "tenant_id": "tenant"}


def test_main_passes_azure_cli_tenant_to_credential(monkeypatch, tmp_path):
    FakeCredential.instances.clear()
    client = FakeClient()
    result, _, _ = invoke(
        monkeypatch,
        tmp_path,
        client,
        credential="azure-cli",
        tenant_id="tenant",
    )
    assert result == 0
    assert FakeCredential.instances[-1].kwargs == {
        "process_timeout": 120,
        "tenant_id": "tenant",
    }
    assert FakeCredential.instances[-1].closed is True


def test_default_credential_without_tenant_remains_supported():
    credential = submit_job.make_credential(
        {
            "AzureCliCredential": FakeCredential,
            "DefaultAzureCredential": FakeCredential,
        },
        "default",
        None,
    )
    assert credential.kwargs == {}


def test_cleanup_failure_does_not_mask_primary_error(monkeypatch, tmp_path):
    client = FakeClient(
        validation_error=RuntimeError("primary validation failure"),
        close_error=RuntimeError("synthetic close failure"),
    )
    with pytest.raises(RuntimeError, match="primary validation failure"):
        invoke(monkeypatch, tmp_path, client)

    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    assert client.closed is True
    assert "client.close failed: RuntimeError: synthetic close failure" in evidence[
        "cleanupWarnings"
    ]
    assert FakeCredential.instances[-1].closed is True


def test_job_status_rejects_tenant_with_default_credential(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "job_status.py",
            "--config",
            "missing-config.json",
            "--job-name",
            "job",
            "--tenant-id",
            "tenant",
        ],
    )
    with pytest.raises(ContractError, match="--tenant-id requires --credential azure-cli"):
        job_status.main()


def test_job_status_closes_credential_when_client_construction_fails(monkeypatch, tmp_path):
    config, _, _, _ = write_cloud_inputs(tmp_path)
    credential = FakeCredential()

    def fail_client(**_kwargs):
        raise RuntimeError("synthetic client construction failure")

    monkeypatch.setattr(
        job_status,
        "_sdk_imports",
        lambda: {
            "AIProjectClient": fail_client,
            "AzureCliCredential": FakeCredential,
            "DefaultAzureCredential": lambda: credential,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["job_status.py", "--config", str(config), "--job-name", "job"],
    )
    with pytest.raises(RuntimeError, match="synthetic client construction failure"):
        job_status.main()
    assert credential.closed is True


def test_pinned_sdk_constructs_measured_job_contract(tmp_path):
    pytest.importorskip("azure.ai.projects")
    from importlib import metadata

    from job_contract import build_contract, validate_overrides

    config_path, overrides_path, _, _ = write_cloud_inputs(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    overrides = validate_overrides(json.loads(overrides_path.read_text(encoding="utf-8")))
    contract = build_contract(
        config,
        overrides,
        code_uri="azureai://datasets/test-code/versions/1",
        data_uri="azureai://datasets/test-data/versions/1",
        suffix="sdk",
    )

    assert metadata.version("azure-ai-projects") == "2.3.0a20260525001"
    job = submit_job.sdk_job_from_contract(submit_job._sdk_imports(), config, contract)
    assert job.compute == config["computeId"]
    assert job.inputs["code_dataset"].path == "azureai://datasets/test-code/versions/1"
    assert job.inputs["train_data"].path == "azureai://datasets/test-data/versions/1"