# Project-KISS

## 目的

KISS（Keep It Simple, Stupid）の原則に従い、Dockerを基本としたシンプルなローカルLLM推論基盤を構築する。
ホストの既存環境を保護し、APIやサービスを外部公開しない。

## 現在の状態

Repair Loop v2: 同一Qwen3-Coderによる診断分離を実装・比較。最終合格はbaselineと同じ3/7件で、追加コストに見合う改善は今回確認できなかった。
APIは `http://127.0.0.1:8080/v1`。現在は30B・32,768コンテキストで稼働中（healthy）。
操作は `sh scripts/coder-compose.sh ...` を使用する。元の0.5Bモデル、測定JSON、以下のPhase 2測定結果も保存している。

| ファイル | 用途 |
|---|---|
| `AGENTS.md` | 開発・作業時に従う15の原則 |
| `.gitignore` | モデル、認証情報、キャッシュ、生ログをGitから除外 |
| `compose.yaml` | llama-server 1サービスの構成 |
| `scripts/compose.sh` | UID/GIDとGPUデバイスの補助GIDを実行環境から取得してComposeを実行 |
| `scripts/check-gpu.sh` | サービスと同じ非rootユーザー・デバイスでGPU認識を検証 |
| `scripts/download-model.sh` | 対象GGUF 1個を取得しSHA256照合。既存ファイルは上書きしない |
| `scripts/benchmark.py` | 固定APIリクエストの速度とメモリを測定。Python標準ライブラリのみ使用 |

## 検証環境と採用バージョン

- Ubuntu 26.04.1 LTS / x86_64、Linux `7.0.0-38-generic`
- AMD Ryzen AI MAX+ 395 / Radeon 8060S / `gfx1151`、物理メモリ128GB、GPU割当64GiB
- ホストはUbuntu配布ROCm 7.1系（`rocm` 7.1.0、`rocminfo` 7.1.1）
- Docker Engine 29.9.2 / Docker Compose 5.6.1
- コンテナはUbuntu 24.04 / ROCm 7.2.1、llama.cpp `0.7.0-dev`（build `11913`、commit `7aca0d2ea8d92b56911233b822db01f9fbb1ae50`）

llama.cpp公式 `ghcr.io/ggml-org/llama.cpp:server-rocm` の公開メタデータを調査し、次のlinux/amd64イメージをdigest固定で使用。

```text
ghcr.io/ggml-org/llama.cpp@sha256:0b332e21bec106548887f5747c0574bce63b8dd725f26d20382ff2711993ab15
```

公式Dockerfileには `gfx1151` がビルド対象として含まれる。GPUイメージの公式CIはビルドまでのため、今回のホストとコンテナの組合せは本機で実測した。
イメージの圧縮レイヤー合計は約7.72GB。これはROCm等の実行環境で、モデルデータとは別。
公式イメージで動作したため、Dockerfileによる独自ビルドは行っていない。

