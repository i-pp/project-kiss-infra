# gpt-oss-20b MXFP4 GGUF：Phase B2 単独実機検証

2026-10-28 JST。**ロード・GPU推論・速度測定・メモリ・再起動/切戻しはPASS、コード品質はFAIL**。
検証後はB2を停止し、現用30Bだけが稼働する状態に戻した。B1は停止状態を維持した。
ホスト、ROCm、kernel、BIOS、GPU割当、既存Compose、Repair Loop、独立テストは変更していない。
同時高負荷試験、外部推論API、追加モデル取得、B2のGit commit/pushは実施していない。

## 固定した配布物と実行条件

- 配布元 `ggml-org/gpt-oss-20b-GGUF`、revision `15dcfc7e7c608c6161507211ed43c5b590801b4b`。
- 取得重みは `gpt-oss-20b-MXFP4.gguf` **1ファイル、12,109,566,624 bytes（11.278 GiB）**。
- SHA-256 **`27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`**：全ファイルを計算し指定値との一致PASS。
- 配布元の固定revisionのサイズ/LFS hash/Apache-2.0表記を再確認。上流LICENSEの照合は事前調査ログに保存済み。
- GGUF V3、459 tensors：MXFP4 **72**、Q8_0 **98**、F32 **289**。全tensorが4bitという意味ではない。
- 実GGUFのarchitecture=gpt-oss、24 blocks、context metadata=131072、license=apache-2.0、埋込Harmony templateを確認。
- template SHA-256 `a4c9919cbbd4acdd51ccffe22da049264b1b73e59055fa58811a99efbd7c8146`。
- 現用と同じimage：`ghcr.io/ggml-org/llama.cpp@sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15`。
  b11913、source `7aca0d2ea8d92b56911233b822db01f9fbb1ae50`、ROCm 7.2.1。imageの追加取得・buildは不要だった。

初回urllib転送が約数十KiB/sと遅かったため途中で止め、既存curl（HTTP/2対応）で同じ固定ファイルをresumeした。
途中データは削除せず、TLS検証を維持。curl再開からhash検証まで148.48秒、転送中は約80 MiB/s。実転送のHTTP versionや改善要因は切り分けていない。
Range診断用の約1 MiBも同じ承認済みファイルの断片であり、別モデルではない。最終的な本体hashが一致したことを採用条件とした。

独立Compose projectは`project-kiss-gpt-oss-b2`、公開先は **127.0.0.1:8082のみ**。
UID/GIDは実行環境、GPU補助GIDはkfd/renderの所有GIDから取得する。
非root、cap_drop ALL、no-new-privileges、標準seccomp/AppArmor、rootfs/model read-only、CPU8、RAM24 GiB/swap0、PID512、private IPC。
実効UID1000/CapEff0/NoNewPrivs1/Seccomp2、localhost port mappingとresource設定を各contextで確認した。
通常の専用bridgeであり、完全なegress遮断ではない。モデルはローカル参照、`--offline`を使用し、外部推論APIは呼ばない。

固定条件：parallel1、ngl99、**fit off**、batch256/ubatch128、threads8、K/V=f16、Flash Attention on、context shift無効。
Jinja/Harmony、reasoning-format=deepseek、**reasoning-effort=low**。固定imageのhelpでも各引数を確認した。
8K→16K→32Kで変更したのはcontext長のみ。旧30BとB1の設定は変更しない。

## ロード・推論・形式・速度

全contextで、ロードログに **offloaded 25/25 layers to GPU**、MXFP4 72 tensors、ROCm0 model buffer **10,949.38 MiB**を確認。
token embedding等のROCm_Host model buffer **586.82 MiB**は残る。「全層offload」と「全tensor GPU常駐」は同義ではない。
MXFP4重みのGPU配置とそのモデルからの生成を確認した。個別HIP kernelのprofiler追跡やnative FP4命令の検証はしていない。
モデル全体がBF16/F32に展開されるようなresident buffer・メモリ逼迫は観測しなかった。F32 norm/biasや一時的なkernel内の展開とは区別する。

`/apply-template`の実出力でHarmony特殊tokenと`Reasoning: low`を確認した。
OpenAI互換chat APIはreasoning_contentと最終contentを分離し、17+25への最終回答は全contextと各再起動後に42だった。

| context | 起動待ち秒 | warm prompt tokens/s | warm generation tokens/s | 長文入力tokens | 長文prompt tokens/s |
|---:|---:|---:|---:|---:|---:|
| 8192 | 2.04 | 1439.3 | 69.32 | 7244 | 1511.3 |
| 16384 | 2.04 | 1406.0 | 69.33 | 15436 | 1366.6 |
| 32768 | 2.04 | 1404.7 | 67.00 | 31820 | 1092.2 |

