# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

"""Verify bounded hardware-probe evidence. Never execute trace contents."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def verify(path: Path) -> dict:
    if path.stat().st_size > 10_000_000:
        raise ValueError("oversized trace")
    lines = path.read_text().splitlines()
    # -yy ties each ioctl to the physical accel device, not an arbitrary fd.
    submissions = sum(bool(re.search(r"ioctl\(\d+</dev/accel/accel0(?:<char \d+:\d+>)?>, DRM_IOCTL_AMDXDNA_EXEC_CMD,.*\) = 0$", line)) for line in lines)
    waits = sum(bool(re.search(r"ioctl\(\d+</dev/accel/accel0(?:<char \d+:\d+>)?>, DRM_IOCTL_SYNCOBJ_TIMELINE_WAIT,.*\) = 0$", line)) for line in lines)
    if not submissions or not waits:
        raise ValueError("no successful NPU command submission/completion wait")
    return {"hardware_execution_verified": True, "successful_exec_commands": submissions,
            "successful_completion_waits": waits, "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.trace), indent=2))
