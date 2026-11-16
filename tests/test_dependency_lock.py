"""Supply chain: every direct dependency is pinned with hashes, and the workflows pin their actions by commit."""

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
PINNED = re.compile(r"(?m)^([A-Za-z0-9_.-]+)==[\w.]+ \\$")
HASH_LINES = re.compile(r"--hash=sha256:[0-9a-f]{64}")


def package_name(requirement: str) -> str:
    return re.split(r"[<>=!~;\s#]", requirement.strip(), maxsplit=1)[0].lower().replace("_", "-")


def test_every_direct_dependency_is_pinned_in_the_lock_with_hashes() -> None:
    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    pinned = {name.lower().replace("_", "-") for name in PINNED.findall(lock)}
    wanted = {package_name(line) for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
              if line.strip() and not line.startswith("#")}
    assert wanted <= pinned
    assert len(HASH_LINES.findall(lock)) >= len(pinned)


def test_workflow_actions_are_pinned_to_a_commit() -> None:
    for workflow in (ROOT / ".github" / "workflows").glob("*.yml"):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            if "uses:" in line:
                assert re.search(r"@[0-9a-f]{40}\b", line), f"{workflow.name}: {line.strip()}"


def test_setup_installs_the_lock_with_hash_checking() -> None:
    for path in ("dev.ps1", ".github/workflows/ci.yml"):
        assert "--require-hashes -r" in (ROOT / path).read_text(encoding="utf-8")


def test_ci_runs_the_server_tests_with_the_hash_checked_dev_lock() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "src/server/requirements-dev.lock" in workflow
    assert "working-directory: src/server" in workflow
    assert workflow.count("--require-hashes -r") >= 2
