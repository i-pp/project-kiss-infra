# vLLM Phase B1：gfx1151 最小実機検証

2026-10-28 JST。対象は EVO-X3 / Radeon 8060S gfx1151。**GPU推論、localhost API、再起動はPASS**。
既存30Bは停止・再起動・設定変更していない。検証終了後、新規B1コンテナだけを停止した。
長文入力への指示追従はFAILであり、モデルのコード品質や長文精度の合格は主張しない。

## 固定した配布物

公式 [vLLM ROCm手順](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/) にある配布元を使用。
`inference/vllm-b1/versions.lock.json` に以下を固定した。

- タグ：`vllm/vllm-openai-rocm:v0.32.0`
- 実行参照：`vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905`
- 公式registryのmanifestをSHA-256で再検証。config blobのSHA-256も検証し、Dockerはdigest指定で取得。
- 圧縮層合計 11,608,971,476 bytes。Docker image Size 46,775,103,527 bytes。
- 内蔵実測：vLLM `0.32.0+rocm723`、Torch `2.13.0+git733fca1`、HIP `7.2.53211`、ROCm `7.2.3`。
  安定タグのイメージに含まれるTorchはgit版。個別wheelを入れ替えず、イメージ全体を固定する。
- このDockerのimage IDはmanifest digestと同じ。registry config digest
  `sha256:03f01e2ac1e94913e448025fa866f4925e34002a269878779e434bc793215e7f` と混同しない。

モデルは公式 [Qwen/Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)、Apache-2.0。

- revision `2e1fd397ee46e1388853d2af2c993145b0f1098a`
- `model.safetensors` 3,087,467,144 bytes、全tensorのdtypeをヘッダーからBF16と確認。
- 公式LFS SHA-256 `c1b9b30e907950516ba3c646bdf570d8084c25a6410a0cdca80cf04b11bc13a8`
- 設定・tokenizer・LICENSE・README込み9ファイル、3,098,972,269 bytes。
  小ファイルは固定revisionの公式Git blob hash、重みは公式LFS SHA-256で検証。全ファイルのSHA-256も記録。
- 保存先 `models/Qwen2.5-Coder-1.5B-Instruct-BF16/`。既存GGUFは保持した。
  gpt-ossその他のモデルは取得していない。

## 構成と停止条件

独立Compose `inference/vllm-b1/compose.yaml`、project名 `project-kiss-vllm-b1`。
既存のルートCompose・wrapper・モデル・Repair Loop・独立テストは変更しない。

- UID/GIDは実行環境から取得し、GPU補助GIDは両デバイスの所有GIDを検証して取得。
- GPUデバイスは `/dev/kfd` と `/dev/dri/renderD128` だけ。非root、privilegedなし、cap_drop ALL、no-new-privileges、標準seccomp/AppArmor。
- rootfsとモデルはread-only。新規専用キャッシュだけを `.cache/vllm-b1/runtime/` に書く。
- CPU 8、RAM 24 GiB、swap 0、PID 512、private IPC、shm 2 GiB、tmpfs 2 GiB。
  実効値と UID 1000 / CapEff=0 / NoNewPrivs=1 / Seccomp=2 を確認した。既存30BのRAM設定は変更しない。
- 専用の通常bridgeと `127.0.0.1:8081:8000`。host networkは使用しない。
  **通常bridgeには外向き経路がある**。完全なネットワーク遮断を保証する構成ではない。
  モデルはローカル参照、HF/Transformersはoffline、telemetry/usage statsを無効化。外部推論APIは呼ばない。
- GPU基本演算チェックのコンテナはnetwork none。
- BF16、context 8192、max-num-seqs 1、TP 1、batch tokens 512、eager、TRITON_ATTN。
  wrapperはcontext 8192超を拒否する。今回context縮小は不要だった。
- GPU memory utilization 0.20（64 GiBの12.8 GiBが目安）。これは実利用量の厳密な上限ではない。
  実測ログはモデル約2.98 GiB、KVプール約9.46 GiB。予約KVは354,448 tokensだが、APIの1要求の上限は8192、同時実行上限は1。