warmは**固定512-tokenのHarmony入力・最大256-token生成**の3回中央値。別にベンチ初回も保存した。
prompt cacheは無効でcache_n=0。温度0/seed42。ベンチ初回もknown-answer試験後であり、完全なcold GPU/I/O試験ではない。
生成速度とTTFTはreasoning・control tokenを含む全生成の値。コードだけの速度やfinal専用TTFTではない。
warm先頭token待ちは約0.356〜0.384秒。長文の応答は全contextでOKとなり、context容量とこの短い指示追従はPASS。
最長の実入力は31820 tokensであり、32768全部を埋めた試験や長文コード理解の証明にはならない。
再起動後のready待ちは各約2.04秒。file cacheをdropせず、モデルのdisk cold loadは測っていない。

## メモリと停止条件

| context | GPU全体peak GiB | 新規サーバーcgroup RAM peak GiB | Linux MemAvailable最小 GiB | 実KV buffer MiB |
|---:|---:|---:|---:|---:|
| 8192 | 32.264 | 1.984 | 45.670 | 192 + 6 |
| 16384 | 32.359 | 2.299 | 43.579 | 384 + 6 |
| 32768 | 32.903 | 2.564 | 44.292 | 768 + 6 |

開始時GPU約20.94 GiBから最大32.90 GiB、差分は約11.96 GiB。GPU/GTTはホスト全体の値で、GUI等の変動も含む。
cgroupのmemory.peakはkernel記録。GPU/Linuxは約1秒間隔の観測であり、サブ秒のGPU peakを保証しない。
CPU検証コンテナには別途RAM2 GiBの制限があり、その使用もLinux全体のavailableに影響する。
cgroup値にGPU領域やホストで既に課金されたmodel page cacheの全量は含まれない。UMAのGPU/GTT/Linux RAMを独立容量として合算しない。

起動前にGPU空き24 GiB・Linux MemAvailable24 GiB・disk空き30 GiB以上を確認して各段階へ進んだ。
実行中はGPU58 GiB超/available16 GiB未満の6秒継続、available8 GiB未満、OOM、GPU reset等、旧30B/B1の状態変化を監視した。
新規B2のID以外を停止できないproject確認を行う。監視異常時もB2のみを停止する。
今回はOOM/GPU reset/継続的圧迫を検出せず、権限緩和やホスト変更は不要だった。実障害を故意に発生させた安全性試験は行わない。

## 独立コード品質：不合格

既存7コード課題・公開仕様・独立テスト・verifier imageを維持した。
各contextで主系列の初回生成と失敗時最大3修正を行い、さらに各課題2回の独立した初回再生成を調べた。
追加再生成は修正せず、主系列の結果を置き換えるbest-of選択にも使用しない。
以前の計画の「修正なし」は、今回の実行承認にある初回/修正後比較へ変更した。

| 課題 | 8K 初回→最終（修正数） | 16K 初回→最終（修正数） | 32K 初回→最終（修正数） |
|---|---|---|---|
| C parse_u32 | PASS→PASS (0) | FAIL→PASS (1) | PASS→PASS (0) |
| C++ append_slice | PASS→PASS (0) | FAIL→PASS (3) | PASS→PASS (0) |
| POSIX write_all_nb | PASS→PASS (0) | PASS→PASS (0) | PASS→PASS (0) |
| Rust prefix_sums | PASS→PASS (0) | PASS→PASS (0) | PASS→PASS (0) |
| AArch64 sum | FAIL→FAIL (3) | FAIL→FAIL (3) | FAIL→FAIL (3) |
| NEON SAD | FAIL→FAIL (3) | FAIL→FAIL (3) | FAIL→FAIL (3) |
| NEON dot | FAIL→FAIL (3) | FAIL→FAIL (3) | FAIL→FAIL (3) |
| 主系列合計 | **4/7→4/7** | **2/7→4/7** | **4/7→4/7** |

合格は独立fixtureでの検証合格を意味し、形式的な全入力保証ではない。
既存のC/C++ ASan/UBSan・strict warning/debug STL、Rust overflow/unsafe制約、AArch64 baseline ISA・QEMU・参照比較を維持した。
verifier imageは`sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c`。
生成コードはnetwork none・GPUなし・非root・read-only、RAM2 GiB/swapなし、CPU4、PID128、全体120秒/step30秒、出力1 MiB/step64 KiB等でのみ実行した。
ホストで生成コードを実行していない。修正時に渡すのは既存feedback.pyがフィルターした情報だけで、期待値・参照コード・fixtureをモデルへ渡さない。
最終contentから指定単一コードブロックだけを抽出し、analysisからの救済やテスト弱体化は行わない。

### 修正の効果と残った原因

- **16K C**：NULL宣言不足によるcompile FAIL。モデルがstddef.hを追加し、独立境界/参照比較がPASS。
- **16K C++**：同じvector由来のiterator範囲をinsertへ渡し、debug STLが拒否。3修正目で一時bufferへコピーする実装となり、独立検証PASS。
  不合格時にはlibstdc++のエラー表示経路内のASan診断もある。モデル自身の直接的なglobal-buffer-overflowと断定せず、先行するself-range拒否と区別する。
