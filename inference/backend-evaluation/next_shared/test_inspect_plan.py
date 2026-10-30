import copy
import json
import unittest
from inspect_plan import ROOT, required_non_moe, validate_config, validate_plan


def observed_config_shape():
    # Reconstructed from selected fixed public config, not an original-byte fixture.
    return {"architectures":["Qwen3NextForCausalLM"], "dtype":"bfloat16",
            "quantization_config":{"quant_method":"compressed-tensors","format":"pack-quantized",
              "ignore":sorted(required_non_moe()),"config_groups":{"group_0":{
                "targets":["Linear"],"input_activations":None,"weights":{
                  "num_bits":4,"group_size":32,"symmetric":True,"type":"int",
                  "strategy":"group","dynamic":False,"actorder":None}}}}}


class OfflinePlanTests(unittest.TestCase):
    def setUp(self):
        self.c = json.loads((ROOT / "candidate.json").read_text())
        self.p = json.loads((ROOT / "launch-plan.json").read_text())

    def test_exact_selected_manifest_and_no_execution(self):
        r = validate_plan(self.c, self.p)
        self.assertEqual(r["required_bytes"],48278252061)
        self.assertFalse(r["execution_allowed"])
        self.assertEqual(r["environment"],"NOT_RUN")

    def test_missing_shard_and_new_revision_rejected(self):
        self.c["required_files"].pop()
        with self.assertRaises(ValueError): validate_plan(self.c,self.p)
        self.setUp(); self.c["revision"] = "main"
        with self.assertRaises(ValueError): validate_plan(self.c,self.p)

    def test_all_non_moe_preserved_and_no_ignored_experts(self):
        cfg = observed_config_shape()
        self.assertTrue(validate_config(cfg))
        self.assertEqual(len(required_non_moe()),397)
        cfg["quantization_config"]["ignore"].remove("model.layers.3.self_attn.q_proj")
        with self.assertRaises(ValueError): validate_config(cfg)
        cfg = observed_config_shape()
        cfg["quantization_config"]["ignore"].append("model.layers.0.mlp.experts.0")
        with self.assertRaises(ValueError): validate_config(cfg)

    def test_wrong_packing_or_activation_rejected(self):
        cfg = observed_config_shape()
        cfg["quantization_config"]["quant_method"] = "awq"
        with self.assertRaises(ValueError): validate_config(cfg)
        cfg = observed_config_shape()
        cfg["quantization_config"]["config_groups"]["group_0"]["weights"]["symmetric"] = False
        with self.assertRaises(ValueError): validate_config(cfg)

    def test_remote_code_and_arbitrary_address_rejected(self):
        cfg = observed_config_shape(); cfg["auto_map"]={"AutoModel":"remote.Custom"}
        with self.assertRaises(ValueError): validate_config(cfg)
        self.p["host_bind"]="0.0.0.0:30000"
        with self.assertRaises(ValueError): validate_plan(self.c,self.p)

    def test_execution_or_retry_expansion_rejected(self):
        self.p["execution_allowed"]=True
        with self.assertRaises(ValueError): validate_plan(self.c,self.p)
        self.setUp(); self.p["limits"]["retry_count"]=1
        with self.assertRaises(ValueError): validate_plan(self.c,self.p)


if __name__ == "__main__": unittest.main()
