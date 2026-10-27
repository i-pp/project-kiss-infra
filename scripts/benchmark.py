#!/usr/bin/env python3
"""Fixed API workload; sample host GPU counters and container cgroup v2 RAM."""
import datetime
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time
import urllib.request


os.chdir(Path(__file__).resolve().parent.parent)
destination = Path("logs/benchmark.json")
if destination.exists():
    raise SystemExit("logs/benchmark.json exists; preserve it before another run")
base_url = "http://127.0.0.1:8080"
device = Path("/sys/class/drm/renderD128/device")
container_id = subprocess.check_output(
    ["sh", "scripts/compose.sh", "ps", "-q", "llama-server"], text=True
).strip()
if not container_id:
    raise SystemExit("llama-server is not running")
pid = subprocess.check_output(
    ["docker", "inspect", "--format", "{{.State.Pid}}", container_id], text=True
).strip()
cgroup_lines = Path(f"/proc/{pid}/cgroup").read_text().splitlines()
cgroup_path = next(line[3:] for line in cgroup_lines if line.startswith("0::"))
memory_file = Path("/sys/fs/cgroup") / cgroup_path.lstrip("/") / "memory.current"

payload = {
    "model": "kiss-qwen2.5-0.5b",
    "messages": [{"role": "user", "content": (
        "Explain how a local language model processes a prompt and generates text. "
        "Describe tokenization, prompt processing, the KV cache, GPU offloading, "
        "and autoregressive decoding in order. Write at least 300 words."
    )}],
    "temperature": 0,
    "seed": 42,
    "max_tokens": 128,
    "stream": False,
    "cache_prompt": False,
}


def snapshot():
    return {
        "time_monotonic": time.monotonic(),
        "gpu_vram_used_bytes": int((device / "mem_info_vram_used").read_text()),
        "gpu_gtt_used_bytes": int((device / "mem_info_gtt_used").read_text()),
        "container_memory_current_bytes": int(memory_file.read_text()),
    }


def request():
    req = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.load(response)
    elapsed = time.monotonic() - start
    assert result["choices"][0]["message"]["content"].strip(), result
    assert result["timings"]["cache_n"] == 0, result["timings"]
    return {"wall_seconds": elapsed, "response": result}


report = {
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "container_id": container_id,
    "payload": payload,
    "sampling_interval_seconds": 0.1,
    "idle": snapshot(),
}
# Warm up once, then measure the identical uncached workload three times.
report["warmup"] = request()
samples = []
errors = []
stop = threading.Event()


def monitor():
    while not stop.is_set():
        try:
            samples.append(snapshot())
        except Exception as error:
            errors.append(str(error))
            return
        stop.wait(0.1)


worker = threading.Thread(target=monitor)
worker.start()
try:
    report["runs"] = [request() for _ in range(3)]
finally:
    stop.set()
    worker.join()
if errors:
    raise RuntimeError(errors)
assert samples, "No memory samples collected"
report["after"] = snapshot()
report["samples"] = samples
report["summary"] = {
    "prompt_tokens_per_second_median": statistics.median(
        run["response"]["timings"]["prompt_per_second"] for run in report["runs"]
    ),
    "generation_tokens_per_second_median": statistics.median(
        run["response"]["timings"]["predicted_per_second"] for run in report["runs"]
    ),
    "sample_count": len(samples),
    "sampled_max_gpu_vram_used_bytes": max(s["gpu_vram_used_bytes"] for s in samples),
    "sampled_max_gpu_gtt_used_bytes": max(s["gpu_gtt_used_bytes"] for s in samples),
    "sampled_max_container_memory_current_bytes": max(
        s["container_memory_current_bytes"] for s in samples
    ),
}
Path("logs").mkdir(exist_ok=True)
destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report["summary"], indent=2))
print(f"Full responses and memory samples: {destination}")
