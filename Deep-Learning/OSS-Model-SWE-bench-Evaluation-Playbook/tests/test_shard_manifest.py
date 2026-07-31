import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "shard_instance_manifest.py"


class ShardManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_manifest(self, name: str, instance_ids: list[str]) -> Path:
        path = self.root / name
        with path.open("w", newline="") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=["instance_id", "group"], delimiter="\t"
            )
            writer.writeheader()
            writer.writerows(
                {"instance_id": instance_id, "group": "test"}
                for instance_id in instance_ids
            )
        return path

    def run_sharder(self, manifest: Path, output: Path, expect_success: bool = True):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--manifest",
                str(manifest),
                "--shards",
                "2",
                "--output-dir",
                str(output),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if expect_success and result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return result

    def read_ids(self, path: Path) -> list[str]:
        with path.open(newline="") as stream:
            return [row["instance_id"] for row in csv.DictReader(stream, delimiter="\t")]

    def test_balanced_disjoint_shards_preserve_union(self) -> None:
        manifest = self.write_manifest("manifest.tsv", ["f", "a", "e", "b", "d", "c"])
        output = self.root / "output"
        self.run_sharder(manifest, output)
        first = self.read_ids(output / "shard-000.tsv")
        second = self.read_ids(output / "shard-001.tsv")
        self.assertEqual(first, ["a", "c", "e"])
        self.assertEqual(second, ["b", "d", "f"])
        self.assertFalse(set(first) & set(second))
        self.assertEqual(set(first) | set(second), set("abcdef"))
        summary = json.loads((output / "sharding-summary.json").read_text())
        self.assertEqual([shard["count"] for shard in summary["shards"]], [3, 3])

    def test_input_order_does_not_change_shards(self) -> None:
        first = self.write_manifest("first.tsv", ["a", "b", "c", "d"])
        second = self.write_manifest("second.tsv", ["d", "b", "a", "c"])
        first_output = self.root / "first-output"
        second_output = self.root / "second-output"
        self.run_sharder(first, first_output)
        self.run_sharder(second, second_output)
        for index in range(2):
            self.assertEqual(
                self.read_ids(first_output / f"shard-{index:03d}.tsv"),
                self.read_ids(second_output / f"shard-{index:03d}.tsv"),
            )

    def test_duplicate_instance_ids_fail_closed(self) -> None:
        manifest = self.write_manifest("duplicate.tsv", ["a", "a", "b"])
        result = self.run_sharder(manifest, self.root / "duplicate-output", False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate instance IDs", result.stderr)


if __name__ == "__main__":
    unittest.main()