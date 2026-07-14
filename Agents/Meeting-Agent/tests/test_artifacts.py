import json
import zipfile
from pathlib import Path

from PIL import Image, ImageStat

from meeting_agent.analyzers import OfflineContractAnalyzer
from meeting_agent.artifacts import _atomic_generate, generate_artifacts
from meeting_agent.session import load_jsonl

ROOT = Path(__file__).resolve().parents[1]


def test_generates_nonblank_mind_map_and_valid_pptx(tmp_path: Path) -> None:
    analysis = OfflineContractAnalyzer().analyze(
        load_jsonl(ROOT / "examples" / "product-planning.jsonl")
    )
    artifacts = generate_artifacts(analysis, tmp_path)

    image = Image.open(artifacts["mind_map_png"])
    assert image.size == (1280, 720)
    assert all(variance > 100 for variance in ImageStat.Stat(image).var)

    assert zipfile.is_zipfile(artifacts["presentation"])
    with zipfile.ZipFile(artifacts["presentation"]) as archive:
        assert "ppt/presentation.xml" in archive.namelist()

    graph = json.loads(artifacts["mind_map_json"].read_text(encoding="utf-8"))
    assert graph["label"] == analysis.title
    assert artifacts["mind_map_svg"].read_text(encoding="utf-8").startswith("<svg")


def test_atomic_generation_preserves_existing_file_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "artifact.bin"
    target.write_bytes(b"accepted")

    def fail_after_partial_write(temporary: Path) -> None:
        temporary.write_bytes(b"partial")
        raise RuntimeError("generation failed")

    try:
        _atomic_generate(target, fail_after_partial_write)
    except RuntimeError as error:
        assert str(error) == "generation failed"
    else:
        raise AssertionError("expected generation failure")

    assert target.read_bytes() == b"accepted"
    assert list(tmp_path.glob("*.tmp")) == []