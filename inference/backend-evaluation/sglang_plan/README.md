# SGLang: 読み取り確認・未実行の準備データ

対象はEVO-X3/gfx1151と既存3種類のGGUF。現構成のまま実機検証へ進める組合せはない。
モデルの能力FAILではなく、環境・形式の前提が未充足。生成/起動/導入/DLは0。

公式の[量子化表](https://docs.sglang.io/docs/advanced_features/quantization)はGGUFのAMD対応をNoとし、
[v0.5.22のGGUF実装](https://github.com/sgl-project/sglang/blob/v0.5.22/python/sglang/srt/layers/quantization/gguf.py)
もHIP経路の未対応を示す。手元のQ4_K_M、GSQ-RCO Q2_0、MXFP4 GGUFをそのまま使う試験は実施しない。

[AMD/gfx1151文書](https://docs.sglang.io/docs/hardware-platforms/amd_gpu)には専用image/Triton/AITER=0の経路がある。
[固定版Dockerfile](https://github.com/sgl-project/sglang/blob/v0.5.22/docker/rocm-gfx1151.Dockerfile)は
ROCm7.2.4/PyTorch2.9.1を基礎にgfx1151向けkernel gateをpatchする専用buildで、既存のInstinct imageとは別。
その推奨例にあるseccomp変更やhost IPCは採用・実行していない。

Coder Nextの[公式recipe](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3-Coder-Next)は存在するが、
これだけでRDNA上のGDN/MoEと選択量子化が動くとは判断しない。
Flashの[recipe](https://docs.sglang.io/cookbook/autoregressive/Qwen/Qwen3.8-Flash-Next)は0.5.22以上。
NVIDIA向けNVFP4例は126GiBのcheckpointを扱い、表のfile-backed offloadも含むため、128GB級UMAでの適合は別の検証が必要。
gpt-ossの[recipe](https://docs.sglang.io/cookbook/autoregressive/OpenAI/GPT-OSS)も、
AMD MXFP4経路のCDNA3/4要件をgfx1151の実証に置き換えられない。

`sglang-readiness.json`は主担当の有限runner向け判断データと、前提充足後にだけ使える未実行launch案。
実checkpointの新規DL容量は未確定。BF16の160GB/234GBはパラメータ数からの論理下限に近い概算で、
実配布物の確定サイズではない。巨大DLやkernel移植を自動開始しない。

ローカルの`.safetensors`検索では既存B1の1.5B BF16だけが見つかった。
この小モデルの存在は対象3モデルのcheckpoint互換性や能力の証拠ではない。
既存llama.cppの3モデル稼働・原本証拠・サービスには変更していない。

`sglang_prepare.py`は純粋なオフライン前提gate。固定profile/重み形式/承認済み実行経路/
kernel証拠/immutable runtime digest/資源見積りを検証し、全条件が揃っても
READY_FOR_MANUAL_REVIEWまででexecution_allowed=falseのまま。コマンド実行・モデルimport・HTTPを持たない。
対応7試験が成功。GGUFが環境存在だけで可行判定になること、CDNA向けMXFP4がRDNAへ流れること、
GPU経路やメモリ見積りが未確認のままlaunch案へ進むことを防ぐ。

```bash
python3 -B -m unittest -v test_sglang_prepare
python3 -B sglang_prepare.py
```
