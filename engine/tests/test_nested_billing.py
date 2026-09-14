"""Nested-module fixtures (invented services/billing under a git root)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cqb.e2e import evaluate_catalog, evaluate_e2e  # noqa: E402
from test_gate import _run_orch  # noqa: E402

PREFIXES = ["services/billing"]
INVOICE = "services/billing/internal/application/services/invoice_total.go"
SQL = "services/billing/internal/db/queries/faturas_queries.sql"


def _yaml() -> str:
    return textwrap.dedent(
        """
        prefix: "services/billing"
        red_allowlist:
          - "internal/application/services/*invoice*"
        testable:
          include:
            - "internal/"
          exclude: []
        e2e:
          catalog_root: "internal/e2e"
        cover:
          io_floor: 80
          baseline_path: ".cqb/cover-baseline.json"
        """
    )


def _write_nested(root: Path, *, e2e_body: str | None = None) -> None:
    app = root / "services" / "billing" / "internal" / "application" / "services"
    app.mkdir(parents=True)
    (app / "invoice_total.go").write_text(
        "package services\n\nfunc InvoiceTotal(n int) int { return n }\n",
        encoding="utf-8",
    )
    sql = root / "services" / "billing" / "internal" / "db" / "queries"
    sql.mkdir(parents=True)
    (sql / "faturas_queries.sql").write_text("-- invoice query\n", encoding="utf-8")
    suite = root / "services" / "billing" / "internal" / "e2e" / "invoices"
    suite.mkdir(parents=True)
    (suite / "globs.txt").write_text(
        "internal/application/services/*invoice*\n"
        "internal/db/queries/faturas_queries.sql\n",
        encoding="utf-8",
    )
    if e2e_body is not None:
        (suite / "flow_test.go").write_text(e2e_body, encoding="utf-8")
    (root / "go.mod").write_text("module github.com/example/billingapp\n\ngo 1.22\n", encoding="utf-8")
    (root / "cqb.yaml").write_text(_yaml(), encoding="utf-8")


E2E_PASS = textwrap.dedent(
    """
    //go:build e2e

    package invoices

    import "testing"

    func TestInvoiceFlow(t *testing.T) {}
    """
)

E2E_FAIL = textwrap.dedent(
    """
    //go:build e2e

    package invoices

    import "testing"

    func TestInvoiceFlow(t *testing.T) { t.Fatal("boom") }
    """
)


def _path_without_docker(bindir: Path) -> str:
    bindir.mkdir(parents=True, exist_ok=True)
    for name in ("go", "gofmt", "git"):
        found = shutil.which(name)
        if not found:
            continue
        dest = bindir / name
        if not dest.exists():
            os.symlink(found, dest)
    return str(bindir)


class TestNestedBilling(unittest.TestCase):
    def test_literal_sql_under_prefix_does_not_break_catalog(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root)
            hit = evaluate_catalog(
                root,
                "internal/e2e",
                [INVOICE],
                prefixes=PREFIXES,
            )
            self.assertNotEqual(hit.color, "red", msg=hit.reason)
            self.assertEqual(hit.implied, ["invoices"])

    def test_nested_catalog_when_root_catalog_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root)
            self.assertFalse((root / "internal" / "e2e").exists())
            hit = evaluate_catalog(root, "internal/e2e", [INVOICE], prefixes=PREFIXES)
            self.assertEqual(hit.implied, ["invoices"])

    def test_implied_e2e_pass_is_green(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root, e2e_body=E2E_PASS)
            hit = evaluate_e2e(root, "internal/e2e", [INVOICE], PREFIXES, True)
            self.assertEqual(hit.color, "green", msg=hit.reason)
            self.assertEqual(hit.implied, ["invoices"])

    def test_implied_e2e_fail_is_red(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root, e2e_body=E2E_FAIL)
            hit = evaluate_e2e(root, "internal/e2e", [INVOICE], PREFIXES, True)
            self.assertEqual(hit.color, "red", msg=hit.reason)

    def test_docker_missing_unavailable(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root, e2e_body=E2E_PASS)
            hit = evaluate_e2e(root, "internal/e2e", [INVOICE], PREFIXES, False)
            self.assertEqual(hit.color, "unavailable")
            self.assertNotEqual(hit.color, "green")

    def test_orchestrator_nested_glob_cover_hunters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root, e2e_body=E2E_PASS)
            baseline = root / ".cqb" / "cover-baseline.json"
            baseline.parent.mkdir(parents=True)
            before = json.dumps({INVOICE: 99.0})
            baseline.write_text(before, encoding="utf-8")
            test_rel = INVOICE[:-3] + "_test.go"
            (root / test_rel).write_text(
                textwrap.dedent(
                    """
                    package services

                    import "testing"

                    func TestInvoiceTotal(t *testing.T) {
                    	t.Fatal("short")
                    }
                    """
                ),
                encoding="utf-8",
            )
            code, doc = _run_orch(root, "file-list", f"{INVOICE},{test_rel}")
            self.assertTrue(doc["has_red"], msg=json.dumps(doc, indent=2))
            findings = doc["slots"]["hunters"].get("findings") or []
            files = {f.get("file") for f in findings}
            self.assertTrue(any(str(p).startswith("services/billing/") for p in files | {INVOICE}))
            blinds = [f for f in findings if f.get("hunter") == "blind_assert"]
            self.assertEqual(len(blinds), 1, msg=json.dumps(blinds, indent=2))
            self.assertEqual(doc["slots"]["cover"]["color"], "red")
            self.assertEqual(baseline.read_text(encoding="utf-8"), before)
            self.assertNotEqual(doc["slots"]["cover"]["color"], "yellow")
            self.assertEqual(code, 1)
            e2e = doc["slots"]["e2e"]
            self.assertNotEqual(e2e["color"], "red")  # catalog ok; may be unavailable without docker

    def test_push_without_docker_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_nested(root, e2e_body=E2E_PASS)
            env_git = dict(os.environ)
            env_git.update(
                {
                    "GIT_AUTHOR_NAME": "cqb",
                    "GIT_AUTHOR_EMAIL": "cqb@example.com",
                    "GIT_COMMITTER_NAME": "cqb",
                    "GIT_COMMITTER_EMAIL": "cqb@example.com",
                }
            )
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, env=env_git)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=cqb",
                    "-c",
                    "user.email=cqb@example.com",
                    "commit",
                    "-m",
                    "init",
                ],
                cwd=root,
                check=True,
                capture_output=True,
                env=env_git,
            )
            (root / INVOICE).write_text(
                "package services\n\nfunc InvoiceTotal(n int) int { return n + 1 }\n",
                encoding="utf-8",
            )
            (root / "cqb.yaml").write_text(
                textwrap.dedent(
                    """
                    prefix: "services/billing"
                    red_allowlist: []
                    testable:
                      include: ["internal/"]
                      exclude: []
                    e2e:
                      catalog_root: "internal/e2e"
                    """
                ),
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PATH"] = _path_without_docker(root / "fakebin")
            env["CGO_ENABLED"] = "0"
            cmd = [
                sys.executable,
                str(ROOT / "orchestrator.py"),
                "--root",
                str(root),
                "--mode",
                "push",
                "--output",
                str(root / ".quality" / "last.json"),
            ]
            p = subprocess.run(cmd, capture_output=True, text=True, env=env)
            doc = json.loads((root / ".quality" / "last.json").read_text())
            self.assertEqual(doc["slots"]["e2e"]["color"], "unavailable", msg=json.dumps(doc, indent=2))
            self.assertFalse(doc["has_red"], msg=json.dumps(doc, indent=2))
            self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
