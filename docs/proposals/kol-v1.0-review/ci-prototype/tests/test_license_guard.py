"""Synthetic fixtures only. No real code is relicensed by these tests."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

TOOL = Path(__file__).resolve().parents[1] / "tools/license_guard.py"
spec = importlib.util.spec_from_file_location("guard", TOOL)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "candidate"
        self.root.mkdir()
        self.write("LICENSES/LicenseRef-KOL-v1.0.txt", "FIXTURE ONLY, NOT A LICENSE: KOL v1.0 draft placeholder\n")
        self.write("LICENSES/MIT.txt", "FIXTURE ONLY: MIT placeholder, not a real grant\n")
        self.write("NOTICE", "This distribution includes AceIS, developed by I-plusplus and the AceIS contributors.\n")
        self.write("third_party/widget/NOTICE", "Synthetic Widget contributors\n")
        self.write("rights/fixture.md", "Synthetic test files, not actual product files or ownership evidence.\n")
        self.write("src/new.c", self.source())
        self.write("third_party/widget/widget.c", self.source("MIT", "Synthetic Widget contributors"))
        self.write("legacy/old.c", "/* Copyright 1999 Legacy Fixture */\nint old(void) {return 0;}\n")
        self.write("output/user.c", "// SPDX-License-Identifier: MIT\n// SPDX-FileCopyrightText: 2026 Output User\nint user(void) {return 0;}\n")
        self.p = {
            "schema": 1, "status": "draft-prototype-not-adopted",
            "licenses": {guard.KOL: "LICENSES/LicenseRef-KOL-v1.0.txt", "MIT": "LICENSES/MIT.txt"},
            "scopes": [
                self.scope("src", "first-party", guard.KOL, ["Actual Fixture Holder"]),
                self.scope("third_party/widget", "third-party", "MIT", ["Synthetic Widget contributors"],
                           bundled_in=["aceis"], license_files=[{"source": "LICENSES/MIT.txt", "target": "licenses/widget-MIT.txt"}],
                           notice_files=[{"source": "third_party/widget/NOTICE", "target": "notices/widget-NOTICE"}]),
                self.scope("legacy", "legacy", None, ["Legacy Fixture"]),
                self.scope("output", "acc-output", "MIT", ["Output User"], license_origin="user-choice")],
            "notices": [{"path": "NOTICE", "required_text": ["AceIS", "I-plusplus", "AceIS contributors"]}],
            "protected_files": ["policy.json"],
            "excluded_paths": [{"path": "baseline.json", "reason": "Baseline self-comparison is performed by check against the trusted copy."}],
            "artifact_payloads": {
                "aceis": [{"target": "aceis.bin", "scopes": ["src", "third_party/widget"]}],
                "acc-pure-output": [{"target": "main.c", "source": "output/user.c", "scopes": ["output"]}]},
            "distribution": {
                "aceis": [{"source": "LICENSES/LicenseRef-KOL-v1.0.txt", "target": "LICENSE-KOL-v1.0"}, {"source": "NOTICE", "target": "NOTICE"}],
                "acc-pure-output": [{"source": "LICENSES/MIT.txt", "target": "USER-LICENSE"}]}}
        self.save_policy()
        current, errors = guard.inspect(self.root, self.p)
        self.assertEqual(errors, [])
        self.baseline = current
        self.trusted = Path(self.tmp.name) / "trusted-baseline.json"
        self.trusted.write_text(json.dumps(current, sort_keys=True))
        self.write("baseline.json", self.trusted.read_text())
        self.artifact = Path(self.tmp.name) / "artifact"
        self.artifact.mkdir()
        for mapping in self.p["distribution"]["aceis"] + self.p["scopes"][1]["license_files"] + self.p["scopes"][1]["notice_files"]:
            target = self.artifact / mapping["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((self.root / mapping["source"]).read_bytes())
        (self.artifact / "aceis.bin").write_bytes(b"\x00synthetic binary")

    def source(self, license=guard.KOL, holder="Actual Fixture Holder"):
        return f"// SPDX-FileCopyrightText: 2026 {holder}\n// SPDX-License-Identifier: {license}\nint fixture(void) {{return 0;}}\n"

    def scope(self, path, kind, license, holders, **kw):
        return dict(path=path, kind=kind, expected_license=license, copyright_holders=holders,
                    rights_evidence={"status": "fixture-only", "record": "rights/fixture.md"}, **kw)

    def write(self, path, text):
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def save_policy(self):
        self.write("policy.json", json.dumps(self.p, indent=2))

    def errors(self):
        current, errors = guard.inspect(self.root, self.p)
        errors += guard.baseline_compare(current, self.baseline)
        return {x["code"] for x in errors}

    def cli(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = guard.main(list(args))
        return code, out.getvalue()

    def check(self, *extra):
        return self.cli("check", "--root", str(self.root), "--policy", str(self.root / "policy.json"),
                        "--baseline", str(self.trusted), "--candidate-baseline", "baseline.json", *extra)

    def test_clean_check(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertTrue(json.loads(out)["not_legal_approval"])

    def test_inventory_does_not_write(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        code, out = self.cli("inventory", "--root", str(self.root), "--policy", str(self.root / "policy.json"))
        self.assertEqual(code, 0, out)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_new_file_in_known_rights_scope(self):
        self.write("src/another.c", self.source())
        self.assertEqual(self.errors(), set())

    def test_unknown_new_file_fails(self):
        self.write("unknown.c", self.source())
        self.assertIn("SCOPE", self.errors())

    def test_missing_spdx_fails(self):
        self.write("src/new.c", "// SPDX-FileCopyrightText: 2026 Actual Fixture Holder\nint x;\n")
        self.assertIn("SPDX", self.errors())

    def test_unapproved_identifier_fails(self):
        self.write("src/new.c", self.source("KOL-v1.0"))
        self.assertIn("SOURCE", self.errors())

    def test_duplicate_identifiers_fail(self):
        self.write("src/new.c", self.source() + "// SPDX-License-Identifier: MIT\n")
        self.assertIn("SPDX", self.errors())

    def test_missing_holder_fails(self):
        self.write("src/new.c", self.source(holder="Not The Holder"))
        self.assertIn("COPYRIGHT", self.errors())

    def test_copyright_added_is_allowed(self):
        self.write("src/new.c", self.source() + "// SPDX-FileCopyrightText: 2026 New Contributor\n")
        self.assertEqual(self.errors(), set())

    def test_contributor_removed_fails(self):
        old = self.baseline["sources"]["src/new.c"]
        old["copyrights"].append("2025 Existing Contributor")
        self.assertIn("BASELINE_COPYRIGHT", self.errors())

    def test_legacy_no_header_is_preserved(self):
        self.assertEqual(self.errors(), set())

    def test_legacy_relabel_fails(self):
        self.write("legacy/old.c", self.source())
        self.assertIn("BASELINE_LICENSE", self.errors())

    def test_legacy_copyright_change_fails(self):
        self.write("legacy/old.c", "/* Copyright 1999 Other Holder */\nint old;\n")
        self.assertIn("BASELINE_COPYRIGHT", self.errors())

    def test_file_removal_requires_review(self):
        (self.root / "legacy/old.c").unlink()
        self.assertIn("BASELINE_REMOVAL", self.errors())

    def test_notice_fact_missing_fails(self):
        self.write("NOTICE", "AceIS I-plusplus\n")
        self.assertIn("NOTICE", self.errors())

    def test_license_text_changed_fails(self):
        self.write("LICENSES/LicenseRef-KOL-v1.0.txt", "Changed\n")
        self.assertIn("BASELINE_DOCUMENT", self.errors())

    def test_empty_legal_document_fails(self):
        self.write("LICENSES/MIT.txt", "\n")
        self.assertIn("DOCUMENT", self.errors())

    def test_rights_record_changed_fails(self):
        self.write("rights/fixture.md", "Changed evidence\n")
        self.assertIn("BASELINE_DOCUMENT", self.errors())

    def test_thirdparty_relabel_fails(self):
        self.write("third_party/widget/widget.c", self.source())
        self.assertIn("BASELINE_LICENSE", self.errors())

    def test_policy_disallows_thirdparty_kol(self):
        self.p["scopes"][1]["expected_license"] = guard.KOL
        self.save_policy()
        with self.assertRaises(guard.GuardError):
            guard.policy_load(self.root / "policy.json")

    def test_quarantine_fails_closed(self):
        self.p["scopes"][0]["kind"] = "quarantine"
        self.p["scopes"][0]["rights_evidence"]["status"] = "unresolved"
        self.assertIn("RIGHTS_UNRESOLVED", self.errors())

    def test_unknown_rights_cannot_pass_by_label(self):
        self.p["scopes"][0]["rights_evidence"]["status"] = "unresolved"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_overlapping_scopes_fail(self):
        self.p["scopes"].append(self.scope("src/new.c", "first-party", guard.KOL, ["Actual Fixture Holder"]))
        self.assertIn("SCOPE", self.errors())

    def test_stale_scope_fails(self):
        self.p["scopes"].append(self.scope("absent", "legacy", None, []))
        self.assertIn("EMPTY_SCOPE", self.errors())

    def test_symlink_source_fails(self):
        (self.root / "src/link.c").symlink_to(self.root / "src/new.c")
        self.assertIn("SYMLINK", self.errors())

    def test_symlink_directory_fails(self):
        (self.root / "src/linked").symlink_to(self.root / "output", target_is_directory=True)
        self.assertIn("SYMLINK", self.errors())

    def test_policy_unknown_key_fails(self):
        self.p["silent_bypass"] = True
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_policy_traversal_fails(self):
        self.p["licenses"][guard.KOL] = "../secret"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_baseline_tamper_fails(self):
        self.write("baseline.json", "{}")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("BASELINE_TAMPER", {x["code"] for x in json.loads(out)["errors"]})

    def test_policy_bytes_changed_fails(self):
        self.write("policy.json", (self.root / "policy.json").read_text() + "\n")
        self.assertIn("BASELINE_DOCUMENT", self.errors())

    def test_bad_tree_cannot_snapshot(self):
        self.write("src/new.c", "no header\n")
        code, out = self.cli("snapshot", "--root", str(self.root), "--policy", str(self.root / "policy.json"))
        self.assertEqual(code, 1, out)
        self.assertEqual(json.loads(out)["status"], "fail")

    def test_valid_snapshot(self):
        code, out = self.cli("snapshot", "--root", str(self.root), "--policy", str(self.root / "policy.json"))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(out), self.baseline)

    def test_distribution_directory_pass(self):
        self.assertEqual(guard.distribution_check(self.root, self.p, self.artifact, "aceis"), [])

    def test_missing_distribution_notice_fails(self):
        (self.artifact / "NOTICE").unlink()
        self.assertTrue(guard.distribution_check(self.root, self.p, self.artifact, "aceis"))

    def test_changed_distribution_license_fails(self):
        (self.artifact / "LICENSE-KOL-v1.0").write_text("wrong text")
        self.assertTrue(guard.distribution_check(self.root, self.p, self.artifact, "aceis"))

    def test_thirdparty_license_auto_included(self):
        (self.artifact / "licenses/widget-MIT.txt").unlink()
        errors = guard.distribution_check(self.root, self.p, self.artifact, "aceis")
        self.assertIn("licenses/widget-MIT.txt", {x["path"] for x in errors})

    def test_thirdparty_notice_auto_included(self):
        (self.artifact / "notices/widget-NOTICE").unlink()
        self.assertTrue(guard.distribution_check(self.root, self.p, self.artifact, "aceis"))

    def test_zip_distribution_pass(self):
        archive = Path(self.tmp.name) / "artifact.zip"
        with zipfile.ZipFile(archive, "w") as z:
            for file in self.artifact.rglob("*"):
                if file.is_file():
                    z.write(file, file.relative_to(self.artifact).as_posix())
        self.assertEqual(guard.distribution_check(self.root, self.p, archive, "aceis"), [])

    def test_tar_distribution_pass(self):
        archive = Path(self.tmp.name) / "artifact.tar.gz"
        with tarfile.open(archive, "w:gz") as t:
            for file in self.artifact.rglob("*"):
                if file.is_file():
                    t.add(file, arcname=file.relative_to(self.artifact).as_posix())
        self.assertEqual(guard.distribution_check(self.root, self.p, archive, "aceis"), [])

    def test_zip_traversal_rejected_without_extracting(self):
        archive = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("../escape", "evil")
        with self.assertRaises(guard.GuardError):
            guard.artifact_files(archive)
        self.assertFalse((Path(self.tmp.name) / "escape").exists())

    def test_zip_duplicate_rejected(self):
        import warnings
        archive = Path(self.tmp.name) / "bad.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("NOTICE", "first")
                z.writestr("NOTICE", "second")
        with self.assertRaises(guard.GuardError):
            guard.artifact_files(archive)

    def test_zip_symlink_rejected(self):
        archive = Path(self.tmp.name) / "bad.zip"
        with zipfile.ZipFile(archive, "w") as z:
            info = zipfile.ZipInfo("link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            z.writestr(info, "elsewhere")
        with self.assertRaises(guard.GuardError):
            guard.artifact_files(archive)

    def test_tar_link_rejected(self):
        archive = Path(self.tmp.name) / "bad.tar"
        with tarfile.open(archive, "w") as t:
            info = tarfile.TarInfo("link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            t.addfile(info)
        with self.assertRaises(guard.GuardError):
            guard.artifact_files(archive)

    def test_empty_artifact_rejected(self):
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        with self.assertRaises(guard.GuardError):
            guard.artifact_files(empty)

    def test_artifact_without_kind_fails(self):
        self.assertEqual(self.check("--artifact", str(self.artifact))[0], 2)

    def test_pure_acc_output_has_no_compiler_credit_requirement(self):
        self.assertEqual(self.errors(), set())
        artifact = Path(self.tmp.name) / "output-package"
        artifact.mkdir()
        (artifact / "USER-LICENSE").write_bytes((self.root / "LICENSES/MIT.txt").read_bytes())
        (artifact / "main.c").write_bytes((self.root / "output/user.c").read_bytes())
        self.assertEqual(guard.distribution_check(self.root, self.p, artifact, "acc-pure-output"), [])

    def test_acc_injected_license_fails(self):
        self.write("output/user.c", self.source())
        self.assertIn("ACC_OBLIGATION", self.errors())

    def test_acc_injected_mandatory_credit_fails(self):
        self.write("output/user.c", (self.root / "output/user.c").read_text() + "// You must credit acc and I-plusplus.\n")
        self.assertIn("ACC_OBLIGATION", self.errors())

    def test_user_selected_kol_output_not_automatic(self):
        self.p["scopes"][3]["expected_license"] = guard.KOL
        self.p["scopes"][3]["license_origin"] = "compiler-default"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_runtime_output_is_not_blanket_exempt(self):
        scope = self.p["scopes"][3]
        scope["kind"] = "runtime-output"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)
        scope["license_files"] = [{"source": "LICENSES/MIT.txt", "target": "runtime-license.txt"}]
        scope["bundled_in"] = ["aceis"]
        del self.p["distribution"]["acc-pure-output"]
        del self.p["artifact_payloads"]["acc-pure-output"]
        self.save_policy()
        guard.policy_load(self.root / "policy.json")
        self.assertIn("runtime-license.txt", {x["path"] for x in guard.distribution_check(self.root, self.p, self.artifact, "aceis")})

    def test_undeclared_artifact_member_fails(self):
        (self.artifact / "unexpected-runtime.bin").write_bytes(b"runtime")
        errors = guard.distribution_check(self.root, self.p, self.artifact, "aceis")
        self.assertIn("PAYLOAD_UNDECLARED", {x["code"] for x in errors})

    def test_missing_payload_fails(self):
        (self.artifact / "aceis.bin").unlink()
        self.assertIn("PAYLOAD", {x["code"] for x in guard.distribution_check(self.root, self.p, self.artifact, "aceis")})

    def test_runtime_cannot_be_classified_as_pure_output(self):
        self.p["artifact_payloads"]["acc-pure-output"][0]["scopes"].append("third_party/widget")
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_payload_rights_automatically_require_notices(self):
        self.p["scopes"][1]["bundled_in"] = []
        (self.artifact / "licenses/widget-MIT.txt").unlink()
        self.assertIn("licenses/widget-MIT.txt", {x["path"] for x in guard.distribution_check(self.root, self.p, self.artifact, "aceis")})

    def test_legacy_license_prose_cannot_disappear(self):
        self.write("legacy/old.c", "/* Copyright 1999 Legacy Fixture */\n/* Permission only for noncommercial purposes. Retain this notice. */\nint old;\n")
        before, errors = guard.inspect(self.root, self.p)
        self.assertEqual(errors, [])
        self.write("legacy/old.c", "/* Copyright 1999 Legacy Fixture */\nint old;\n")
        after, _ = guard.inspect(self.root, self.p)
        self.assertIn("BASELINE_PRESERVED_SOURCE", {x["code"] for x in guard.baseline_compare(after, before)})

    def test_alternate_policy_is_bound_to_baseline(self):
        alternate = copy.deepcopy(self.p)
        alternate["excluded_paths"].append({"path": "src/unlicensed.jsx", "reason": "attempted bypass"})
        external = Path(self.tmp.name) / "alternate.json"
        external.write_text(json.dumps(alternate))
        self.write("src/unlicensed.jsx", "unlicensed();")
        code, out = self.cli("check", "--root", str(self.root), "--policy", str(external), "--baseline", str(self.trusted), "--candidate-baseline", "baseline.json")
        self.assertEqual(code, 1, out)
        self.assertIn("BASELINE_POLICY", {x["code"] for x in json.loads(out)["errors"]})

    def test_unknown_extension_is_checked(self):
        self.write("src/unlicensed.jsx", "unlicensed();")
        self.assertIn("SPDX", self.errors())

    def test_unclassified_file_without_extension_fails(self):
        self.write("extensionless", "unlicensed();")
        self.assertIn("SCOPE", self.errors())

    def test_voluntary_user_kol_output_package_allowed(self):
        scope = self.p["scopes"][3]
        scope["expected_license"] = guard.KOL
        scope["license_origin"] = "user-choice"
        self.write("output/user.c", self.source(holder="Output User"))
        self.p["distribution"]["acc-pure-output"] = [{"source": self.p["licenses"][guard.KOL], "target": "USER-LICENSE"}]
        artifact = Path(self.tmp.name) / "voluntary-kol"
        artifact.mkdir()
        (artifact / "USER-LICENSE").write_bytes((self.root / self.p["licenses"][guard.KOL]).read_bytes())
        (artifact / "main.c").write_bytes((self.root / "output/user.c").read_bytes())
        self.save_policy()
        guard.policy_load(self.root / "policy.json")
        self.assertEqual(guard.distribution_check(self.root, self.p, artifact, "acc-pure-output"), [])

    def test_pure_output_with_no_user_license_has_no_license_requirement(self):
        self.p["distribution"]["acc-pure-output"] = []
        scope = self.p["scopes"][3]
        scope["expected_license"] = None
        scope["copyright_holders"] = []
        self.write("output/user.c", "int user;\n")
        self.save_policy()
        guard.policy_load(self.root / "policy.json")
        artifact = Path(self.tmp.name) / "unlicensed-output"
        artifact.mkdir()
        (artifact / "main.c").write_bytes((self.root / "output/user.c").read_bytes())
        self.assertEqual(guard.distribution_check(self.root, self.p, artifact, "acc-pure-output"), [])

    def test_artifact_git_directory_not_silently_ignored(self):
        (self.artifact / ".git").mkdir()
        (self.artifact / ".git/config").write_text("not for distribution")
        self.assertIn("PAYLOAD_UNDECLARED", {x["code"] for x in guard.distribution_check(self.root, self.p, self.artifact, "aceis")})

    def test_acc_binary_obligation_markers_are_scanned(self):
        self.p["artifact_payloads"]["acc-pure-output"] = [{"target": "binary.o", "scopes": ["output"]}]
        artifact = Path(self.tmp.name) / "binary-output"
        artifact.mkdir()
        (artifact / "USER-LICENSE").write_bytes((self.root / "LICENSES/MIT.txt").read_bytes())
        (artifact / "binary.o").write_bytes(b"\xff\x00" + guard.KOL.encode())
        self.assertIn("ACC_OBLIGATION", {x["code"] for x in guard.distribution_check(self.root, self.p, artifact, "acc-pure-output")})

    def test_payload_cannot_read_excluded_source(self):
        self.p["excluded_paths"].append({"path": "excluded", "reason": "Synthetic exclusion"})
        self.write("excluded/generated.c", self.source("MIT"))
        self.p["artifact_payloads"]["acc-pure-output"][0]["source"] = "excluded/generated.c"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_payload_cannot_read_legal_document_as_source(self):
        self.p["artifact_payloads"]["acc-pure-output"][0]["source"] = "LICENSES/MIT.txt"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_payload_scope_must_match_actual_source(self):
        self.p["artifact_payloads"]["acc-pure-output"][0]["source"] = "third_party/widget/widget.c"
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_selected_output_license_cannot_be_omitted(self):
        self.p["distribution"]["acc-pure-output"] = []
        self.save_policy()
        self.assertEqual(self.check()[0], 2)

    def test_pure_output_extra_document_cannot_impose_compiler_credit(self):
        self.write("extra.txt", "You must credit acc and I-plusplus.\n")
        self.p["distribution"]["acc-pure-output"].append({"source": "extra.txt", "target": "EXTRA"})
        self.save_policy()
        guard.policy_load(self.root / "policy.json")
        artifact = Path(self.tmp.name) / "extra-output"
        artifact.mkdir()
        for mapping in self.p["distribution"]["acc-pure-output"]:
            (artifact / mapping["target"]).write_bytes((self.root / mapping["source"]).read_bytes())
        (artifact / "main.c").write_bytes((self.root / "output/user.c").read_bytes())
        self.assertIn("ACC_OBLIGATION", {x["code"] for x in guard.distribution_check(self.root, self.p, artifact, "acc-pure-output")})

    def test_header_prints_actual_holder_only(self):
        code, out = self.cli("header", "--holder", "Actual Author", "--year", "2026")
        self.assertEqual(code, 0)
        self.assertIn("2026 Actual Author", out)
        self.assertNotIn("I-plusplus", out)
        self.assertIn(guard.KOL, out)

    def test_header_newline_injection_rejected(self):
        self.assertEqual(self.cli("header", "--holder", "Author\nInjected", "--year", "2026")[0], 2)

    def test_header_year_validation(self):
        self.assertEqual(self.cli("header", "--holder", "Author", "--year", "twenty")[0], 2)

    def test_duplicate_json_keys_rejected(self):
        self.write("policy.json", '{"schema":1,"schema":1}')
        self.assertEqual(self.check()[0], 2)

    def test_spdx_compound_syntax(self):
        guard.spdx("(MIT OR LicenseRef-KOL-v1.0) AND MIT", set(self.p["licenses"]))
        for invalid in ("MIT OR", "(MIT", "MIT MIT", "MIT;rm", "MIT WITH Unknown", "NONE"):
            with self.subTest(invalid=invalid), self.assertRaises(guard.GuardError):
                guard.spdx(invalid, set(self.p["licenses"]))

    def test_malformed_baseline_fails(self):
        self.trusted.write_text('{"schema":1,"sources":{"x":{"licenses":null,"copyrights":[],"kind":"legacy"}},"documents":{}}')
        self.assertEqual(self.check()[0], 2)

    def test_subprocess_cli_works_without_dependencies(self):
        p = subprocess.run([sys.executable, str(TOOL), "header", "--holder", "Verified Author", "--year", "2026", "--style", "hash"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.startswith("# SPDX-FileCopyrightText:"))


if __name__ == "__main__":
    unittest.main()
