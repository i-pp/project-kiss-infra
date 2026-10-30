"""Internal fixed-command runner; no CLI, namespaces, session creation or GPU imports.

The caller supplies only previously reviewed fixed argv. This module does not
download software, manipulate the coordinator, or interpret model output as code.
Limits are soft observations, not cgroup/OOM guarantees.
"""
from __future__ import annotations

import dataclasses
import glob
import math
import os
from pathlib import Path
import queue
import select
import signal
import subprocess
import threading
import time

GIB = 1 << 30


@dataclasses.dataclass(frozen=True)
class Limits:
    start_ram_bytes: int = 24 * GIB
    min_ram_bytes: int = 16 * GIB
    max_gpu_bytes: int = 58 * GIB
    max_rss_bytes: int = 32 * GIB
    max_swap_growth_bytes: int = 0
    max_disk_growth_bytes: int = 70 * GIB
    log_bytes: int = 2 << 20
    line_bytes: int = 64 << 10


@dataclasses.dataclass(frozen=True)
class Identity:
    pid: int
    starttime: int


def _stat(pid):
    """Read process identity without opening command lines or environment."""
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        tail = raw[raw.rfind(")") + 2:].split()
        return {"pid": int(pid), "state": tail[0], "ppid": int(tail[1]),
                "starttime": int(tail[19]), "rss": max(0, int(tail[21])) * os.sysconf("SC_PAGE_SIZE")}
    except (OSError, ValueError, IndexError):
        return None


def _ancestors():
    seen, p = set(), os.getpid()
    while p > 0 and p not in seen:
        seen.add(p)
        row = _stat(p)
        if row is None:
            break
        p = row["ppid"]
    return seen


class OwnedTree:
    """Track root and observed descendants; never signal a process-group ID.

    Only ancestry observed while the parent identity was live establishes a new
    owned PID. Previously observed descendants retain their starttime after
    reparenting. Extremely short-lived unobserved forks cannot be guaranteed
    discoverable without an external containment mechanism (not added here).
    """
    def __init__(self, pid):
        row = _stat(pid)
        self.known = {pid: row["starttime"]} if row else {}
        self.root = Identity(pid, row["starttime"]) if row else None
        self.forbidden = _ancestors() | {0, 1}
        self.signal_errors = []

    def refresh(self):
        rows = {}
        for name in glob.glob("/proc/[0-9]*/stat"):
            row = _stat(int(name.split("/")[2]))
            if row:
                rows[row["pid"]] = row
        live = {p for p, start in self.known.items()
                if p in rows and rows[p]["starttime"] == start and rows[p]["state"] != "Z"}
        while True:
            new = {p for p, row in rows.items()
                   if p not in self.forbidden and row["ppid"] in live
                   and p not in self.known and row["state"] != "Z"}
            if not new:
                break
            for p in new:
                self.known[p] = rows[p]["starttime"]
            live.update(new)
        return [rows[p] for p in live if p not in self.forbidden]

    def signal(self, sig):
        self.refresh()
        sent = []
        # Descendants before the root; verify starttime immediately before kill.
        rootpid = self.root.pid if self.root else -1
        for p in sorted(self.known, key=lambda n: n == rootpid):
            row = _stat(p)
            if (p in self.forbidden or row is None or row["state"] == "Z"
                    or row["starttime"] != self.known[p]):
                continue
            try:
                # A pidfd closes the stat-check/PID-reuse race. Fail closed if the
                # platform cannot supply it; never fall back to killpg/authority.
                if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
                    self.signal_errors.append("PIDFD_UNAVAILABLE")
                    continue
                fd = os.pidfd_open(p)
                try:
                    check = _stat(p)
                    if check is None or check["starttime"] != self.known[p]:
                        continue
                    signal.pidfd_send_signal(fd, sig)
                finally:
                    os.close(fd)
                sent.append(p)
            except ProcessLookupError:
                pass
            except PermissionError:
                # Report survivor rather than switching authority.
                self.signal_errors.append("SIGNAL_PERMISSION_DENIED")
        return sent


