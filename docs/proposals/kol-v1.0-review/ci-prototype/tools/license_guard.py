#!/usr/bin/env python3
"""Read-only license-governance prototype. This tool grants no license rights."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

KOL = "LicenseRef-KOL-v1.0"
SCHEMA = 1
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
LICENSE_RE = re.compile(r"SPDX-License-Identifier:\s*([^\r\n]+)")
COPYRIGHT_RE = re.compile(r"(?:SPDX-FileCopyrightText:\s*|Copyright\s*(?:\(c\)|\u00a9)?\s*)([^\r\n]+)", re.I)
KINDS = {"first-party", "third-party", "legacy", "quarantine", "acc-output", "runtime-output"}
CREDIT_RE = re.compile(r"(?:must|shall|required)[^\n]{0,100}(?:credit|attribut)[^\n]{0,100}(?:acc\b|I-plusplus)|(?:credit|attribut)[^\n]{0,100}(?:acc\b|I-plusplus)[^\n]{0,100}(?:must|shall|required)", re.I)


class GuardError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise GuardError("invalid relative path")
    p = PurePosixPath(value)
    if p.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")) or ":" in value:
        raise GuardError(f"unsafe path: {value!r}")
    return value


def local_file(root: Path, value: str) -> Path:
    value = relative(value)
    current = root
    for part in PurePosixPath(value).parts:
        current = current / part
        if current.is_symlink():
            raise GuardError(f"symlink not allowed: {value}")
    if not current.is_file():
        raise GuardError(f"missing regular file: {value}")
    if current.stat().st_size > MAX_FILE_BYTES:
        raise GuardError(f"file too large for prototype: {value}")
    return current


def read_bytes(root: Path, value: str) -> bytes:
    return local_file(root, value).read_bytes()


def load_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise GuardError(f"invalid JSON file: {path}")
    def no_duplicates(pairs):
        d = {}
        for key, value in pairs:
            if key in d:
                raise GuardError(f"duplicate JSON key: {key}")
            d[key] = value
        return d
    result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    if not isinstance(result, dict):
        raise GuardError("JSON document must be an object")
    return result


def fields(obj: dict, allowed: set[str], required: set[str], context: str):
    if not isinstance(obj, dict):
        raise GuardError(f"{context}: expected object")
    if set(obj) - allowed or required - set(obj):
        raise GuardError(f"{context}: unknown or missing fields: {sorted((set(obj)-allowed)|(required-set(obj)))}")


def spdx(expression: str, known: set[str]) -> None:
    """Validate a deliberately bounded SPDX subset, with explicit ID allowlisting."""
    if not isinstance(expression, str) or not expression.strip():
        raise GuardError("empty SPDX expression")
    tokens = re.findall(r"\(|\)|[A-Za-z0-9.+-]+", expression)
    if "".join(tokens) != re.sub(r"\s", "", expression):
        raise GuardError(f"invalid SPDX syntax: {expression}")
    if len(tokens) > 512:
        raise GuardError("SPDX expression too complex for prototype")
    index = 0
    def term():
        nonlocal index
        if index >= len(tokens):
            raise GuardError(f"incomplete SPDX expression: {expression}")
        token = tokens[index]
        index += 1
        if token == "(":
            expr()
            if index >= len(tokens) or tokens[index] != ")":
                raise GuardError("unbalanced SPDX parentheses")
            index += 1
        elif token not in known or token in {"AND", "OR", "WITH", ")"}:
            raise GuardError(f"unapproved SPDX identifier: {token}")
        if index < len(tokens) and tokens[index] == "WITH":
            raise GuardError("SPDX WITH exceptions need explicit reviewer support; prototype rejects them")
    def expr():
        nonlocal index
        term()
        while index < len(tokens) and tokens[index] in {"AND", "OR"}:
            index += 1
            term()
    expr()
    if index != len(tokens):
        raise GuardError(f"invalid SPDX expression: {expression}")


def policy_load(path: Path) -> dict:
    p = load_json(path)
    allowed = {"schema", "status", "licenses", "scopes", "notices", "protected_files", "distribution", "artifact_payloads", "excluded_paths"}
    fields(p, allowed, allowed - {"excluded_paths"}, "policy")
    if p["schema"] != SCHEMA or p["status"] != "draft-prototype-not-adopted":
        raise GuardError("only the draft prototype schema is supported")
    if not isinstance(p["licenses"], dict) or KOL not in p["licenses"]:
        raise GuardError("KOL local LicenseRef mapping required; this does not mean SPDX registration")
    for identifier, license_path in p["licenses"].items():
        if not re.fullmatch(r"[A-Za-z0-9.+-]+", identifier):
            raise GuardError("invalid license identifier")
        relative(license_path)
    if not isinstance(p["scopes"], list) or not p["scopes"]:
        raise GuardError("explicit source scopes required")
    for s in p["scopes"]:
        fields(s, {"path", "kind", "expected_license", "copyright_holders", "rights_evidence", "license_origin", "bundled_in", "license_files", "notice_files"}, {"path", "kind", "expected_license", "copyright_holders", "rights_evidence"}, "scope")
        relative(s["path"])
        if s["kind"] not in KINDS:
            raise GuardError("unknown scope kind")
        evidence = s["rights_evidence"]
        fields(evidence, {"status", "record"}, {"status", "record"}, "rights evidence")
        if evidence["status"] not in {"fixture-only", "owner-reviewed", "unresolved"}:
            raise GuardError("rights evidence must be fixture-only, owner-reviewed, or unresolved")
        relative(evidence["record"])
        if evidence["status"] == "unresolved" and s["kind"] != "quarantine":
            raise GuardError("unresolved rights must be quarantined; labels and Git history do not establish rights")
        if not isinstance(s["copyright_holders"], list) or any(not isinstance(x, str) or not x for x in s["copyright_holders"]):
            raise GuardError("copyright_holders must be a string list")
        if s["expected_license"] is not None:
            spdx(s["expected_license"], set(p["licenses"]))
        if s["kind"] in {"first-party", "third-party", "runtime-output"} and (not s["expected_license"] or not s["copyright_holders"]):
            raise GuardError("licensed source requires expected license and actual copyright holders")
        if s["kind"] == "third-party" and KOL in re.findall(r"[A-Za-z0-9.+-]+", s["expected_license"] or ""):
            raise GuardError("third-party source cannot be relabeled KOL")
        if s["kind"] in {"third-party", "runtime-output"} and not s.get("license_files"):
            raise GuardError("third-party/runtime material requires its original license documents")
        if s["kind"] == "acc-output" and KOL in re.findall(r"[A-Za-z0-9.+-]+", s["expected_license"] or "") and s.get("license_origin") != "user-choice":
            raise GuardError("KOL on pure acc output requires explicit user-choice evidence")
        for group in ("license_files", "notice_files"):
            for f in s.get(group, []):
                fields(f, {"source", "target"}, {"source", "target"}, group)
                relative(f["source"]); relative(f["target"])
        if not isinstance(s.get("bundled_in", []), list):
            raise GuardError("bundled_in must be a list")
    if not isinstance(p["notices"], list) or not isinstance(p["protected_files"], list):
        raise GuardError("notices and protected_files must be lists")
    for notice in p["notices"]:
        fields(notice, {"path", "required_text"}, {"path", "required_text"}, "notice")
        relative(notice["path"])
        if not isinstance(notice["required_text"], list) or not notice["required_text"] or any(not isinstance(x, str) or not x for x in notice["required_text"]):
            raise GuardError("notice must identify required attribution facts")
    for name in p["protected_files"]:
        relative(name)
    if not isinstance(p["distribution"], dict):
        raise GuardError("distribution must be an object")
    for kind, mappings in p["distribution"].items():
        if not isinstance(mappings, list) or (not mappings and kind != "acc-pure-output"):
            raise GuardError(f"empty or invalid distribution document set: {kind}")
        for f in mappings:
            fields(f, {"source", "target"}, {"source", "target"}, "distribution")
            relative(f["source"]); relative(f["target"])
    if not isinstance(p["artifact_payloads"], dict) or set(p["artifact_payloads"]) != set(p["distribution"]):
        raise GuardError("every distribution requires an explicit artifact payload inventory")
    scopes = {s["path"]: s for s in p["scopes"]}
    for kind, payloads in p["artifact_payloads"].items():
        if not isinstance(payloads, list) or not payloads:
            raise GuardError("empty artifact payload inventory")
        targets = set()
        for payload in payloads:
            fields(payload, {"target", "source", "scopes"}, {"target", "scopes"}, "artifact payload")
            relative(payload["target"])
            if payload["target"] in targets:
                raise GuardError("duplicate artifact payload target")
            targets.add(payload["target"])
            if "source" in payload:
                relative(payload["source"])
            if not isinstance(payload["scopes"], list) or not payload["scopes"]:
                raise GuardError("artifact payload needs explicit rights scopes")
            for name in payload["scopes"]:
                if name not in scopes or scopes[name]["kind"] == "quarantine":
                    raise GuardError("artifact payload has unknown or quarantined rights")
                if kind == "acc-pure-output" and scopes[name]["kind"] != "acc-output":
                    raise GuardError("pure output package cannot silently embed runtime or other covered material")
    if "aceis" in p["distribution"]:
        required = {p["licenses"][KOL]} | {n["path"] for n in p["notices"]}
        if not required.issubset({f["source"] for f in p["distribution"]["aceis"]}):
            raise GuardError("AceIS distribution must carry its KOL document and attribution notices")
    for s in p["scopes"]:
        for kind in s.get("bundled_in", []):
            if kind not in p["distribution"]:
                raise GuardError(f"unknown bundled distribution: {kind}")
    for exclusion in p.get("excluded_paths", []):
        fields(exclusion, {"path", "reason"}, {"path", "reason"}, "exclusion")
        relative(exclusion["path"])
        if not isinstance(exclusion["reason"], str) or not exclusion["reason"].strip():
            raise GuardError("exclusion requires reason")
    for kind, payloads in p["artifact_payloads"].items():
        used_scopes = {name for item in payloads for name in item["scopes"]}
        included = [scope for scope in p["scopes"] if scope["path"] in used_scopes or kind in scope.get("bundled_in", [])]
        document_sources = {f["source"] for f in p["distribution"][kind]}
        for scope in included:
            document_sources.update(f["source"] for f in scope.get("license_files", []))
            document_sources.update(f["source"] for f in scope.get("notice_files", []))
            license_ids = set(re.findall(r"[A-Za-z0-9.+-]+", scope["expected_license"] or "")) & set(p["licenses"])
            for identifier in license_ids:
                if p["licenses"][identifier] not in document_sources:
                    raise GuardError(f"included scope {scope['path']} is missing its {identifier} distribution document")
        for payload in payloads:
            payload_source_scope(p, payload)
    return p


def under(name: str, prefix: str) -> bool:
    return name == prefix or name.startswith(prefix + "/")


def document_paths(p: dict) -> set[str]:
    paths = set(p["licenses"].values()) | set(p["protected_files"]) | {n["path"] for n in p["notices"]}
    for mappings in p["distribution"].values():
        paths.update(f["source"] for f in mappings)
    for scope in p["scopes"]:
        paths.add(scope["rights_evidence"]["record"])
        for group in ("license_files", "notice_files"):
            paths.update(f["source"] for f in scope.get(group, []))
    return paths


def payload_source_scope(p: dict, payload: dict) -> None:
    if "source" not in payload:
        return
    source = payload["source"]
    if ".git" in PurePosixPath(source).parts or source in document_paths(p) or any(under(source, e["path"]) for e in p.get("excluded_paths", [])):
        raise GuardError("payload source must be an inspected source, never metadata, a document, or an exclusion")
    matches = [scope for scope in p["scopes"] if under(source, scope["path"])]
    if len(matches) != 1 or set(payload["scopes"]) != {matches[0]["path"]}:
        raise GuardError("payload source must match its one actual inspected rights scope")


def walk_files(root: Path, *, skip_git=True):
    # Never follow links, including directory links. Exclusions are applied later.
    import os
    for here, dirs, names in os.walk(root, followlinks=False):
        dirs.sort(); names.sort()
        dirs[:] = [d for d in dirs if not (skip_git and d == ".git")]
        for d in dirs:
            p = Path(here) / d
            if p.is_symlink():
                yield p.relative_to(root).as_posix(), p
        for name in names:
            p = Path(here) / name
            yield p.relative_to(root).as_posix(), p


def header_data(data: bytes) -> tuple[list[str], list[str], str]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise GuardError("source must be UTF-8 for header inspection") from e
    # Inspect full file, so a removed header cannot hide behind moving it past a limit.
    licenses = [x.strip().removesuffix("*/").strip() for x in LICENSE_RE.findall(text)]
    copyrights = [x.strip().removesuffix("*/").strip() for x in COPYRIGHT_RE.findall(text)]
    return licenses, copyrights, text


def inspect(root: Path, p: dict) -> tuple[dict, list[dict]]:
    errors = []
    records = {}
    def err(code, path, detail):
        errors.append({"code": code, "path": path, "detail": detail})
    declared_docs = document_paths(p)
    seen_scope = set()
    for name, path in walk_files(root):
        if path.is_symlink():
            err("SYMLINK", name, "symlinks are not checked or followed; materialize a regular file")
            continue
        if any(under(name, e["path"]) for e in p.get("excluded_paths", [])):
            continue
        if name in declared_docs:
            continue
        matches = [s for s in p["scopes"] if under(name, s["path"])]
        if len(matches) != 1:
            err("SCOPE", name, f"expected exactly one explicit rights scope; found {len(matches)}")
            continue
        scope = matches[0]
        seen_scope.add(scope["path"])
        try:
            source_bytes = read_bytes(root, name)
            licenses, copyrights, text = header_data(source_bytes)
            records[name] = {"licenses": licenses, "copyrights": copyrights, "kind": scope["kind"], "content_sha256": digest(source_bytes)}
            if scope["kind"] == "quarantine":
                err("RIGHTS_UNRESOLVED", name, "rights unresolved; exclude from KOL migration and release")
                continue
            expected = scope["expected_license"]
            if licenses != ([] if expected is None else [expected]):
                err("SPDX", name, f"expected {expected!r}; observed {licenses!r}")
            for license_text in licenses:
                spdx(license_text, set(p["licenses"]))
            for holder in scope["copyright_holders"]:
                if not any(holder in line for line in copyrights):
                    err("COPYRIGHT", name, f"missing recorded rights holder: {holder}")
            if scope["kind"] in {"first-party", "third-party", "runtime-output"} and not copyrights:
                err("COPYRIGHT", name, "copyright statement required")
            if scope["kind"] == "acc-output":
                if (KOL in text and not (KOL in re.findall(r"[A-Za-z0-9.+-]+", expected or "") and scope.get("license_origin") == "user-choice")) or CREDIT_RE.search(text):
                    err("ACC_OBLIGATION", name, "unexpected compiler-license or mandatory compiler-credit marker in pure output")
        except (OSError, GuardError) as e:
            err("SOURCE", name, str(e))
    for scope in p["scopes"]:
        if scope["path"] not in seen_scope:
            err("EMPTY_SCOPE", scope["path"], "scope matched no source; stale or misspelled policy")
    docs = set(p["licenses"].values()) | set(p["protected_files"])
    for notice in p["notices"]:
        docs.add(notice["path"])
        try:
            text = read_bytes(root, notice["path"]).decode("utf-8")
            for fact in notice["required_text"]:
                if fact not in text:
                    err("NOTICE", notice["path"], f"missing attribution fact: {fact}")
        except (OSError, UnicodeError, GuardError) as e:
            err("NOTICE", notice["path"], str(e))
    for mappings in p["distribution"].values():
        docs.update(f["source"] for f in mappings)
    for scope in p["scopes"]:
        docs.add(scope["rights_evidence"]["record"])
        for field in ("license_files", "notice_files"):
            docs.update(f["source"] for f in scope.get(field, []))
    hashes = {}
    for name in sorted(docs):
        try:
            data = read_bytes(root, name)
            if not data.strip():
                raise GuardError("document is empty")
            hashes[name] = digest(data)
        except (OSError, GuardError) as e:
            err("DOCUMENT", name, str(e))
    return {"schema": SCHEMA, "policy_sha256": digest(json.dumps(p, sort_keys=True, separators=(",", ":")).encode()), "sources": records, "documents": hashes}, errors


def baseline_compare(current: dict, baseline: dict) -> list[dict]:
    fields(baseline, {"schema", "policy_sha256", "sources", "documents"}, {"schema", "policy_sha256", "sources", "documents"}, "baseline")
    if baseline["schema"] != SCHEMA or not isinstance(baseline["sources"], dict) or not isinstance(baseline["documents"], dict):
        raise GuardError("invalid baseline schema")
    errors = []
    def err(code, path, detail):
        errors.append({"code": code, "path": path, "detail": detail})
    if baseline["policy_sha256"] != current["policy_sha256"]:
        err("BASELINE_POLICY", "policy", "executed policy differs from the policy bound to the trusted baseline")
    for path, old in baseline["sources"].items():
        relative(path)
        fields(old, {"licenses", "copyrights", "kind", "content_sha256"}, {"licenses", "copyrights", "kind", "content_sha256"}, "baseline source")
        if not isinstance(old["licenses"], list) or not isinstance(old["copyrights"], list) or any(not isinstance(x, str) for x in old["licenses"] + old["copyrights"]):
            raise GuardError("invalid baseline license/copyright list")
        now = current["sources"].get(path)
        if now is None:
            err("BASELINE_REMOVAL", path, "baseline file removed or no longer covered; explicit rights review required")
            continue
        if old["kind"] in {"legacy", "third-party"} and old["content_sha256"] != now["content_sha256"]:
            err("BASELINE_PRESERVED_SOURCE", path, "legacy/vendor bytes changed; preserve all original legal prose until explicit review")
        if old["licenses"] != now["licenses"] or old["kind"] != now["kind"]:
            err("BASELINE_LICENSE", path, "license identifier or rights classification changed")
        if not set(old["copyrights"]).issubset(now["copyrights"]):
            err("BASELINE_COPYRIGHT", path, "an existing copyright statement was changed or removed")
    for path, old_hash in baseline["documents"].items():
        relative(path)
        if not isinstance(old_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", old_hash):
            raise GuardError("invalid document digest")
        if current["documents"].get(path) != old_hash:
            err("BASELINE_DOCUMENT", path, "protected license/notice/governance document changed or disappeared")
    return errors


def artifact_files(path: Path) -> dict[str, bytes]:
    result = {}
    total = 0
    def add(name, data):
        nonlocal total
        relative(name)
        if name in result:
            raise GuardError(f"duplicate artifact member: {name}")
        total += len(data)
        if len(data) > MAX_FILE_BYTES or total > MAX_ARTIFACT_BYTES:
            raise GuardError("artifact exceeds prototype size limit")
        result[name] = data
    if path.is_symlink():
        raise GuardError("artifact cannot be a symlink")
    if path.is_dir():
        for name, file in walk_files(path, skip_git=False):
            if file.is_symlink():
                raise GuardError(f"artifact symlink: {name}")
            add(name, read_bytes(path, name))
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                name = info.filename.rstrip("/")
                relative(name)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise GuardError(f"artifact symlink: {name}")
                if info.is_dir():
                    continue
                if info.file_size > MAX_FILE_BYTES or total + info.file_size > MAX_ARTIFACT_BYTES:
                    raise GuardError("artifact exceeds prototype size limit")
                add(name, z.read(info))
    elif tarfile.is_tarfile(path):
        with tarfile.open(path) as t:
            for info in t:
                name = info.name.rstrip("/")
                relative(name)
                if info.isdir():
                    continue
                if not info.isfile():
                    raise GuardError(f"artifact link or special member: {name}")
                if info.size > MAX_FILE_BYTES or total + info.size > MAX_ARTIFACT_BYTES:
                    raise GuardError("artifact exceeds prototype size limit")
                stream = t.extractfile(info)
                if stream is None:
                    raise GuardError(f"unreadable artifact member: {name}")
                add(name, stream.read(MAX_FILE_BYTES + 1))
    else:
        raise GuardError("artifact must be a directory, ZIP or TAR archive")
    if not result:
        raise GuardError("empty artifact")
    return result


def distribution_check(root: Path, p: dict, path: Path, kind: str) -> list[dict]:
    if kind not in p["distribution"]:
        raise GuardError(f"unknown distribution kind: {kind}")
    contents = artifact_files(path)
    mappings = list(p["distribution"][kind])
    used_scopes = {name for payload in p["artifact_payloads"][kind] for name in payload["scopes"]}
    for scope in p["scopes"]:
        if kind in scope.get("bundled_in", []) or scope["path"] in used_scopes:
            mappings.extend(scope.get("license_files", []))
            mappings.extend(scope.get("notice_files", []))
    errors = []
    targets = {}
    for f in mappings:
        source, target = f["source"], f["target"]
        expected = read_bytes(root, source)
        if target in targets and targets[target] != digest(expected):
            raise GuardError(f"conflicting distribution mapping: {target}")
        targets[target] = digest(expected)
        if target not in contents or contents[target] != expected:
            errors.append({"code": "DISTRIBUTION", "path": target, "detail": f"missing or changed license/notice from {source}"})
    allowed = set(targets)
    for payload in p["artifact_payloads"][kind]:
        payload_source_scope(p, payload)
        target = payload["target"]
        if target in allowed:
            raise GuardError(f"payload conflicts with legal document target: {target}")
        allowed.add(target)
        if target not in contents:
            errors.append({"code": "PAYLOAD", "path": target, "detail": "declared distribution payload missing"})
        elif "source" in payload and contents[target] != read_bytes(root, payload["source"]):
            errors.append({"code": "PAYLOAD", "path": target, "detail": "source output differs from declared source file"})
    for name in set(contents) - allowed:
        errors.append({"code": "PAYLOAD_UNDECLARED", "path": name, "detail": "artifact member has no reviewed rights/provenance mapping"})
    if kind == "acc-pure-output":
        payload_by_target = {x["target"]: x for x in p["artifact_payloads"][kind]}
        scopes_by_path = {x["path"]: x for x in p["scopes"]}
        for name, data in contents.items():
            if name in targets:
                # Only a specifically chosen license document can carry its own terms.
                voluntary_license_sources = {
                    p["licenses"][identifier]
                    for scope_path in used_scopes
                    for scope in [scopes_by_path[scope_path]]
                    if scope.get("license_origin") == "user-choice"
                    for identifier in set(re.findall(r"[A-Za-z0-9.+-]+", scope["expected_license"] or "")) & set(p["licenses"])
                }
                matching = [mapping for mapping in mappings if mapping["target"] == name]
                if matching and all(mapping["source"] in voluntary_license_sources for mapping in matching):
                    continue
            text = data.decode("latin-1")  # Scan ASCII obligation markers even in binary payloads.
            declared = payload_by_target.get(name, {})
            selected_kol = bool(declared) and all(
                scopes_by_path[scope].get("license_origin") == "user-choice"
                and KOL in re.findall(r"[A-Za-z0-9.+-]+", scopes_by_path[scope]["expected_license"] or "")
                for scope in declared.get("scopes", []))
            if (KOL in text and not selected_kol) or CREDIT_RE.search(text):
                errors.append({"code": "ACC_OBLIGATION", "path": name, "detail": "unexpected compiler-license or mandatory credit marker in declared pure output package"})
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("inventory", "snapshot", "check"):
        cmd = sub.add_parser(command)
        cmd.add_argument("--root", type=Path, required=True)
        cmd.add_argument("--policy", type=Path, required=True)
        if command == "check":
            cmd.add_argument("--baseline", type=Path, required=True, help="trusted base or external reviewed baseline, never PR candidate")
            cmd.add_argument("--candidate-baseline", required=True, help="repo-relative baseline path, checked against trusted baseline")
            cmd.add_argument("--artifact", type=Path)
            cmd.add_argument("--artifact-kind")
    header = sub.add_parser("header", help="print a header only; never changes an existing file")
    header.add_argument("--holder", required=True, help="actual verified rights holder")
    header.add_argument("--year", required=True)
    header.add_argument("--style", choices=["c", "hash"], default="c")
    args = parser.parse_args(argv)
    try:
        if args.command == "header":
            if "\n" in args.holder or "\r" in args.holder or not args.holder.strip() or not re.fullmatch(r"\d{4}(?:-\d{4})?", args.year):
                raise GuardError("holder must be one nonempty line and year must be YYYY or YYYY-YYYY")
            prefix = "//" if args.style == "c" else "#"
            print(f"{prefix} SPDX-FileCopyrightText: {args.year} {args.holder}\n{prefix} SPDX-License-Identifier: {KOL}")
            return 0
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise GuardError("root must be a directory")
        p = policy_load(args.policy)
        current, errors = inspect(root, p)
        if args.command == "snapshot":
            # A known noncompliant tree must not become the accepted baseline.
            if not errors:
                print(json.dumps(current, indent=2, sort_keys=True))
                return 0
        if args.command == "check":
            baseline = load_json(args.baseline)
            errors.extend(baseline_compare(current, baseline))
            if read_bytes(root, args.candidate_baseline) != args.baseline.read_bytes():
                errors.append({"code": "BASELINE_TAMPER", "path": args.candidate_baseline, "detail": "candidate baseline differs from trusted reviewed baseline"})
            if bool(args.artifact) != bool(args.artifact_kind):
                raise GuardError("artifact and artifact-kind must be specified together")
            if args.artifact:
                errors.extend(distribution_check(root, p, args.artifact, args.artifact_kind))
        report = {"status": "fail" if errors else "pass", "prototype": True, "not_legal_approval": True, "inventory": current, "errors": errors}
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if errors else 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, GuardError, zipfile.BadZipFile, tarfile.TarError) as e:
        print(json.dumps({"status": "error", "prototype": True, "error": str(e)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