`scripts/test-vllm-b1.py` は起動直前にGPU/RAMの余裕を確認し、実行中は約2秒間隔で監視する。
GPU総使用58 GiB超、Linux MemAvailable 16 GiB未満が3サンプル継続、既存30Bのhealth/StartedAt等の変化、
新規OOM、監視対象のカーネルGPU reset/fault/timeout・OOMログを検出すると、**B1 projectだけ**を停止してFAILを保存する。
通常終了時もB1だけ停止する。これはハードウェアレベルのメモリ分離や瞬間的な超過防止を保証しない。

## 結果

機械可読ログ：`logs/vllm-b1/20261027T155727443976Z/`。
主結果は `serve-20261027T160638324995Z/report.json`、最終集計は `summary-final.json`。
2秒サンプルは各runの`memory.jsonl`、実効権限・制限・併存時APIは`effective-runtime-and-coexistence.json`。

| 検証 | 結果 | 根拠 |
|---|---|---|
| gfx1151認識、FP32/BF16 GEMM・要素演算 | PASS | gpu-check出力、CPU参照との比較 |
| モデル整合性・全tensor BF16 | PASS | model-verification.json |
| 8K設定でlocalhost OpenAI互換API生成 | PASS | 3要求とも57入力/56出力tokens、Cコードを生成 |
| 長文の処理容量 | PASS | 入力7038 + 出力16 = 7054 tokens、HTTP 200 |
| 長文の「OKだけ返す」指示 | **FAIL** | `x`を16個出力しlength終了。原因は未確定 |
| B1再起動後の再生成 | PASS | StartedAt変化、health応答、56 tokens再生成 |
| 既存30Bの保護 | PASS | 検証前・併存時・後ともHTTP 200、回答42。StartedAt/ID/image/restart count不変 |
| 監視・health応答処理の単体テスト | PASS | 標準unittest 5件。故障注入はmockで行い、実GPU reset等は起こさない |

初回短文生成を含むdecode速度は **71.35 / 70.10 / 68.60 tokens/s**、再起動後 **71.66 tokens/s**。
計算はSSEの `(completion_tokens - 1) / (最後のcontent時刻 - 最初のcontent時刻)`。
SSE chunkとtokenの境界が一致するとは限らず、短い出力1種の近似測定である。
TTFTは1.698 / 0.038 / 0.040秒、再起動後0.148秒。初回warmupとキャッシュの差を含む。
metricsの4要求合計prefill時間・prompt tokensからの集計もsummaryに保存する。長文単独の純prefill速度とは区別する。

成功runの起動待ち20.30秒、再起動後20.31秒、全体53.89秒（image/model取得は含まない）。
ホスト全体GPUは約20.74 GiBから最大 **33.64 GiB**（差分約12.90 GiB）。
成功runの新規cgroup RAM peakは **2.70 GiB**、Linux MemAvailableの最小は **46.74 GiB**。
初期の失敗試行を含むcgroup RAMピークは3.00 GiB。GPU/Linux値はサンプル値で、サブ秒のピークは未捕捉。
cgroup peakはカーネルのmemory.peakであり、GPU領域やホスト側で既に課金されたモデルpage cacheの全量を表さない。
UMAのGPU・GTT・Linux RAMを独立した追加メモリとして合算しない。

既存30Bの同じ小入力への応答は成功run前58.6 ms / B1併存時58.8 ms / 後53.7 ms。
すべてprompt cache利用、3出力tokens、少数測定のため性能劣化なしと一般化しない。
併存時の測定はvLLMロード中であり、両モデルが同時decodeする負荷試験ではない。
OOM・GPU reset・持続的メモリ逼迫は今回の監視では検出しなかった。

## 失敗履歴と修正

既存ログも今回の失敗ログも上書きしない。以下を合格に置き換えず、別runで再検証した。

1. `logs/vllm-b1/20261027T155631560018Z/report.json`：元のプロセスにdocker GIDが反映されずアクセスFAIL。
   NSSでは既にユーザーがdocker所属。`sg docker`の子プロセスで既存所属を適用でき、ホスト設定・権限の変更は不要だった。
2. `probe-20261027T160100057968Z/`：演算検査が微小なBF16差約1.8e-7を誤差ゼロ条件でFAIL。
   CPU参照と入力を維持し、GEMMのrtol/atolを1e-5と明示。再検査`probe-20261027T160138302654Z/`はPASS。
