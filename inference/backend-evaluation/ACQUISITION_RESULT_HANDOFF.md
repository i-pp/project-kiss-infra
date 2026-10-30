# Acquisition verified; no repeated download

Strata extracted bundle passed independent publisher signature and all279 file checks. Source and llama.cpp LICENSE texts were read and are MIT. The engine bundle has no LICENSE/NOTICE/COPYING files: its four small UTF-8 text files are BUILD.json, SYSTEM-LIBS.txt, engine-component.json and a tuning table. These are metadata, dependency names, a signed inventory and numeric tuning values; none supplies third-party notice text. Do not mark absent notices as read. The draft review record remains NOT_READY with third_party_notices_reviewed_by_operator=false and empty inventory; no runtime record was registered and no engine command has been issued. Missing publisher notices need resolution/documented review before completing the record.

Next all20 host receipt hashes match the fixed manifest and current files have matching sizes. The host receipt records completed SHA verification; a second44.96GiB rehash was not performed. Both acquisition targets now exist, so acquisition scripts must not be repeated. Current acquisition-only operator record keeps runtime flags false/null.

The existing vLLM CPU-only check is ready for a normal human host terminal, without changing groups/sudo or image pull:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/host_trial/inspect_vllm_host.py --inspect-human
```

This checks the exact existing B1 image, then standard-library distribution metadata in a brief network-none, nonroot, CPU-only container. It does not stop30B or import GPU packages. Permission denied or uncertain outcome must not be retried via another privilege path.