def _directory_bytes(root):
    if root is None:
        return 0
    total = 0
    for here, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not Path(here, d).is_symlink()]
        for name in files:
            p = Path(here, name)
            try:
                if not p.is_symlink():
                    total += p.stat().st_size
            except FileNotFoundError:
                pass
    return total


def system_probe():
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        fields[key] = int(value.split()[0]) * 1024
    vram, gtt, devices = 0, 0, set()
    for item in glob.glob("/sys/class/drm/card[0-9]*/device/mem_info_vram_used"):
        p = Path(item)
        device = str(p.parent.resolve())
        if device in devices:
            continue
        devices.add(device)
        vram += int(p.read_text())
        gtt_file = p.parent / "mem_info_gtt_used"
        if gtt_file.exists():
            gtt += int(gtt_file.read_text())
    return {"mem_available": fields["MemAvailable"],
            "swap_used": fields["SwapTotal"] - fields["SwapFree"],
            "gpu_used": vram if devices else None,
            "gtt_used": gtt if devices else None}


class _Capture:
    def __init__(self, proc, limits):
        self.proc, self.limits = proc, limits
        self.events = queue.Queue(maxsize=256)
        self.abort = threading.Event()
        self.reason = None
        self.total = 0
        self.lock = threading.Lock()
        self.threads = []
        for stream, pipe in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            t = threading.Thread(target=self._read, args=(stream, pipe), daemon=True)
            self.threads.append(t)
            t.start()

    def fail(self, reason):
        with self.lock:
            if self.reason is None:
                self.reason = reason
        self.abort.set()

    def _put(self, event):
        try:
            self.events.put(event, timeout=.05)
        except queue.Full:
            self.fail("OUTPUT_BACKPRESSURE")

    def _read(self, stream, pipe):
        buf = b""
        try:
            while True:
                chunk = os.read(pipe.fileno(), 8192)
                if not chunk:
                    break
                with self.lock:
                    self.total += len(chunk)
                    over = self.total > self.limits.log_bytes
                if over:
                    self.fail("OUTPUT_LIMIT")
                if self.abort.is_set():
                    continue  # Drain without retaining unbounded output.
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if len(line) > self.limits.line_bytes:
                        self.fail("LINE_LIMIT")
                        buf = b""
                        break
                    self._put((stream, line.rstrip(b"\r")))
                if len(buf) > self.limits.line_bytes:
                    self.fail("LINE_LIMIT")
                    buf = b""
            if buf and not self.abort.is_set():
                self._put((stream, buf))
        except (OSError, ValueError):
            pass
        finally:
            self._put((stream, None))