- **AArch64 sum**：全contextで`add x2,x2,w3`の幅/拡張指定がassembler error。修正後もcompile FAIL。
- **NEON SAD**：`uint8x16_t`を8-laneの`vabd_u8`へ渡す型不整合等。修正途中にはコード提供拒否も発生。最終候補もcompile FAIL。
- **NEON dot**：初回のintrinsic型不整合からcompile可能な候補へ進んだが、独立参照と不一致。
  最終候補は全contextでint32x4_tへ長期間蓄積してから64bitへ広げる。公開上限n=1000000、全要素-128なら1laneが32768×125000=4096000000となり、32bit範囲を超える。
  これはコードと公開仕様から導いた反例であり、この追加入力を別実行したと主張するものではない。実測では既存独立テストの不一致を確認した。

既存feedbackフィルターは小文字error/note等を対象とし、GNU assemblerの大文字`Error:`診断をモデルへ返していなかった。
この制約を途中で変えず比較条件を維持した。診断欠落が修正停滞へ与えた効果は切り分けていない。
上記分析結果を後続の診断プロンプトへ埋め込んでいない。

### 再生成の不安定さ

主系列初回を含む3回×7課題の初回合格数は、8K **8/21**、16K **9/21**、32K **9/21**。
3回とも初回合格した課題数は各context **2/7**にとどまる。同一payload・temperature0・seed42でも最終出力が変わった。
原因をGPU kernel、量子化、context長等の特定要素へ断定しない。入力payload/output hashとcache_n=0のtimingsを保存している。
32KのRust追加再生成ではdoc-test内の追加fence/テスト例が単一ブロック・no-tests契約に違反し、形式FAILとなった。
3件のコード提供拒否もFAILとして残した。今回の失敗にtoken上限到達は観測されておらず、形式違反と打切りを区別する。
7課題と反復のみでモデル全般の精度やcontext長の効果を一般化しない。

## 記録・保護・実行時間

- ルートログ：`logs/gpt-oss-b2/20261027T164036147397Z/`
- 集計：`summary.json`（品質を含む総合statusはFAIL）、`cause-review.json`、`protection.json`。
- 実行本体：`execution-20261027T165336700287Z/report.json`。このstatusはruntime完了/安全性のPASSであり、品質の合格ではない。
- 各contextにprops、実テンプレート、security inspect、既知回答、benchmarks、長文応答、再起動後回答、startup/fullログ。
- 各課題・各候補にAPI要求/生応答、抽出コード、sandbox/独立判定、フィルター済みfeedback、修正diffを保存。
- 94候補（主系列52、追加初回42）。品質API使用量 **117565 tokens**、うち主系列と修正 **81849 tokens**。速度・長文プローブは別。
- 実行本体 **1126.65秒（約18分47秒）**。モデル取得と事後集計/文書作成は含まない。
- 旧30Bは前後とも42を返し、ID/image/設定/StartedAt/restart count=0/healthyは不変。旧B1の停止状態も維持。
  前後の小入力応答は59.5/56.7 msで、同時高負荷の影響評価ではない。
- モデル12.11 GBを保持。追加df差分は約12.5 GB（他のホスト活動も含む）。新規imageはなく、旧cache・ログ・モデルは削除しない。

## 再現

既存Docker所属が反映された非rootセッションで実行する。必要なら既に登録済みの所属を`sg docker`の子プロセスで適用する。
ホストのユーザー/group設定やsocket権限は変更しない。以下は再実行用で、既にB2が動いている場合controllerは拒否する。

```sh
run="logs/gpt-oss-b2/$(date -u +%Y%m%dT%H%M%S)-reproduce"
mkdir -p "$run" .cache/gpt-oss-b2/runtime
sh scripts/gpt-oss-compose.sh config --quiet
python3 scripts/test-gpt-oss-b2-unit.py -v
python3 scripts/download-gpt-oss.py --report "$run/model-verification.json"
python3 inference/gpt-oss-b2/inspect-gguf.py models/gpt-oss-20b/gpt-oss-20b-MXFP4.gguf > "$run/gguf-inspection.json"
python3 scripts/test-gpt-oss-b2.py --run-dir "$run"
```

モデルが既にあれば全体hashを検証して再利用し、再取得や上書きをしない。各コマンドのexit statusを確認する。
controllerは各contextの結果と監視を新しいexecutionディレクトリへ保存し、正常/異常終了時ともB2のみ停止する。
今回の集計はログ内の`analyze.py`による。既存summaryは上書きしない。

## 未検証と次の候補

- 個別kernel tracing/native FP4命令、final専用TTFT、完全cold I/O、長時間/同時高負荷、完全egress遮断は未検証。
- 32Kの長文コード理解や全入力の正しさは未保証。以前の計画のJSON専用2課題は今回の7コード課題の実行範囲に含めず未実施。
- まずassembler診断の大文字Errorと公開intrinsic型情報を安全に返す別条件で、独立テストを維持して修正効果を比較する案。
- 同一payloadでの出力差を別工程で切り分ける。今回の結果だけで量子化/driverの不具合と断定しない。
- 旧30Bとの同時高負荷は別承認。今回の基盤PASSを品質合格や自動採用可能という意味では扱わない。
