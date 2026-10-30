"""Offline plan validation only. No network, subprocess or backend imports."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = "cyankiwi/Qwen3-Coder-Next-AWQ-4bit"
REV = "c92cabfad08cadb011dc169cabb3e6da621b0719"
SOURCE = "baa9befa381511cd4d56f83980951e5a45fffc6d"
GIB = 1024**3


def required_non_moe():
    names = ["lm_head"]
    for i in range(48):
        attention = ([f"self_attn.{x}_proj" for x in "qkvo"] if i % 4 == 3
                     else ["linear_attn.in_proj_qkvz", "linear_attn.in_proj_ba", "linear_attn.out_proj"])
        other = ["mlp.gate", "mlp.shared_expert.gate_proj", "mlp.shared_expert.up_proj",
                 "mlp.shared_expert.down_proj", "mlp.shared_expert_gate"]
        names.extend(f"model.layers.{i}.{x}" for x in attention + other)
    return set(names)


def validate_config(config):
    q = config["quantization_config"]
    if config["architectures"] != ["Qwen3NextForCausalLM"]:
        raise ValueError("architecture changed")
    if config.get("dtype", config.get("torch_dtype")) != "bfloat16":
        raise ValueError("BF16 non-MoE preservation required")
    if config.get("auto_map"):
        raise ValueError("remote model code is out of scope")
    if q["quant_method"] != "compressed-tensors" or q["format"] != "pack-quantized":
        raise ValueError("wrong loader/format")
    groups = q["config_groups"]
    if set(groups) != {"group_0"}:
        raise ValueError("unexpected mixed quantization")
    g = groups["group_0"]
    w = g["weights"]
    expected = {"num_bits": 4, "group_size": 32, "symmetric": True,
                "type": "int", "strategy": "group", "dynamic": False, "actorder": None}
    if any(w.get(k) != v for k, v in expected.items()):
        raise ValueError("unsupported MoE scheme")
    if g["targets"] != ["Linear"] or g.get("input_activations") is not None:
        raise ValueError("unexpected activation/target")
    if set(q["ignore"]) != required_non_moe() or len(q["ignore"]) != 397:
        raise ValueError("dense INT4 or ignored routed expert would change HIP route")
    return True


def validate_plan(candidate, plan):
    if candidate["repo"] != REPO or candidate["revision"] != REV or candidate["source_commit"] != SOURCE:
        raise ValueError("unreviewed revision")
    names = [f["name"] for f in candidate["required_files"]]
    if len(names) != len(set(names)) or any("/" in x or x.endswith(".py") for x in names):
        raise ValueError("file scope expanded")
    total = sum(f["bytes"] for f in candidate["required_files"])
    weights = sum(f["bytes"] for f in candidate["required_files"] if f["name"].endswith(".safetensors"))
    if total != 48278252061 or weights != 48245164128 or len(names) != 20:
        raise ValueError("incomplete or changed file manifest")
    for row in candidate["required_files"]:
        for field, length in (("sha256",64),("git_blob_sha1",40)):
            if field in row and (len(row[field]) != length or any(x not in "0123456789abcdef" for x in row[field])):
                raise ValueError("invalid upstream hash metadata")
    if plan["execution_allowed"] is not False or plan["generation_count"] != 0:
        raise ValueError("preparation is not runtime authorization")
    args = plan["server_argv"]
    def value(flag):
        return args[args.index(flag) + 1]
    if value("--host") != "0.0.0.0" or plan.get("route_mode") != "owned-internal-ip" or plan.get('host_bind') is not None:
        raise ValueError("listener must use verified owned internal endpoint without host publication")
    if value("--model-path") != "/models/next-int4" or "--trust-remote-code" in args:
        raise ValueError("arbitrary model/remote code prohibited")
    if "--quantization" in args or value("--moe-runner-backend") != "triton":
        raise ValueError("do not override checkpoint format")
    if value("--max-running-requests") != "1" or value("--context-length") != "4096":
        raise ValueError("smoke scope expanded")
    if plan["limits"] != {"startup_seconds":90,"generation_seconds":90,"total_seconds":900,
                          "request_count":1,"max_output_tokens":64,"retry_count":0,
                          "min_mem_available_bytes":24*GIB,"min_mem_available_continue_bytes":16*GIB,
                          "max_gpu_bytes":58*GIB,"container_memory_bytes":32*GIB,"container_memory_swap_bytes":32*GIB}:
        raise ValueError("finite/resource contract changed")
    return {"status":"STATIC_PREPARATION_VALIDATED", "execution_allowed":False,
            "environment":"NOT_RUN", "quality":"UNASSESSED", "generation_count":0,
            "required_bytes":total,"weights_bytes":weights,
            "required_GiB":round(total/GIB,6),"weights_GiB":round(weights/GIB,6)}


def verify_snapshot_metadata(directory, include_weights=False):
    """Offline byte verification. Large weights are read only if explicitly requested."""
    directory = Path(directory)
    candidate = json.loads((ROOT / "candidate.json").read_text())
    for row in candidate["required_files"]:
        if row["name"].endswith(".safetensors") and not include_weights:
            continue
        path = directory / row["name"]
        if path.stat().st_size != row["bytes"]:
            raise ValueError("metadata size mismatch: " + row["name"])
        if row["name"].endswith(".safetensors"):
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024**2), b""):
                    digest.update(block)
            if digest.hexdigest() != row["sha256"]:
                raise ValueError("weight hash mismatch: " + row["name"])
            continue
        content = path.read_bytes()
        if "git_blob_sha1" in row:
            oid = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            if oid != row["git_blob_sha1"]:
                raise ValueError("metadata hash mismatch: " + row["name"])
        if "sha256" in row and hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError("metadata hash mismatch: " + row["name"])
    return validate_config(json.loads((directory / "config.json").read_text()))


if __name__ == "__main__":
    print(json.dumps(validate_plan(json.loads((ROOT/"candidate.json").read_text()),
                                   json.loads((ROOT/"launch-plan.json").read_text())), indent=2))