3. `serve-20261027T160311747473Z/`：internal-only bridgeではHostConfigの要求に対して実ポートマッピングがnull。
   vLLM内部起動まで確認したが、localhost API未成立としてFAIL。新規側だけを停止し、専用の通常bridgeで再試行した。
   [Mobyの同種報告](https://github.com/moby/moby/discussions/53256)もあるが、本機でのinspect結果を根拠とする。
4. `serve-20261027T160512075979Z/`：HTTP 200・空ボディのhealthを検証側がJSONとして扱ったため待機。
   検証プロセスへSIGINTを送り、finallyで新規側だけを停止。試行はFAILのまま保存。
   空ボディを扱うよう修正し、単体テストと新しい成功runで確認した。

失敗時の既存サーバー保護確認も各reportに保存。累積Dockerログと今回の時間範囲だけのログは区別する。
最終レビューでREADME追記位置を末尾へ修正し、旧README全体をprefixとして保持する検査を通した。
初回の文書保護チェックFAILは`protection.json`/`summary.json`に残し、修正後は`protection-final.json`/`summary-final.json`に保存。
稼働中のB1が既にある場合に停止せず拒否する後処理も修正し、mockによる拒否経路テストを追加した。
この最終変更後の追加GPU実行は行っていない（推論経路は変更せず、拒否時の後処理だけを変更）。

追加ディスク使用量はdf差分で約50.05 GB（約46.61 GiB、他のホスト活動も含む）。
新規イメージ46.78 GB、モデル3.10 GB、キャッシュ約86 MB、ログ約2 MBが主な内訳。
既存6イメージ・3コンテナ・92追跡ファイル（READMEは元の全文を保持して追記）・771ログ・既存2モデル・ホスト設定の保護を確認した。

## 再現

リポジトリrootで実行。Docker利用権限がある非rootセッションが前提。
今回のようにNSS所属が既にあるのにセッションに反映されていない場合だけ、以下を`sg docker -c '…'`で実行できる。
socketのchmod/chown、ユーザー追加、sudo、daemon設定変更は行わない。

```sh
id
docker ps
mkdir -p .cache/vllm-b1/runtime logs/vllm-b1
# 新しい、未使用のログディレクトリを選ぶ
run="logs/vllm-b1/$(date -u +%Y%m%dT%H%M%S)-reproduce"
mkdir "$run"
docker pull vllm/vllm-openai-rocm@sha256:14f6a575e1fb0a580b0f633c09e06f648709d60405b85f6a7ff3f80d49f39905
sh scripts/vllm-compose.sh config --quiet
python3 scripts/test-vllm-b1-unit.py -v
python3 scripts/test-vllm-b1.py probe --run-dir "$run"
python3 scripts/download-vllm-b1-model.py --report "$run/model-verification.json"
python3 scripts/test-vllm-b1.py serve --run-dir "$run"
```

ダウンローダーは既存ファイルがあれば検証して再利用し、上書きしない。
失敗した`.part`が残る場合も勝手に削除せず停止する。test runnerも既にB1が稼働中なら停止して上書きせず、開始を拒否する。
再実行の失敗を見落とさないよう、各コマンドのexit statusを確認する。
初回から設定を変更する場合は別条件として記録し、再承認が必要な範囲を確認する。

モデル・ログ・キャッシュは既存gitignoreにより追跡対象外。Git commit/pushは実行していない。

## 未検証と次の候補

- 完全8192 tokensを埋めた入力、16K以降、複数同時要求、長時間連続稼働、両サーバーの同時decode。
- Cコードのコンパイル・正しさの独立採点、長文指示追従不良の再現率・原因。今回は推論動作のPoC。
- CUDA graph/torch.compile、別attention backend、より大きいモデル。ロード成功だけから性能を推定しない。
- 完全なegress遮断を必要とする場合、現在の通常bridgeとは別途設計・検証が必要。
- 次の最小改善候補は余分なKV予約の縮小、初回とwarm状態を分けた測定、固定された独立コード課題。
  gpt-oss-20b以降の取得・検証にはまだ進んでいない。
