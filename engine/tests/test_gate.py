"""Engine unit tests. Fixtures use invented github.com/example/billingapp only."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cqb.bundle import assemble, slot  # noqa: E402
from cqb.collect import collect_files, is_generated, matches_globs, matches_prefix, module_rel  # noqa: E402
from cqb.complexity import classify, measure_func  # noqa: E402
from cqb.config import parse_config  # noqa: E402
from cqb.cover import evaluate_cover  # noqa: E402
from cqb.e2e import evaluate_catalog  # noqa: E402
from cqb.go_source import extract_functions  # noqa: E402
from cqb.hunters import boundary_findings, content_findings, quick_test_findings, unique_findings  # noqa: E402
from cqb.mutation import evaluate_mutation  # noqa: E402


def _if_ladder(name: str, n: int) -> str:
    lines = [
        "package billing",
        "",
        f"func {name}(s string) string {{",
    ]
    for i in range(n):
        lines.append(f'\tif s == "{i}" {{')
        lines.append("\t\treturn s")
        lines.append("\t}")
    lines.append("\treturn s")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


class TestConfig(unittest.TestCase):
    def test_defaults_and_fixture_yaml(self):
        text = (ROOT.parent / "templates" / "cqb.yaml.default").read_text()
        cfg = parse_config(text)
        self.assertEqual(cfg.complexity.cognitive, 30)
        self.assertEqual(cfg.complexity.cyclomatic, 30)
        self.assertEqual(cfg.complexity.nested_if, 5)
        self.assertEqual(cfg.strict_paths, [])
        self.assertEqual(cfg.extra_hunters, [])

    def test_retired_red_allowlist_key_is_ignored(self):
        cfg = parse_config(
            textwrap.dedent(
                """
                red_allowlist:
                  - "internal/billing/**"
                """
            )
        )
        self.assertEqual(cfg.strict_paths, [])

    def test_illegal_keys_ignored(self):
        cfg = parse_config(
            textwrap.dedent(
                """
                yellow_blocks: true
                whole_module: true
                always_on_hook: true
                legacy_absolute_red: true
                complexity:
                  cognitive: 30
                """
            )
        )
        self.assertIn("yellow_blocks", cfg.ignored_keys)
        self.assertIn("whole_module", cfg.ignored_keys)
        self.assertIn("always_on_hook", cfg.ignored_keys)
        self.assertIn("legacy_absolute_red", cfg.ignored_keys)


class TestBundle(unittest.TestCase):
    def test_yellow_does_not_set_has_red(self):
        doc = assemble(
            mode="uncommitted",
            slots={
                "lint": slot("green"),
                "complexity": slot("yellow", reason="over ceiling"),
                "hunters": slot("yellow"),
            },
        )
        self.assertFalse(doc["has_red"])
        self.assertEqual(doc["schema_version"], 1)

    def test_red_sets_has_red(self):
        doc = assemble(mode="uncommitted", slots={"lint": slot("red")})
        self.assertTrue(doc["has_red"])


class TestCollectGitModes(unittest.TestCase):
    def test_uncommitted_and_generated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            env = dict(__import__("os").environ)
            env.update({
                "GIT_AUTHOR_NAME": "cqb",
                "GIT_AUTHOR_EMAIL": "cqb@example.com",
                "GIT_COMMITTER_NAME": "cqb",
                "GIT_COMMITTER_EMAIL": "cqb@example.com",
            })
            (root / "go.mod").write_text("module github.com/example/billingapp\n\ngo 1.22\n")
            pkg = root / "internal" / "billing"
            pkg.mkdir(parents=True)
            (pkg / "normalize.go").write_text("package billing\n", encoding="utf-8")
            (pkg / "query.sql.go").write_text("package billing\n", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True, env=env)
            subprocess.run(
                ["git", "-c", "user.name=cqb", "-c", "user.email=cqb@example.com", "commit", "-m", "init"],
                cwd=root,
                check=True,
                capture_output=True,
                env=env,
            )
            (pkg / "normalize.go").write_text("package billing\n\nfunc X() {}\n", encoding="utf-8")
            (pkg / "extra.go").write_text("package billing\n", encoding="utf-8")
            names = collect_files(root, "uncommitted", None)
            self.assertIn("internal/billing/normalize.go", names)
            self.assertIn("internal/billing/extra.go", names)
            self.assertNotIn("internal/billing/query.sql.go", names)
            subprocess.run(["git", "add", "internal/billing/extra.go"], cwd=root, check=True, capture_output=True, env=env)
            staged = collect_files(root, "staged", None)
            self.assertIn("internal/billing/extra.go", staged)
            listed = collect_files(root, "file-list", ["internal/billing/normalize.go", "internal/billing/query.sql.go"])
            self.assertEqual(listed, ["internal/billing/normalize.go"])

    def test_generated_excluded(self):
        self.assertTrue(is_generated("internal/billing/query.sql.go"))
        self.assertTrue(is_generated("internal/billing/models.go"))
        self.assertTrue(is_generated("docs/docs.go"))
        self.assertFalse(is_generated("internal/billing/normalize.go"))

    def test_prefix_match(self):
        self.assertTrue(matches_prefix("services/billing/a.go", ["services/billing"]))
        self.assertFalse(matches_prefix("services/auth/a.go", ["services/billing"]))

    def test_module_rel_and_directory_include(self):
        rel = "services/billing/internal/application/services/invoice_total.go"
        prefixes = ["services/billing"]
        self.assertEqual(module_rel(rel, prefixes), "internal/application/services/invoice_total.go")
        self.assertTrue(matches_globs(rel, ["internal/application/services/*invoice*"], prefixes=prefixes))
        self.assertTrue(matches_globs(rel, ["internal/"], prefixes=prefixes))
        self.assertFalse(matches_globs("services/auth/foo.go", ["internal/"], prefixes=prefixes))


class TestComplexity(unittest.TestCase):
    def test_new_func_31_is_yellow_not_red(self):
        src = _if_ladder("NormalizeInvoiceRef", 31)
        fn = extract_functions(src)[0]
        cog, _, _ = measure_func(fn)
        self.assertGreaterEqual(cog, 31)
        rows = classify(
            file="internal/billing/normalize.go",
            current_src=src,
            head_src=None,
            added_lines=set(),
            ceilings={"cognitive": 30, "cyclomatic": 30, "nested_if": 5, "delta": 5},
        )
        self.assertEqual(rows[0].kind, "new")
        self.assertTrue(rows[0].yellow)

    def test_legacy_delta_plus_one_not_red(self):
        old = _if_ladder("NormalizeInvoiceRef", 2)
        new = _if_ladder("NormalizeInvoiceRef", 3)
        rows = classify(
            file="internal/billing/normalize.go",
            current_src=new,
            head_src=old,
            added_lines=set(),
            ceilings={"cognitive": 30, "cyclomatic": 30, "nested_if": 5, "delta": 5},
        )
        self.assertEqual(rows[0].kind, "delta")
        self.assertEqual(rows[0].delta_cognitive, 1)
        self.assertFalse(rows[0].yellow)  # not even yellow at delta ceiling 5; never red


class TestHunters(unittest.TestCase):
    def test_quick_test_missing_yellow_outside_allowlist(self):
        src = "package billing\nfunc NormalizeX(s string) string { return s }\n"
        hits = quick_test_findings(
            rel="internal/billing/normalize.go",
            src=src,
            test_src=None,
            testable_include=["internal/"],
            testable_exclude=["internal/interface/"],
            allowlist=[],
            new_func_names=["NormalizeX"],
        )
        self.assertTrue(hits)
        self.assertEqual(hits[0].color, "yellow")

    def test_quick_test_missing_red_on_allowlist(self):
        src = "package billing\nfunc NormalizeX(s string) string { return s }\n"
        hits = quick_test_findings(
            rel="internal/billing/normalize.go",
            src=src,
            test_src="package billing\n",
            testable_include=["internal/"],
            testable_exclude=[],
            allowlist=["internal/billing/**"],
            new_func_names=["NormalizeX"],
        )
        self.assertEqual(hits[0].color, "red")

    def test_fatal_x_outside_allowlist_is_yellow(self):
        src = textwrap.dedent(
            """
            package billing

            import "testing"

            func TestNormalizeX(t *testing.T) {
            	t.Fatal("x")
            }
            """
        )
        hits = content_findings(rel="internal/billing/normalize_test.go", test_src=src, allowlist=[])
        kinds = {h.hunter for h in hits}
        self.assertIn("blind_assert", kinds)
        self.assertTrue(all(h.color == "yellow" for h in hits if h.hunter == "blind_assert"))

    def test_blind_assert_deduped(self):
        src = textwrap.dedent(
            """
            package billing

            import "testing"

            func TestTotal(t *testing.T) {
            	t.Fatal("short")
            }
            """
        )
        a = content_findings(rel="internal/billing/total_test.go", test_src=src, allowlist=[])
        b = content_findings(rel="internal/billing/total_test.go", test_src=src, allowlist=[])
        merged = unique_findings(a + b)
        blinds = [h for h in merged if h.hunter == "blind_assert"]
        self.assertEqual(len(blinds), 1)

    def test_test_name_volume_is_not_missing_boundary(self):
        src = textwrap.dedent(
            """
            package billing

            import "testing"

            func TestTotal_volume(t *testing.T) {}
            """
        )
        hits = content_findings(rel="internal/billing/total_test.go", test_src=src, allowlist=[])
        self.assertFalse(any(h.hunter == "missing_boundary" for h in hits))

    def test_new_numeric_comparison_without_test_literal(self):
        prod = "package billing\n\nfunc Total(n int) int {\n\tif n > 10 {\n\t\treturn n\n\t}\n\treturn 0\n}\n"
        hits = boundary_findings(
            rel="internal/billing/total.go",
            src=prod,
            test_src="package billing\nfunc TestTotal_volume() {}\n",
            added_lines={4},
            allowlist=[],
        )
        self.assertTrue(any(h.hunter == "missing_boundary" for h in hits))


class TestE2E(unittest.TestCase):
    def test_fake_suite_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            suite = root / "internal" / "e2e" / "invoices"
            suite.mkdir(parents=True)
            (suite / "globs.txt").write_text("internal/billing/**\n", encoding="utf-8")
            (root / "internal" / "billing").mkdir(parents=True)
            (root / "internal" / "billing" / "normalize.go").write_text("package billing\n", encoding="utf-8")
            hit = evaluate_catalog(root, "internal/e2e", ["internal/billing/normalize.go"])
            self.assertEqual(hit.implied, ["invoices"])
            miss = evaluate_catalog(root, "internal/e2e", ["internal/geo/city.go"])
            self.assertEqual(miss.color, "skip")
            orphan = root / "internal" / "e2e" / "orphans"
            orphan.mkdir()
            broken = evaluate_catalog(root, "internal/e2e", ["internal/billing/normalize.go"])
            self.assertEqual(broken.color, "red")
            self.assertTrue(any("globs.txt" in e for e in broken.catalog_errors))


class TestCover(unittest.TestCase):
    def test_empty_strict_paths_is_yellow_not_skip(self):
        r = evaluate_cover(
            strict_paths=[],
            diff_files=["internal/billing/normalize.go"],
            coverprofile="mode: set\n",
            baseline_path=None,
            rewrite_baseline=False,
            io_floor=80,
            io_files=set(),
            invoked_pure=set(),
        )
        self.assertEqual(r.color, "yellow")
        self.assertNotEqual(r.color, "skip")
        self.assertNotEqual(r.color, "red")

    def test_no_production_go_skips(self):
        r = evaluate_cover(
            strict_paths=[],
            diff_files=["internal/billing/normalize_test.go"],
            coverprofile="mode: set\n",
            baseline_path=None,
            rewrite_baseline=False,
            io_floor=80,
            io_files=set(),
            invoked_pure=set(),
        )
        self.assertEqual(r.color, "skip")

    def test_refuses_rewrite_flag(self):
        with self.assertRaises(AssertionError):
            evaluate_cover(
                strict_paths=["internal/billing/**"],
                diff_files=["internal/billing/normalize.go"],
                coverprofile=None,
                baseline_path=None,
                rewrite_baseline=True,
                io_floor=80,
                io_files=set(),
                invoked_pure=set(),
            )

    def test_missing_profile_on_strict_path_is_red(self):
        r = evaluate_cover(
            strict_paths=["internal/billing/**"],
            diff_files=["internal/billing/normalize.go"],
            coverprofile=None,
            baseline_path=None,
            rewrite_baseline=False,
            io_floor=80,
            io_files=set(),
            invoked_pure=set(),
        )
        self.assertNotEqual(r.color, "yellow")
        self.assertEqual(r.color, "red")


class TestMutation(unittest.TestCase):
    def test_fixture_json_survivors_yellow(self):
        raw = json.dumps(
            {
                "mutants": [
                    {
                        "status": "LIVED",
                        "file": "internal/billing/normalize.go",
                        "line": 4,
                        "type": "conditionals/negate",
                    }
                ]
            }
        )
        r = evaluate_mutation(tool_present=True, report_path=None, report_json=raw, should_run=True)
        self.assertEqual(r.color, "yellow")
        self.assertEqual(r.survivors[0]["line"], 4)

    def test_missing_tool_unavailable_never_green(self):
        r = evaluate_mutation(tool_present=False, report_path=None, report_json=None, should_run=True)
        self.assertEqual(r.color, "unavailable")
        self.assertNotEqual(r.color, "green")


def _run_orch(root: Path, mode: str, files: str) -> tuple[int, dict]:
    cmd = [
        sys.executable,
        str(ROOT / "orchestrator.py"),
        "--root",
        str(root),
        "--mode",
        mode,
        "--files",
        files,
        "--output",
        str(root / ".quality" / "last.json"),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    doc = json.loads((root / ".quality" / "last.json").read_text())
    return p.returncode, doc


class TestOrchestratorSkipAndYellow(unittest.TestCase):
    def test_prefix_skip_synthetic_file_list(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cqb.yaml").write_text(
                'prefix: "services/billing"\nstrict_paths: []\n', encoding="utf-8"
            )
            (root / "services" / "auth").mkdir(parents=True)
            (root / "services" / "auth" / "x.go").write_text("package auth\n", encoding="utf-8")
            code, doc = _run_orch(root, "file-list", "services/auth/x.go")
            self.assertEqual(code, 0)
            self.assertTrue(doc["skipped"])
            self.assertFalse(doc["has_red"])

    def test_yellow_blocks_key_does_not_fail_git(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cqb.yaml").write_text(
                textwrap.dedent(
                    """
                    prefix: ""
                    yellow_blocks: true
                    complexity:
                      cognitive: 30
                      cyclomatic: 30
                      nested_if: 5
                      delta: 5
                    strict_paths: []
                    testable:
                      include: ["internal/"]
                      exclude: []
                    """
                ),
                encoding="utf-8",
            )
            (root / "go.mod").write_text("module github.com/example/billingapp\n\ngo 1.22\n")
            pkg = root / "internal" / "billing"
            pkg.mkdir(parents=True)
            (pkg / "normalize.go").write_text(_if_ladder("NormalizeInvoiceRef", 31), encoding="utf-8")
            code, doc = _run_orch(root, "file-list", "internal/billing/normalize.go")
            self.assertEqual(code, 0, msg=json.dumps(doc, indent=2))
            self.assertFalse(doc["has_red"])
            self.assertEqual(doc["slots"]["complexity"]["color"], "yellow")
            self.assertIn("yellow_blocks", doc["ignored_keys"])

    def test_empty_strict_paths_cover_runs_yellow(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cqb.yaml").write_text(
                textwrap.dedent(
                    """
                    prefix: ""
                    strict_paths: []
                    testable:
                      include: ["internal/"]
                      exclude: []
                    """
                ),
                encoding="utf-8",
            )
            (root / "go.mod").write_text("module github.com/example/billingapp\n\ngo 1.22\n")
            pkg = root / "internal" / "billing"
            pkg.mkdir(parents=True)
            (pkg / "normalize.go").write_text(
                "package billing\n\nfunc NormalizeX(s string) string { return s }\n",
                encoding="utf-8",
            )
            code, doc = _run_orch(root, "file-list", "internal/billing/normalize.go")
            self.assertEqual(code, 0, msg=json.dumps(doc, indent=2))
            self.assertNotEqual(doc["slots"]["cover"]["color"], "skip")
            self.assertNotEqual(doc["slots"]["cover"]["color"], "red")
            self.assertEqual(doc["slots"]["cover"]["color"], "yellow")


if __name__ == "__main__":
    unittest.main()