class OwnedProcessRunner:
    def __init__(self, *, limits=None, probe=None, run_dir=None, poll_interval=.5,
                 disk_baseline_bytes=None):
        self.limits = limits or Limits()
        self.probe = probe or system_probe
        self.run_dir = Path(run_dir) if run_dir else None
        self.poll_interval = max(.01, float(poll_interval))
        if disk_baseline_bytes is not None and (type(disk_baseline_bytes) is not int or disk_baseline_bytes < 0):
            raise ValueError("disk baseline must be a non-negative integer")
        self._disk_start = _directory_bytes(self.run_dir) if disk_baseline_bytes is None else disk_baseline_bytes
        self._swap_start = None

    def _sample(self, tree, baseline, disk_start, peaks, sample=None):
        rows = tree.refresh() if tree else []
        sample = dict(self.probe()) if sample is None else dict(sample)
        sample["rss_bytes"] = sum(row["rss"] for row in rows)
        sample["disk_growth_bytes"] = max(0, _directory_bytes(self.run_dir) - disk_start)
        sample["owned_processes"] = len(rows)
        for k, v in sample.items():
            if isinstance(v, (int, float)):
                if k == "mem_available":
                    peaks["min_mem_available"] = min(peaks.get("min_mem_available", v), v)
                else:
                    peaks[k] = max(peaks.get(k, v), v)
        if any(type(sample.get(k)) not in {int, float} or not math.isfinite(sample[k]) or sample[k] < 0
               for k in ("mem_available", "swap_used", "gpu_used")):
            return sample, "RESOURCE_PROBE_UNAVAILABLE"
        if sample["mem_available"] <= self.limits.min_ram_bytes:
            return sample, "RAM_FLOOR"
        if sample["gpu_used"] > self.limits.max_gpu_bytes:
            return sample, "GPU_LIMIT"
        if sample["swap_used"] - baseline["swap_used"] > self.limits.max_swap_growth_bytes:
            return sample, "SWAP_GROWTH"
        if sample["rss_bytes"] > self.limits.max_rss_bytes:
            return sample, "RSS_SOFT_LIMIT"
        if sample["disk_growth_bytes"] > self.limits.max_disk_growth_bytes:
            return sample, "DISK_GROWTH"
        return sample, None

    @staticmethod
    def _send(proc, text, timeout=.25):
        if proc.poll() is not None:
            return False
        try:
            fd, data = proc.stdin.fileno(), text.encode("ascii")
            os.set_blocking(fd, False)
            end, sent = time.monotonic() + timeout, 0
            while sent < len(data):
                if time.monotonic() >= end or proc.poll() is not None:
                    return False
                _, writable, _ = select.select([], [fd], [], min(.02, max(0, end-time.monotonic())))
                if not writable:
                    continue
                try:
                    sent += os.write(fd, data[sent:])
                except BlockingIOError:
                    pass
            return True
        except (OSError, ValueError):
            return False

    def _cleanup(self, proc, tree, engine, timeout, active):
        end = time.monotonic() + max(.1, timeout)
        actions = []
        if engine and proc.poll() is None:
            if active:
                if self._send(proc, "STOP\n"):
                    actions.append("STOP")
            if self._send(proc, "QUIT\n"):
                actions.append("QUIT")
        # All waits are bounded and poll tree identity, not process groups.
        graceful_end = min(end, time.monotonic() + min(20., timeout * .45))
        while time.monotonic() < graceful_end:
            proc.poll()
            if not tree.refresh():
                break
            time.sleep(min(.05, max(0, graceful_end - time.monotonic())))
        if tree.refresh():
            actions.append({"TERM": tree.signal(signal.SIGTERM)})
            term_end = min(end, time.monotonic() + min(5., timeout * .25))
            while time.monotonic() < term_end and tree.refresh():
                proc.poll()
                time.sleep(.02)
        if tree.refresh():
            actions.append({"KILL": tree.signal(signal.SIGKILL)})
        while time.monotonic() < end:
            proc.poll()
            if not tree.refresh():
                break
            time.sleep(.02)
        proc.poll()
        survivors = [Identity(r["pid"], r["starttime"]).__dict__ for r in tree.refresh()]
        unreadable = [p for p in tree.known if p not in tree.forbidden
                      and Path(f"/proc/{p}").exists() and _stat(p) is None]
        unverified_root = proc.poll() is None and tree.root is None
        return {"actions": actions, "survivors": survivors,
                "complete": not survivors and not unreadable and not unverified_root,
                "unreadable_owned_pids": unreadable,
                "unverified_root_pid": proc.pid if unverified_root else None,
                "signal_errors": tree.signal_errors,
                "scope": "observed PID/starttime descendants only; unobserved transient forks not guaranteed"}

    def run(self, argv, cwd, timeout, *, env=None, stop_timeout=45):
        return self._execute(argv, cwd, env, timeout, stop_timeout, None)

    def rawserve(self, argv, cwd, prompt_ids, *, start_timeout=90,
                 generation_timeout=90, stop_timeout=45, max_tokens=128, env=None,
                 required_startup_marker=None):
        if (not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or not 1 <= max_tokens <= 128
                or not isinstance(prompt_ids, (list, tuple)) or not prompt_ids
                or len(prompt_ids) + max_tokens > 8192
                or any(type(x) is not int or x < 0 or x >= (1 << 31) for x in prompt_ids)):
            raise ValueError("Expected non-empty validated token IDs and at most128 output tokens within8192")
        wire = (f"GEN {max_tokens} temperature=0 seed=42 ckpt=0 "
                + ",".join(str(x) for x in prompt_ids) + "\n")
        if len(wire) > self.limits.line_bytes:
            raise ValueError("GEN wire exceeds reviewed line budget")
        spec = {"ids": list(prompt_ids), "max_tokens": max_tokens,
                "start_timeout": float(start_timeout), "generation_timeout": float(generation_timeout),
                "required_startup_marker": required_startup_marker, "wire":wire}
        return self._execute(argv, cwd, env, start_timeout, stop_timeout, spec)

    def _execute(self, argv, cwd, env, timeout, stop_timeout, engine):
        if not isinstance(argv, (tuple, list)) or not argv or any(not isinstance(x, str) or "\x00" in x for x in argv):
            raise ValueError("Internal argv must be a non-empty list of strings")
        started = time.monotonic()
        result = {"status": "BLOCKED", "reason": None, "generation_requests": 0,
                  "token_ids": [], "done": None, "logs": [], "resource_peaks": {},
                  "resource_samples": [], "resource_sample_count": 0,
                  "limits": dataclasses.asdict(self.limits), "limit_mode": "soft observations, no hard cap"}
        def record_sample(sample):
            result["resource_sample_count"] += 1
            result["resource_samples"].append({"elapsed_seconds": time.monotonic()-started, **sample})
            if len(result["resource_samples"]) > 1000:
                result["resource_samples"].pop(0)
        try:
            initial = dict(self.probe())
            if self._swap_start is None:
                self._swap_start = initial.get("swap_used")
            baseline = {**initial, "swap_used":self._swap_start}
            disk_start = self._disk_start
            sample, problem = self._sample(None, baseline, disk_start, result["resource_peaks"], initial)
            record_sample(sample)
        except (KeyboardInterrupt, SystemExit):
            result["status"], result["reason"] = "FAILED", "INTERRUPTED"
            return result
        except Exception as exc:
            result["reason"] = "RESOURCE_PROBE_UNAVAILABLE"
            result["probe_error"] = type(exc).__name__
            return result
        if problem or baseline["mem_available"] < self.limits.start_ram_bytes:
            result["reason"] = problem or "START_RAM_FLOOR"
            return result
        try:
            proc = subprocess.Popen(list(argv), cwd=cwd, env=env,
                                    stdin=subprocess.PIPE if engine else subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=False, close_fds=True)
        except OSError as exc:
            result["reason"], result["spawn_error"] = "SPAWN_FAILED", type(exc).__name__
            return result
        tree, capture = OwnedTree(proc.pid), _Capture(proc, self.limits)
        result["root_identity"] = dataclasses.asdict(tree.root) if tree.root else None
        deadline = time.monotonic() + float(timeout)
        next_probe = 0.
        eof, phase, active = set(), "STARTUP" if engine else "RUN", False
        ready_seen = False
        marker_seen = engine is None or not engine["required_startup_marker"]
        def send_generation():
            nonlocal phase, deadline, active
            result["generation_requests"] = 1
            active = True
            if not self._send(proc, engine["wire"]):
                return "SUBMISSION_UNCERTAIN"
            phase = "GENERATION"
            deadline = time.monotonic() + engine["generation_timeout"]
            return None
        log_size = 0
        reason = None
        try:
            while True:
                now = time.monotonic()
                proc.poll()
                if capture.abort.is_set():
                    reason = capture.reason
                    break
                if now >= next_probe:
                    try:
                        sample, reason = self._sample(tree, baseline, disk_start, result["resource_peaks"])
                        record_sample(sample)
                    except Exception:
                        reason = "RESOURCE_PROBE_UNAVAILABLE"
                    next_probe = now + self.poll_interval
                    if reason:
                        break
                if now >= deadline:
                    reason = "STARTUP_CONTRACT_MISSING" if phase == "STARTUP" and ready_seen and not marker_seen else phase + "_TIMEOUT"
                    break
                try:
                    stream, raw = capture.events.get(timeout=min(.05, max(.001, deadline - now)))
                except queue.Empty:
                    if proc.returncode is not None and len(eof) == 2:
                        reason = ("STARTUP_CONTRACT_MISSING" if engine and ready_seen and not marker_seen else
                                  "MISSING_DONE" if engine and active else "EARLY_EXIT" if engine else None)
                        break
                    continue
                if raw is None:
                    eof.add(stream)
                    continue
                line = raw.decode("utf-8", errors="replace")
                if log_size + len(raw) + 1 <= self.limits.log_bytes and len(result["logs"]) < 8192:
                    result["logs"].append({"stream": stream, "line": line})
                    log_size += len(raw) + 1
                if engine and phase == "STARTUP" and stream == "stderr" and engine["required_startup_marker"]:
                    if engine["required_startup_marker"] in line:
                        marker_seen = True
                        result["startup_marker_confirmed"] = True
                    if ready_seen and marker_seen:
                        reason = send_generation()
                        if reason:
                            break
                if not engine or stream != "stdout":
                    continue
                if phase == "STARTUP":
                    if line.startswith("READY "):
                        if line != "READY 8192 stop":
                            reason = "BAD_READY"
                            break
                        if ready_seen:
                            reason = "DUPLICATE_READY"
                            break
                        ready_seen = True
                        if marker_seen:
                            reason = send_generation()
                            if reason:
                                break
                    elif line.startswith(("T ", "DONE ", "ERR ")):
                        reason = "UNEXPECTED_PROTOCOL_BEFORE_READY"
                        break
                else:
                    if line.startswith("T "):
                        parts = line.split()
                        if len(parts) != 2 or not parts[1].isdecimal():
                            reason = "BAD_TOKEN_RECORD"
                            break
                        result["token_ids"].append(int(parts[1]))
                        if len(result["token_ids"]) > engine["max_tokens"]:
                            reason = "OUTPUT_TOKEN_LIMIT"
                            break
                    elif line.startswith("DONE "):
                        try:
                            parts = line.split()
                            done = {"generated": int(parts[1]), "prompt_tokens": int(parts[2]),
                                    "prompt_ms": float(parts[3]), "decode_ms": float(parts[4]),
                                    "finish": parts[5], "raw": line}
                            if (done["generated"] != len(result["token_ids"])
                                    or done["prompt_tokens"] != len(engine["ids"])
                                    or not math.isfinite(done["prompt_ms"]) or done["prompt_ms"] < 0
                                    or not math.isfinite(done["decode_ms"]) or done["decode_ms"] < 0
                                    or done["finish"] not in {"stop", "length", "cancel", "nonfinite"}):
                                raise ValueError()
                        except (ValueError, IndexError):
                            reason = "BAD_DONE"
                            break
                        result["done"] = done
                        active = False
                        reason = None if done["finish"] in {"stop", "length"} else done["finish"].upper()
                        break
                    elif line.startswith("ERR "):
                        reason = "ENGINE_ERROR"
                        break
                    elif line.startswith("READY "):
                        reason = "DUPLICATE_READY"
                        break
        except (KeyboardInterrupt, SystemExit):
            reason = "INTERRUPTED"
        finally:
            try:
                result["cleanup"] = self._cleanup(proc, tree, bool(engine), stop_timeout, active)
            except (KeyboardInterrupt, SystemExit):
                result["cleanup"] = {"complete":False, "actions":[], "interrupted":True,
                    "survivors":[Identity(r["pid"], r["starttime"]).__dict__ for r in tree.refresh()],
                    "scope":"observed identities; cleanup interrupted; caller must not assume resources recovered"}
            for t in capture.threads:
                t.join(timeout=.15)
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                if pipe:
                    try:
                        pipe.close()
                    except OSError:
                        pass
            result["exit_code"] = proc.poll()
            result["elapsed_seconds"] = time.monotonic() - started
        result["reason"] = reason
        if reason is None and capture.abort.is_set():
            reason = result["reason"] = capture.reason
        if not result["cleanup"]["complete"]:
            result["status"] = "UNKNOWN"
            result["reason"] = reason or "CLEANUP_INCOMPLETE"
        elif engine:
            result["status"] = "COMPLETED" if reason is None and result["done"] and proc.returncode == 0 else (
                "UNKNOWN" if active and result["done"] is None and reason != "ENGINE_ERROR" else "FAILED")
            if result["status"] == "FAILED" and reason is None:
                result["reason"] = "NONZERO_EXIT"
        else:
            result["status"] = "COMPLETED" if reason is None and proc.returncode == 0 else "FAILED"
            if reason is None and proc.returncode != 0:
                result["reason"] = "NONZERO_EXIT"
        return result