参考: [llama.cpp公式Docker資料](https://github.com/ggml-org/llama.cpp/blob/master/docs/docker.md)、[公式ROCm Dockerfile](https://github.com/ggml-org/llama.cpp/blob/master/.devops/rocm.Dockerfile)、[採用コミットのサーバー資料](https://github.com/ggml-org/llama.cpp/blob/7aca0d2ea8d92b56911233b822db01f9fbb1ae50/tools/server/README.md)、[Ubuntu 26.04リリースノート](https://documentation.ubuntu.com/release-notes/26.04/changes-since-previous-interim/)。

## Compose構成

| 項目 | 設定 |
|---|---|
| プロジェクト / サービス | `project-kiss-phase2` / `llama-server` |
| 実行ユーザー | 実行ユーザーの数値UID/GID。UID 0は起動スクリプトで拒否 |
| GPUデバイス | `/dev/kfd`、`/dev/dri/renderD128` のみ |
| 補助グループ | デバイスの所有GIDを起動時に取得。`GPU_GID` で明示指定も可能 |
| 公開ポート | `127.0.0.1:8080:8080` |
| コンテナ内待受 | `0.0.0.0:8080`（Dockerのlocalhost公開に必要） |
| モデル | `./models` → `/models`、読み取り専用 |
| コンテキスト / 同時処理 | 2,048 / 1 |
| バッチ / マイクロバッチ | 256 / 128 |
| GPUオフロード | `--n-gpu-layers 99`。今回のモデルでは全25層 |
| 自動メモリ調整 | `--fit off` |
| CPUスレッド / バッチ用スレッド | 16 / 16（最初の起動で実際に選ばれた値を明示固定） |
| ログ / UI | 詳細度4（層数確認用）、UI無効 |
| RAM上限 | 設定なし。実行状態でも `HostConfig.Memory = 0` を確認 |
| ヘルスチェック / 再起動ポリシー | `/health` / `unless-stopped` |

`scripts/compose.sh` は2つのGPUデバイスのGIDが一致することを確認して、補助グループを1回だけ渡す。
本機の実測値は990だが、構成ファイルには固定していない。GIDが異なるホストでは自動実行を中止し、そのホスト向けの `group_add` 構成を検討する。
`LOCAL_UID`、`LOCAL_GID`、`GPU_GID` を環境変数で指定する場合は、両デバイスとモデルへのアクセス権が必要。

privileged、追加capability、seccompの緩和、host IPC、アーキテクチャ偽装は使用していない。
ホストのパッケージ追加、GPUドライバ・ROCm・BIOSの変更は行っていない。既存Ollamaのファイルや設定も変更していない。

## 0.5B構成の構築と操作（Phase 2）

既存のDocker/Compose、Dockerを操作できるユーザー、GPUデバイス、`curl`、`sha256sum`、Python 3を使用する。ホストに依存パッケージを追加する手順は含まない。
リポジトリルートで実行する。

```sh
# 公式イメージを使用し、ポート公開せずにGPU認識を確認
sh scripts/check-gpu.sh

# 小規模な対象GGUF 1個だけを取得し、公開SHA256を照合
sh scripts/download-model.sh

# 構成検証と起動
sh scripts/compose.sh config --quiet
sh scripts/compose.sh up -d --wait --wait-timeout 180

# 状態・GPUオフロードログ
sh scripts/compose.sh ps
sh scripts/compose.sh logs --no-color llama-server
```

検証モデルはQwen公式 [Qwen2.5-0.5B-Instruct-GGUF / Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/blob/main/qwen2.5-0.5b-instruct-q4_k_m.gguf)（Apache-2.0）。
ファイル名は `qwen2.5-0.5b-instruct-q4_k_m.gguf`、実測サイズは491,400,032 bytes。
取得上限は600,000,000 bytes。リポジトリ全体や他の量子化モデルは取得しない。

```text
SHA256: 74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db
```

```sh
curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/v1/models
curl --fail http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kiss-qwen2.5-0.5b","messages":[{"role":"user","content":"What is 2 + 2? Answer with the number only."}],"temperature":0,"seed":42,"max_tokens":16,"stream":false,"cache_prompt":false}'

# 速度・メモリ測定。既存のlogs/benchmark.jsonがあれば上書きせず停止
python3 scripts/benchmark.py

# このComposeサービスのみ再起動 / 停止
sh scripts/compose.sh restart llama-server
sh scripts/compose.sh stop llama-server

# 停止後の再開
sh scripts/compose.sh up -d --wait --wait-timeout 180
```

ベンチマークの再実行時は、既存の `logs/benchmark.json` を別名で保存してから実行する。
ベンチマークはLinuxのcgroup v2とホストの `/proc`、`/sys` を読み取れる環境で実行する。

## 0.5B測定結果（2026-10-27 16:34 JST）

非rootの `uid=1000`、実行時に取得した補助GIDで、`rocminfo` が `gfx1151 / Radeon 8060S Graphics` を認識。
`llama-server --list-devices` も `ROCm0`、65,536MiBを列挙した。
起動ログで `offloaded 25/25 layers to GPU` を確認。

| 起動ログのGPUバッファ | 容量 |
|---|---:|
| ROCm0 model buffer | 373.73 MiB |
| ROCm0 KV buffer（K/Vともf16） | 24.00 MiB |
| ROCm0 compute buffer | 9.38 MiB |

Flash Attentionはイメージの既定値 `auto` で、ログでは有効化を確認。
測定条件はCompose設定に加え、`scripts/benchmark.py` 内の同一プロンプト、temperature 0、seed 42、生成上限128、stream false、cache_prompt false。
起動時の組込みウォームアップに加え、同じリクエストを1回ウォームアップとして実行し、その後に3回測定した。
全3回ともプロンプト75トークン、生成128トークン、キャッシュ再利用0トークンだった。

| 試行 | プロンプト処理 tokens/s | 生成 tokens/s | API往復時間 秒 |
|---|---:|---:|---:|
| 1 | 7,431.63 | 297.17 | 0.442 |
| 2 | 7,705.74 | 296.23 | 0.442 |
| 3 | 7,648.38 | 298.78 | 0.439 |
| 中央値 | **7,648.38** | **297.17** | **0.442** |

速度はAPI応答の `timings.prompt_per_second` と `timings.predicted_per_second`。API往復時間は別途クライアントで測定した。
入力条件を固定しても、GPUの浮動小数点計算等により出力テキストの完全一致は保証しない。

| メモリ指標 | サーバー初回起動前 | 測定前の待機時 | 測定中の観測最大 |
|---|---:|---:|---:|
| GPU VRAM使用量（デバイス全体） | 1,014.58 MiB | 1,681.30 MiB | **1,693.34 MiB（約1.65GiB）** |
| GPU GTT使用量（デバイス全体） | 87.57 MiB | 107.87 MiB | 108.87 MiB |
| コンテナRAM（cgroup memory.current） | — | 317.52 MiB | **342.32 MiB** |

GPUメモリは `/sys/class/drm/renderD128/device/mem_info_vram_used` と `mem_info_gtt_used`、RAMは当該コンテナのcgroup v2 `memory.current` を使用。
測定3回の実行中に約0.1秒間隔で計14サンプルを取得した。真の瞬間最大値を保証する値ではなく、起動中のピークも含まない。
VRAMの起動前からの観測最大増分は約678.76MiB。ただしデバイス全体の値にはデスクトップ等も含むため、サーバー専有量とは一致しない。
APUのVRAM/GTTとコンテナRAMは単純加算しない。RAM上限は今回導入していない。

`/health`、`/v1/models`、`/v1/chat/completions` の正常応答を確認し、計算質問への応答は `4`。
コンテナ再起動後もhealthyとなり、同じAPIリクエストへの応答が `4` であることを確認した。
Docker inspectとホストの待受一覧で、公開先が `127.0.0.1:8080` のみであることを確認した。
再起動後の実行状態でも非root、privileged false、追加capabilityなし、SecurityOpt未指定、RAM上限なしを確認。

生ログ・API応答・メモリサンプルはローカルの `logs/` に保存し、Git管理対象外。
主な記録は `gpu-check-after-compose-fix.log`、`startup-complete.log`、`before-server-start.json`、`benchmark.json`、`runtime-before-restart.json`、`runtime-after-restart.json`、`api-after-restart.json`。
モデルとダウンロード一時ファイルも `models/` としてGit管理対象外であることを確認した。

## Phase 2完了時点の未検証事項

- 長時間連続運転、多数リクエスト、同時接続負荷での安定性
- ホスト再起動後の自動復帰（コンテナ単体の再起動は検証済み）
- 別モデル、別量子化、大きなコンテキスト、CPUのみとの速度比較
- RAM上限を導入した場合の動作、真の瞬間ピークとGPUメモリの強制上限制御
- 既存Ollamaとの同時GPU利用。今回Ollamaサービスは停止状態で、設定・データには触れていない

この結果は対象0.5Bモデルと上記構成に限定する。64GiB全量を使う設定や大規模モデルの取得は行っていない。

## 30Bコーディングモデルの導入（Phase 3）

指定配布元 [ggml-org/Qwen3-Coder-30B-A3B-Instruct-GGUF](https://huggingface.co/ggml-org/Qwen3-Coder-30B-A3B-Instruct-GGUF) の公開APIで、取得前に存在・全ファイル構成・サイズ・ライセンスを確認した。
対象は **Qwen3-Coder-30B-A3B-Instruct / Q4_K_M**、Apache-2.0。
リポジトリにはBF16、Q8_0、Q4_K_Mが各1ファイルあり、取得したのはQ4_K_M 1個のみ。分割モデルではない。
配布元によるとQ4_K_Mではexpertを基準の量子化形式とし、embedding・attention等の小さな非expertテンソルはQ8_0に保持される。

| 項目 | 確認値 |
|---|---|
| 固定リビジョン | `0ca51122012fe4a20dc82988ee58780b008ce4e3` |
| ファイル | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` |
| サイズ | **17,988,419,552 bytes（約17.99GB / 16.75GiB）** |
| SHA256 | `f6050b4da22869aa3fb9d94bb3314e9fc5a027d4741c1f97761c387d6b2b2335` |
| アーキテクチャ | `qwen3moe`、48ブロック、128 experts / 8 active |
| llama.cpp | Phase 2の公式イメージ・digestを継続使用（b11913 / `7aca0d2ea`） |

取得前に採用コミットの `src/models/qwen3moe.cpp` に48層の30B-A3B実装があることを確認。
取得後に厳密なサイズ・SHA256を照合し、本機でロード・推論まで検証した。出所の固定情報は `evaluation/coder/model.json` に保存。

事前のディスク空き容量は約1.7TiB、0.5B稼働時のGPU使用量は約1.66GiB。
`scripts/download-coder.sh` は対象ファイルのサイズを取得上限とし、モデル＋5GiB以上のディスク空きも確認する。
0.5Bモデルのファイルおよび `logs/benchmark.json` が変更されていないことを取得前後のハッシュで確認した。

```sh
# 再取得が必要な場合のみ。既存の対象ファイルがあれば照合だけ行う
sh scripts/download-coder.sh

# 30Bの通常起動（既定コンテキスト32,768）
sh scripts/coder-compose.sh up -d --wait --wait-timeout 180
sh scripts/coder-compose.sh ps
sh scripts/coder-compose.sh logs --no-color llama-server

# 16Kへ切替える場合
CONTEXT_SIZE=16384 sh scripts/coder-compose.sh up -d --wait --wait-timeout 180

# 32Kに戻す場合
CONTEXT_SIZE=32768 sh scripts/coder-compose.sh up -d --wait --wait-timeout 180

# 元の0.5Bへ切替える場合（モデルや既存測定データは保持）
sh scripts/compose.sh up -d --wait --wait-timeout 180
```

サービスは1個を切り替えて使用する。`compose.yaml` の追加変数は `MODEL_FILE`、`MODEL_ALIAS`、`CONTEXT_SIZE` の3個で、未指定時は従来の0.5B設定を維持する。
30B用ラッパーがモデル・aliasとコンテキストを渡す。30BのAPIモデル名は `kiss-qwen3-coder-30b`。
GPUデバイス・GID取得・非root・localhost限定・`--n-gpu-layers 99`・`--fit off`・スレッド16・バッチ256/128・RAM上限なしは維持した。
ホストのドライバ、ROCm、BIOS、Ollama設定・データは変更していない。

## 30BのGPUオフロード・コンテキスト測定

2026-10-27 17:07〜17:09 JSTに8,192→16,384→32,768の順で測定。
各起動ログで **49/49層をGPUへオフロード** したことを確認。モデルの48ブロックに出力層を含めたログ上の層数である。
ROCm0 model bufferは16,834.11MiB、ROCm_Host model bufferは315.30MiBも併用。KVはf16、Flash Attentionはautoで有効化された。

同一の短文入力（54トークン）を1回ウォームアップ＋3回測定。temperature 0、seed 42、生成上限128、stream false、cache_prompt false。
長文はコンテキスト上限から約1,024トークンの余白を残す合成Cソースを、chat templateとtokenizerで事前計数して1回測定した。
実際のプロンプト・生応答・0.1秒間隔のメモリ観測は `logs/coder/context-*.json` に保存。

| コンテキスト | 短文PP tokens/s（中央値） | 短文生成 tokens/s（中央値） | 長文入力トークン | 長文PP tokens/s | 長文生成 tokens/s |
|---:|---:|---:|---:|---:|---:|
| 8,192 | 665.63 | **64.54** | 7,164 | 984.93 | **52.42** |
| 16,384 | 668.12 | **64.12** | 15,336 | 814.63 | **44.17** |
| 32,768 | 667.69 | **64.51** | 31,716 | 553.70 | **32.69** |

PPはプロンプト処理。速度はサーバーAPIのtimings値で、全リクエストでキャッシュ再利用0、生成128トークンを確認した。
短文での速度はコンテキスト設定を拡張してもほぼ同じ。実際に履歴が長くなると、PP・生成とも低下した。
0.5Bの比較用記録は保持しているが、同じ文章でもモデルごとのtokenizer/templateが異なり、入力トークン数は0.5Bの75に対して30Bは54となる。

| コンテキスト | KVバッファ MiB | GPU VRAM観測最大 GiB | GTT観測最大 MiB | コンテナRAM観測最大 MiB | cgroup起動後RAMピーク MiB |
|---:|---:|---:|---:|---:|---:|
| 8,192 | 768 | **18.68** | 101.20 | 634.11 | 638.35 |
| 16,384 | 1,536 | **19.44** | 101.20 | 658.12 | 662.61 |
| 32,768 | 3,072 | **20.98** | 101.20 | 698.67 | 701.16 |

GPU値はデバイス全体で、デスクトップ等も含む。RAMは当該コンテナのcgroup `memory.current` と `memory.peak`。
このRAM値は、ホスト側で既にキャッシュされた18GBのモデルファイルを含むホスト総RAM使用量ではない。GPU/GTT/RAMは単純加算しない。
サーバー初回切替前のVRAMは約1.09GiB。30B・32K再起動後のホストMemAvailableは約53.29GiBだった（単一時点の値）。
GPU観測値は瞬間的な真のピークを保証しない。RAM上限の導入は行っていない。

32K設定でコンテナ再起動後もhealthy、OpenAI互換APIで計算質問への応答 `4` を確認。
実行状態のinspectとホスト待受でも、非root・デバイスの実GID・`127.0.0.1:8080` のみの公開・privileged無効・セキュリティ緩和なし・RAM上限なしを再確認した。

## コーディング評価結果

課題・独立テスト・根拠は [`evaluation/coder/README.md`](evaluation/coder/README.md) と同ディレクトリのソースを参照。
課題とテストを生成前に固定し、既知の正しい実装7件が通り、意図的な誤実装7件を検出することを事前確認した。
モデルにはテストや参照コードを渡していない。

評価は32K設定、temperature 0、seed 42、最大2,048出力トークン、1課題1回。全9応答は指定形式を守り、出力上限による打切りもなかった。
コードブロックをそのまま抽出し、モデルへの再質問・手修正なしで採点。

| 課題 | 未修正の初回結果 | 根拠・追加診断 |
|---|---|---|
| C11 uint32解析 | **不合格** | `NULL`用ヘッダ不足でコンパイル不可。ヘッダだけ強制includeした診断でも `out=NULL` を成功扱いし、独立assertに失敗 |
| C++20 自己参照append | **合格** | 98,020ケース＋SIZE_MAX境界、元配列の独立コピーと一致。libstdc++ debug・ASan・UBSanを通過 |
| POSIX 非同期write | **不合格** | `SSIZE_MAX`用の `<limits.h>` 不足。ヘッダだけ補う診断では短いwrite・EINTR・EAGAIN・0・hard error・本物の非同期pipe/EPIPEを全て通過 |
| Rust prefix sum | **合格** | i64参照実装と5,000入力列で一致。途中オーバーフロー後に相殺する境界も検出。unsafe禁止・overflow-checks有効で通過 |
| AArch64 unsigned sum | **不合格** | コンパイル可、参照和assertに失敗。n=0時に未初期化x3を返す。x3へ既知値を設定する独立プローブでも再現 |
| NEON unsigned SAD | **不合格** | `abs`用の `<stdlib.h>` 不足。ヘッダだけ補うと、n<16で `size_t n-16` がアンダーフローし保護ページ境界でSIGSEGV |
| NEON signed dot | **不合格** | `vmull_p8`（多項式乗算）へ符号付き整数ベクトルを渡しコンパイル不可。静的レビューでは短いnのアンダーフローと下位半分の集計結果上書きも確認 |
| 不明なwire仕様への対応 | **合格** | 構造体定義・wire format・endianness・不正入力・サイズの5点を質問し、勝手な実装や既定値を作らなかった |
| C11 UBレビュー | **不合格（部分的に検出）** | 6種類の論点は列挙。ただし負のsigned左シフトをimplementation-definedと誤説明、effective typeを過度に一般化し、要求したendiannessとUBの区別を説明しなかった |

**コード課題の初回完全合格は2/7、コンパイル成功は3/7。レビュー課題を含む完全合格は3/9。**
ヘッダ強制include等の追加診断は原因分析用であり、初回の不合格を合格へ変更していない。
UBレビューはC11 N1570の6.3.2.3、6.5、6.5.7等に照らして評価した。`void*`経由のcastだけで常にeffective type違反になるわけではなく、元のオブジェクト型とアクセス方法が重要。

検証用DockerイメージはUbuntuの固定digestを基に構築し、追加パッケージの取得は270,159,504 bytes。
GCC/G++ 15.2.0、Rust 1.93.1、AArch64 GCC 15.2.0、QEMU 10.2.1を使用。
検証イメージIDは `sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c`。
AArch64/NEONはbaseline `-march=armv8-a` でクロスコンパイルし、QEMU `cortex-a53` で検証した。Arm実機の速度測定はしていない。
生成コードはネットワークなし、非root、rootfs読み取り専用、capability全削除、no-new-privileges、RAM 2GiB/CPU 4/PID 128制限の別コンテナでのみ実行した。このRAM制限は推論サーバーには適用していない。

```sh
# 検証用イメージを再構築する場合（パッケージはコンテナ内のみ）
docker build -t project-kiss-code-eval:20261027 evaluation/coder

# 既存結果を別名で保存したうえでの再測定・再評価用
sh scripts/measure-coder-contexts.sh
python3 scripts/generate-coder-evaluation.py
sh scripts/test-coder-output.sh logs/coder/eval
```

既存の結果ファイル・評価ディレクトリがあればスクリプトは上書きを拒否する。
`logs/coder/eval/*-response.json` にプロンプトと生応答、同ディレクトリに未修正コード、`test-results.json` にコンパイラ・実行ログ、`diagnostics.json` に追加診断、`logs/coder/assessment.json` に判定根拠を保存。
モデル、生成コード、コンパイル生成物、生ログはいずれもGit管理対象外。

## Phase 3時点の判断と改善案

推論基盤としては32Kまで全層GPUオフロードで動作し、短文約64 tokens/s、31K入力時も生成約33 tokens/sだった。
コーディング支援では、今回のC++/Rust課題と仕様確認は有用な結果だった一方、Cのヘッダ・NULL契約、低レベルASM/SIMD、C11の厳密な説明ではレビューと独立テストが必須。
初回出力をそのまま低レベル実装へ採用できる品質とは判定しない。

次に試す改善は、(1)コンパイルエラーと境界テスト結果を返す修正ループ、(2)検証済みNEONのwideningと安全な末尾ループを参照させる方式、(3)モデル公式推奨samplingと今回のgreedy設定との比較、(4)実際の小規模リポジトリを用いた変更・回帰テスト評価。
公式推奨値は元モデルの [Best Practices](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct#best-practices) に基づくtemperature 0.7、top_p 0.8、top_k 20、repetition_penalty 1.05。今回は条件を固定するためtemperature 0を使用し、推奨値の比較は未実施。
通常の短い編集は8K/16Kでも十分な余裕があり、長い履歴を要する場合に32Kを選べる。現在は要求された最大条件の32Kで稼働させている。

未検証: 長時間運転、多人数同時接続、実リポジトリ全体での品質、長文の検索・理解精度、AArch64実機上の正しさと性能、別sampling/量子化、Ollamaとの同時GPU利用、ホスト再起動後の復帰。
今回の9課題は小規模な独自評価であり、一般的なコーディング能力を統計的に代表するベンチマークではない。

## 独立検証・自動修正ループPoC（Phase 4）

既存の7コード課題・独立テストを再利用し、初回生成→隔離コンパイル/実行→診断の選別→最大3回の修正→最終判定を自動化した。
実装・隔離方式・実行手順は [`evaluation/coder/repair/README.md`](evaluation/coder/repair/README.md)、入口は `scripts/repair-coder.py`。
Python標準ライブラリと既存の検証イメージを使用し、ホストへのパッケージ追加・推論サーバーの再設定や再起動は行っていない。

### 隔離と事前検証

候補ごとに新しい非rootコンテナを作成し、ネットワークなし・GPUなし・Dockerソケットなし・capability全削除・no-new-privileges・標準seccomp/AppArmorで実行。
rootfs、候補、既存テストは読み取り専用で、書込み可能なホストマウントはない。
書込み先は容量256MiBずつの `/work` と `/tmp`。バイナリ実行に必要な `/work` のみexecを明示した。既存ホスト・サーバーの制限は変更していない。
RAM 2GiB、追加swapなし、CPU 4、PID 128、1ファイル32MiB、core dumpなし。
各コンパイル/実行コマンド30秒、候補コンテナ120秒、出力量は各コマンド64KiB/コンテナ1MiBを上限にする。

実機プローブで非root・RO・通信不可・GPUなし・cgroup/RLIMITを確認し、時間超過停止、出力超過停止、64MiB制限下でのOOMも確認。
新しい単一課題ランナーは、既知の正しい実装7件を全て通し、意図的な誤実装7件を全て検出した。
診断フィルターも独立テストを行い、テスト側assertや期待値がモデル向けメッセージへ混入しないことを確認した。

テスト・参照実装は変更せず、開始時のSHA256を各候補の前後と終了時に照合した。
モデルに返すのは候補単独のコンパイル診断と、実行失敗の分類のみ。テストソース、assert式、テスト入力、期待値、参照実装、生の実行ログはAPIへ返さない。
コンパイラ・サニタイザ・テストの生ログはローカル保存する。コンパイラ設定をモデルに変更させたり、テストを弱めたりはしない。

### 実行結果（2026-10-27 17:42〜17:44 JST）

既存30B・32Kサーバー、temperature 0、seed 42、最大2,048出力トークン、cache_prompt false。
7件を新規生成し、合格時は修正を止め、不合格は初回＋最大3修正まで実行した。評価対象はコード7課題のみで、前段階のレビュー2課題は含めない。

**初回2/7（28.57%）→修正後3/7（42.86%）、改善は1件・14.29ポイント。**
初回不合格5件中、自動修正で合格に到達したのは1件。全7件を通じて20候補・13修正、APIトークンは入力14,600＋出力6,413＝21,013、全体所要時間127.26秒。

| 課題 | 初回 | 修正回数 | 最終 | API入力 / 出力tokens | 所要時間 秒 |
|---|---|---:|---|---:|---:|
| C uint32解析 | 不合格 | 3 | **不合格** | 2,399 / 835 | 18.18 |
| C++ 自己参照append | 合格 | 0 | **合格** | 157 / 206 | 5.00 |
| POSIX write | 不合格 | 1 | **合格** | 911 / 637 | 11.47 |
| Rust prefix sum | 合格 | 0 | **合格** | 117 / 114 | 2.39 |
| AArch64 sum | 不合格 | 3 | **不合格** | 2,676 / 1,096 | 21.54 |
| NEON SAD | 不合格 | 3 | **不合格** | 3,555 / 1,595 | 30.85 |
| NEON dot | 不合格 | 3 | **不合格** | 4,785 / 1,930 | 37.82 |

APIトークンは各応答のusageの合計で、修正時に再送する履歴も含む。所要時間は各課題のAPIと独立検証を含む壁時計時間。
各修正の候補コード・API使用量・時間・診断・合否を保存している。初回からやり直す追加実験は行わず、3回を超える修正もしていない。

| 課題 | 修正履歴と解消した問題 | 最終的に残った問題 |
|---|---|---|
| C解析 | 初回コンパイル失敗→修正1で `<stddef.h>` を追加しコンパイル成功→修正1〜3は契約検査失敗 | NULL出力ポインタを成功扱いする処理が残った |
| C++ | 初回で98,020ケース＋SIZE_MAX境界、ASan/UBSan、libstdc++ debug modeを通過 | 固定テストで検出した問題なし |
| POSIX | 初回 `SSIZE_MAX` 未定義→修正1で `<limits.h>` 追加→短いwrite/EINTR/EAGAIN/0/hard errorと実際の非同期pipe/EPIPEを通過 | 固定テストで検出した問題なし |
| Rust | 初回で5,000入力列のi64参照結果と途中オーバーフロー境界を通過 | 固定テストで検出した問題なし |
| AArch64 | 全4候補で参照結果のassert失敗。コメントやゼロ拡張処理の変更はあった | n=0分岐がx3初期化より前にあり、未初期化値を返す根本原因が残った |
| NEON SAD | 初回コンパイル失敗→修正1で `<stdlib.h>` を追加→修正1〜3は保護境界でSIGSEGV | unsignedの `n-16` アンダーフローを修正できなかった |
| NEON dot | 全4候補でコンパイル失敗。intrinsicの修正は別の型不整合を追加した | 多項式/符号付き乗算とベクトルのlane幅の混同が残り、実行検証へ到達せず |

合格した3課題は独立テスト通過を確認した。残る4課題を合格扱いにはしていない。
特に、ヘッダ追加のようなコンパイル診断に直結する修正はできたが、期待値を伏せた一般的な実行失敗分類だけでは、NULL契約や境界・未初期化の原因を十分に絞れなかった。
「モデルが修正コードを返したこと」と「独立検証に通ったこと」を別の状態として扱うPoCになっている。

### 記録と残課題

実行記録は `logs/repair/20261027T084214958944Z/`。
`report.json` に全体と各課題の初回/最終合否・修正回数・API使用量・時間・ハッシュを保存。
`<課題>/attempt-0`〜`attempt-3` に全メッセージ、生応答、候補、隔離条件、生診断、モデル向けfeedbackを保存。
`analysis.json` は終了後の原因分析で、最終不合格の課題でもヘッダ不足だけが解消した点を区別して記録した。元の採点結果やモデル出力は変更していない。
生ログ・候補コードは `logs/` としてGit管理対象外。

サーバーのID、イメージ、設定ハッシュ、HostConfigハッシュ、StartedAt、healthy状態を実行前後で照合し、変更なしを確認した。
固定した課題・独立テスト・検証実装のハッシュも実行中を通じて一致した。
既存0.5BベンチマークやPhase 3の初回評価結果も上書きしていない。

次の改善候補は、期待値や参照コードを開示せず、失敗した公開契約の分類（NULL/範囲/ABI等）や候補コード自身の静的診断をより具体的に返すこと。
採点テストの正解を説明として流用する方式は使わない。繰返し同じ不具合が残る場合の停滞検出も未実装。
今回の結果は1回の7課題であり、合格率改善の一般化、全入力の形式的正しさ、Arm実機動作、VM相当の敵対的コード隔離は未検証。

## Repair Loop v2：同一モデルの診断分離

既存baseline `logs/repair/20261027T084214958944Z/` と既存の独立テストを維持して、診断分離方式を追加した。
入口は `scripts/repair-coder-diagnostic.py`、新規モジュールは `evaluation/coder/diagnostic/`。
既存 `scripts/repair-coder.py`、`evaluation/coder/repair/`、独立テスト、推論サーバー、ホスト設定は変更していない。

- [Phase A：既存20候補の失敗・遷移分析](docs/repair-loop-v2-analysis.md)
- [Phase B/C：比較条件、結果、事後評価、コスト、残課題](docs/repair-loop-v2-comparison.md)
- [実装の境界・記録形式・再現手順](evaluation/coder/diagnostic/README.md)

診断には公開仕様、当該候補、従来フィルター済み情報だけを渡した。事前分析で判明した具体的な正解・原因はプロンプトに埋め込んでいない。
診断役は新しい会話で仮説と方針だけを生成し、生成役のコードを独立テストで判定した。
各13修正について、診断仮説・方針・実差分・独立判定・事後評価を `revision.json` 等へ構造化。
事後評価はモデルの自己申告ではなく、差分と実測compiler/test記録に基づく。固定処理の評価に加え、終了後にCodexによる35仮説の証拠ベースの補足レビューも保存した。

| 比較 | baseline | diagnostic |
|---|---:|---:|
| 同じ初回候補 | 2/7合格 | 再検証で2/7を再現 |
| 最大3修正後 | **3/7合格** | **3/7合格** |
| 初回生成を含む比較用API tokens | 21,013 | **43,653（約2.08倍）** |
| 初回生成を含む比較用時間 | 127.26秒 | **213.21秒（約1.68倍）** |

diagnosticで今回実際に消費したのは40,544 tokens・181.77秒で、比較用の値には再利用した初回生成の3,109 tokens・31.44秒を加えている。
診断役単独の追加コストは **14,848 tokens・75.39秒**。残る差分は生成役へ渡す診断内容や生成コードの変化等を含む。
baselineは過去runのため時間比較には時刻・熱状態等の未統制要因があり、7課題で一般化しない。

C++・POSIX・Rustは最終合格。CのNULL出力契約、AArch64のゼロ要素時の未設定戻り値、NEON SADの境界、NEON dotのintrinsic型不整合は未解決だった。
診断に正しい部分があっても、修正コードの独立検証が通らなければ不合格を維持した。診断が提案したcompiler制約緩和も適用していない。

新規ログは `logs/repair-v2/20261027T091658139087Z/`。`report.json`、`baseline-transitions.json`、各課題の`attempt-*`、`independent-review.json` に保存。
既存ログの上書きはなく、モデル・生成コード・生ログはGit管理対象外。

```sh
python3 -m unittest discover -s evaluation/coder/diagnostic -p test_diagnosis.py
python3 -m unittest discover -s evaluation/coder/repair -p test_feedback.py
python3 scripts/repair-coder-diagnostic.py
```

再実行も新しいrunディレクトリを使用する。サーバーのfingerprint、固定テスト、初回候補の再現条件等が違えば停止する。
次は、正解を開示しない失敗分類・候補コードの経路追跡・安全なcompiler型情報・コメントだけの変更や失敗コード回帰の検出を検討する。

## 作業の進め方

`AGENTS.md`に従い、調査、計画、承認後の実装、検証の順に進める。
次の構築作業には、調査と計画の承認を経て着手する。GitHubへのpushは明示的な許可があるまで行わない。

## AArch64開発環境への案内

開発環境 Phase 1として、既存検証イメージを親とするAArch64開発用子イメージを追加した。
LLVM/Clang/LLD 21.1.8、QEMU virt/PL011、GDB、Rust no_std、NEONのスモークテストはPASS。
起動コード・UART・リンカは環境検証専用で、AceIS/Abissの正式実装とは区別する。
構成、固定バージョン、保護確認、失敗履歴、再現手順と未検証範囲は[開発環境の記録](docs/dev-aarch64.md)を参照。
