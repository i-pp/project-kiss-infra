# SGLang imageのsource差分: 旧基準との差を説明

保存済みreceiptを読み取り、固定image `rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230` のidentityが一致していることと、実4ファイルのサイズ・SHA256を取得した。今回の実Docker/再container/再検査/GPU/推論は0回。旧manifestや現用設定は変更していない。

## 結論

実package版のsuffix `gebfbd3ea3` は[公式commit API](https://api.github.com/repos/sgl-project/sglang/commits/ebfbd3ea3)で `ebfbd3ea35acf6e9facbe74e627d37c3542e5fc1`（2026-10-29 14:09:45 UTC）へ解決できる。**公式そのrevisionの選択4ファイルは、image内の実4ファイルとサイズ・SHA256がすべて完全一致した。** 旧基準 `baa9befa381511cd4d56f83980951e5a45fffc6d` との不一致は、新しい公開sourceで説明できる。破損や改変を断定する根拠はない。tag名だけで旧commitと同一と見なすこともできない。

この照合は選択4ファイルの同等性だけ。全commit/tree一致、image全体のprovenance、全native extension/JIT、GPU動作、モデル品質は未証明。helper/environの補助確認は公式公開sourceのみで、image内helperファイルのhashは未確認と明示する。

## 実測metadata（既存receipt由来）

| 項目 | 値 |
|---|---|
| SGLang | 0.5.23.dev1202+gebfbd3ea3 |
| torch | 2.9.1+rocm7.2.4.lw.git39497456 |
| Triton | 3.7.0+amd.rocm7.2.0.git89002410 |
| compressed-tensors | 0.15.0 |
| transformers | 5.19.0 |
| safetensors | 0.8.0 |
| amd-aiter | 0.0.0（commitや利用可否の証明ではない） |
| image Size | 50,912,606,399 bytes |

base imageの公開historyで見たTriton3.5.1と、実package metadataの3.7.0を混同しない。torch/ROCmとTritonの版文字列の違いだけでは互換/非互換を判定できない。実際のGPU/JITは未実施。

## 4本の差分と今回のNext候補への影響

| 対象 | 旧bytes→実bytes | 限定した影響判定 |
|---|---:|---|
| CT dispatch | 58,497→62,187 | 主な追加はFLOAT MXFP4/NVFP4の分岐、expert名対応、runner backend委譲。INT WNA16判定3関数はAST同一、HIPからWNA16TritonMoEへ進む分岐も維持。今回のINT4/group32/BF16候補をFLOAT新分岐へ変える根拠はない。追加importや委譲を含む実importは未検証。 |
| WNA16 expert | 27,584→27,656 | 非対称zero-pointへload_full_w2属性を渡す1行追加のみ。今回のsymmetric候補はその分岐に入らない。WNA16TritonMoE class全体のASTは同一。 |
| Qwen3Next | 46,686→48,920 | AITERかつgfx95専用のfused attention prologueを追加。AITER=0/gfx1151ではその専用経路を選ばずnative経路を使う。HIPのattention出力gate積は旧sigmoid_gate_mulから共通Triton fused_sigmoid_mulへ移動し、これは今回にも関係する実行経路差。公式helperは既定quant=Falseで出力×sigmoid(gate)を計算するが、実GPU/JIT・数値同一は未判定。 |
| GDN projection | 23,624→23,633 | 環境値取得をget_bool_env_varからenvsのEnvBoolへ変更。公式EnvBoolは文字列0をFalseと解釈し、AITER既定もFalse。明示SGLANG_USE_AITER=0を維持する。関数body群のASTは同一。GDN全体の証明には広げない。 |

`file-0.diff`～`file-3.diff`、`static_checks.json`、公開sourceのbytes/SHA/GitblobSHA1を保存した。参照URLは`public-image-revision/file-*.json`と`supporting-source.json`に記録。比較用textは実行・importしていない。

## 次の最小段階

1. 今回のreceiptと公式hash照合を、新しい公開revisionの**選択4ファイル照合済み**の証拠として採用する。旧baa9bef manifestと失敗判定は原本として保持し、成功に書き換えない。同じCPU検査を新期待値で再実行する必要はない。
2. runtime設定を採用する担当者が、新revision/実dependencyを明記した限定reviewを行う。現在の旧commit固定allowlistを勝手に更新・無効化しない。新しいsource pinを許可する場合も、この固定image・revision・根拠へ限定し、wholecommit一致という承認項目へすり替えない。提案JSONは未適用。
3. 実Triton/torch/JIT適合性とロード資源は、必要な取得/実行承認と既存の前提を揃えた後、予定済みのNext単発起動→1ACK→回収/30B復帰へまとめて確認する。別の小分け人間検査は今は要求しない。context4096/逐次/最大64出力、RAM開始24GiB・継続16GiB/GPU58GiB/swap増加なし、container32GiB、90秒起動/90秒生成/全体900秒の上限は維持し、失敗時に保護を緩めない。

この調査だけではGPU試験開始を許可済みとはしない。重み取得・新ソフト実行の未実施承認や資源前提は既存の担当者確認を維持する。

## オフライン再検証

```text
python3 -B <EVIDENCE_DIR>/verify_evidence.py
```

公開before/newのSHA、GitblobSHA1、既存receiptの実hash全4一致と5項目のAST不変を検査するだけ。対象sourceのimport/execution、network、Docker、GPUはない。`evidence.json`に原本receiptのSHA256も記録した。
