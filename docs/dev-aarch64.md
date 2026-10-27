# AArch64開発環境 Phase 1

2026-10-27に構築・実機検証。既存の`project-kiss-code-eval:20261027`を共通の親に、開発用子イメージを1つ追加した。ホストのパッケージ、sysroot、ROCm、Docker設定は変更していない。

`dev/aarch64/smoke/`の起動コード、UART、リンカ、SIMD関数は**環境検証専用**。AceIS/Abissの正式な起動方式、ABI、ランタイム、デバイスドライバ、言語仕様ではない。

## イメージとバージョン

| 対象 | 実測値 |
|---|---|
| 親 | `project-kiss-code-eval:20261027` |
| 親ID | `sha256:d7db62585e135c5ef03be789fbf042ffebae4caa8482dd7aeb1d8e3b4cf0026c` |
| 子 | `project-kiss-aarch64-dev:phase1-20261027` |
| 子ID | `sha256:ea44c479096d2aa12f67e8bf182872afaf41706a35b4b04556529e51a02beb65` |
| Ubuntu snapshot | `20261027T090000Z`、resolute / updates / security |
| Clang / LLVM / LLD / FileCheck | **21.1.8**、Ubuntu `1:21.1.8-6ubuntu1` |
| Rustc / Cargo | **1.93.1**、Rustc内部LLVMも**21.1.8** |
| rustup / ターゲット | 1.29.2 / `aarch64-unknown-none` |
| QEMU system | 10.2.1、Ubuntu `1:10.2.1+ds-1ubuntu3.3` |
| gdb-multiarch | 17.1、Ubuntu `17.1-2ubuntu1` |
| CMake / Ninja / dtc | 4.2.3 / 1.13.2 / 1.7.2 |
| 親から継承したGCC / クロスGCC / QEMU user | 15.2.0 / 15.2.0 / 10.2.1 |
| Python | 3.14.4 |

親IDは各操作の前に検査し、テスト時は親の全RootFSレイヤーが子の先頭に含まれることも検査する。既存タグへの開発イメージの上書きは拒否する。

`/opt/llvm21/bin`のコマンド別名、`CC/CXX/LD/LLVM_DIR`、CMakeツールチェーンを21に固定。Rustのリンクも`/usr/bin/ld.lld-21`を明示する。バージョン・実体パス・LLVM 22パッケージ不在をテストする。ホストのLLVM 22はマウントしない。

`versions.lock.json`に直接依存の版、snapshot、公式RustメタデータとインストーラーのSHA-256を保存。イメージ内の`/opt/kiss-aarch64/packages.tsv`には推移依存を含む全パッケージ版、`package-uris.txt`には取得計画を保存した。各テストのログにも複製する。Rust本体とbare-metal用coreは同じ公式配布版を使用する。親にあるディストリビューション版Rustは共通レイヤーに残り、開発用PATHでは公式版を使う。

## 隔離と既存環境の保護

独立したComposeプロジェクト`project-kiss-dev`のワンショットサービスのみを使う。

- 実行ユーザーUID/GIDを動的に渡す。本機は`1000:973`。
- `network_mode: none`、ポートなし、GPU/KVM/Dockerソケットなし。
- rootfsと検証ソースは読み取り専用。モデル、ホストsysroot、ホーム、認証情報はマウントしない。
- 書込先は新設した`.cache/dev-aarch64/`、`logs/dev-aarch64/`と上限256MiBの`/tmp`。
- capability全削除、no-new-privileges、標準seccomp/AppArmorを維持。ptrace権限追加なし。
- CPU 2、RAM 4GiB、swap追加なし、PID 256、core dump禁止、通常ファイル上限128MiB。
- コマンドごとに時間上限と出力上限1MiB。QEMU通常起動/GDBは各30秒、Cargoは120秒、全体は600秒。
- Dockerログも2MiB×2本に制限する。テスト用に作った一時コンテナだけを終了・削除する。
- 既存イメージ・コンテナ・ログの削除、prune、サービス再起動は行わない。

開始前に465ファイルのSHA-256、モデルのサイズ/mtime、既存コンテナの設定・起動時刻・状態、既存イメージID、キャッシュ6件のID、ネットワーク一覧、ホストのパッケージDB・主要設定の指紋を記録した。モデル本体18GBの全ハッシュは今回再計算していない。

READMEは承認された追記のみ許可し、元の全バイト列が先頭に残ることを確認する。それ以外の保護対象はSHA-256で照合する。既存Repair Loopと独立テストは変更していない。推論APIへの追加実験も実施していない。

## 検証結果

最終スモークログ：
`logs/dev-aarch64/20261027T112000Z/test-120512610272/`

| 項目 | 結果 | 根拠 |
|---|---|---|
| 隔離・資源制限 | PASS | 非root、CapEff=0、NoNewPrivs=1、Seccomp=2、loのみ、GPUなし、cgroup上限の実測 |
| ツールチェーン統一 | PASS | LLVM/Clang/LLD 21.1.8、Rust内部LLVM 21.1.8、LLVM 22パッケージなし |
| C/ASMクロスビルド | PASS | CMake/Ninja→Clang 21→LLD 21、AArch64 ELFのヘッダー・セグメント・入口検査 |
| LLVM IR・逆アセンブル | PASS | IR→bitcode→IR、llc、FileCheck、llvm-objdumpでNEON命令を検査 |
| QEMU virt | PASS | 実際のmachine/CPU/accelerator/device一覧、`virt-10.2` / Cortex-A53 / TCGでELF起動 |
| DTB・PL011 UART | PASS | DTBからUART `0x09000000`とRAM `0x40000000`を検査、UARTログ保存 |
| GDB | PASS | UNIXソケット、初期停止、2か所のブレークポイント、ステップでPC移動、レジスタ・既知メモリ値確認 |
| Rust no_std | PASS | Cargo locked/offline、core使用、LLD 21でリンクしUART出力 |
| NEON | PASS | 4,128組×SAD/dotの独立スカラー比較、別途2件の既知値。長さ0～257、オフセット0～3要素、4パターン |
| 既存環境保護 | PASS | 465ファイル等の照合、推論サーバーhealthy・起動時刻維持、既存イメージ/キャッシュID保持 |

最終試験は2.156秒、cgroupメモリピーク67,620,864 bytes。これは小規模スモークの実測であり、大きなコンパイラのビルド容量や速度の保証ではない。

UART出力：

```text
C_ASM PASS EL1 BSS DATA SP16
NEON PASS cases=4128
SMOKE DONE

RUST PASS no_std core EL1 FP
SMOKE DONE
```

QEMUのゲストRAMは256MiB。DTB用に先頭2MiBを予約し、ELF入口は`0x40200000`。EL1だけを対象とし、BSS初期化、データ配置、SPの16バイト整列、FP/AdvSIMD許可を検証する。テスト終了マーカーの取得後は制御側がQEMUを終了する。ゲストはsemihostingを使わない。

## 構築時・検証時に判明した問題

失敗ログもすべて保存し、後のPASSで上書きしていない。

1. 初回ビルドは親にCA証明書ストアがなくTLS検証に失敗した（`build.log`）。ホストの検証済みHTTPSでSHA-256固定の通常のUbuntu CAパッケージ137,978 bytesを取得し、新しい子の中で標準Mozillaルートをブートストラップした。TLSやAPT署名検証は無効にしていない。ホストへの証明書追加はない。
2. Docker localログドライバーで`max-file=1`と既定圧縮の組合せが拒否された（`test-115909564755`）。上限2MiB×2本に修正した。
3. QEMU `-chardev help`にはmachine指定が必要だった（`test-115922949333`）。実際に`-machine virt-10.2`を指定して機能列挙した。
4. 最初のUART起動はC/ASM確認後、SIMD試験で停止した（`test-115941929039`、`test-120147637139`）。GDBで`ESR_EL1=0x96000021`、`ELR_EL1=0x402011a0`、`FAR_EL1=0x402112d1`、該当命令`ldr s3, [x11], #4`を確認。MMU無効時のDeviceメモリへの非整列アクセスと整合する証拠が得られた。Cコンパイルを`-mstrict-align`に変更し、非整列オフセットを含む同じテストを通した。ホストや権限、CPUモデル、テストの期待値は変更していない。
5. 最初の全PASS試験では読み取り専用`/opt/cargo`へのキャッシュ書込警告があった（`test-120332198876`）。Cargoの書込先を専用`/work/cargo-home`へ移し、最終試験で警告が解消した。

MMU無効時の属性は[Arm公式資料](https://documentation-service.arm.com/static/63a43e333f28e5456434e18b)を確認した。Clangの整列指定は[公式マニュアル](https://clang.llvm.org/docs/UsersManual.html)に従う。この制約は一般的なNormal RAM上のコードの実行条件とは異なる。

## 再現手順

すべてリポジトリルートから、通常のDocker利用ユーザーで実行する。ホストへのパッケージ追加は不要。

既存子イメージで再検証する場合：

```sh
DEV_RUN="logs/dev-aarch64/$(date -u +%Y%m%dT%H%M%S%NZ)"
sh scripts/dev-aarch64.sh snapshot "$DEV_RUN"
sh scripts/dev-aarch64.sh config
sh scripts/dev-aarch64.sh test "$DEV_RUN"
sh scripts/dev-aarch64.sh verify "$DEV_RUN"
```

構築を再現する場合、既存タグは上書きせず新しいタグを指定する。親イメージは保存済みのものを使う。固定版が取得できない場合は停止する。

```sh
DEV_RUN="logs/dev-aarch64/$(date -u +%Y%m%dT%H%M%S%NZ)"
export DEV_IMAGE="project-kiss-aarch64-dev:rebuild-$(date -u +%Y%m%dT%H%M%S)"
sh scripts/dev-aarch64.sh snapshot "$DEV_RUN"
sh scripts/dev-aarch64.sh build "$DEV_RUN"
sh scripts/dev-aarch64.sh test "$DEV_RUN"
sh scripts/dev-aarch64.sh verify "$DEV_RUN"
```

ビルドだけが公式配布元への通信を使い、開発用実行コンテナは通信禁止のまま。Ubuntu snapshotの保存期間などによって将来取得できなくなる可能性はある。同一イメージIDでの再実行にはローカル保存済みイメージを使う。ソースからのビルドはツール・依存の固定を目的とし、時刻を含むイメージ全体のビット単位一致までは保証しない。

対話シェル：

```sh
sh scripts/dev-aarch64.sh shell
clang --version
llvm-config --version
rustc -vV
```

実行したコンパイル・QEMU・GDBコマンドは各`report.json`の`commands`に保存する。生成した`gdb.cmd`、リンカ、ELF、IRは同じrun名の`.cache/dev-aarch64/`以下に残す。GDBはQEMUと同一コンテナ内でUNIXソケットに接続する。`-s`によるTCP 1234公開は使用しない。

## ディスク使用量

| 対象 | 実測値 |
|---|---|
| 子イメージの論理サイズ（親を含む） | 3,792,964,329 bytes、約3.53GiB |
| 共有する親の論理サイズ | 1,746,838,498 bytes、約1.63GiB |
| 子の追加レイヤー分 | 2,046,125,831 bytes、約1.91GiB |
| 主要取得量 | APT 162,537,504、Rust components 131,721,196、rustup 21,139,856 bytes。索引等は別 |
| ホストFS使用量の増分 | 3,748,872,192 bytes、約3.49GiB。作業中の他のホスト活動も含む観測差分 |

DockerのImagesとBuild Cacheは共有領域を含むため単純加算しない。既存キャッシュ6件は保持し、新規キャッシュが追加されている。pruneは実行していない。検証成果物・全失敗ログは数MiBで、Git対象外。正確な最終サイズはrunの`summary.json`に保存する。

## PoC開発へ進む準備状況

| 状態 | 範囲 |
|---|---|
| READY | 固定LLVM 21によるIR生成・AArch64コード生成・リンク・逆アセンブル |
| READY | C/ASMとRust no_stdの小規模ELFをQEMUで実行しUART/GDBで観察 |
| READY | NEONカーネルを別のスカラー実装・既知値と比較する最小の足場 |
| SKIP／未検証 | AceIS/Abiss本体のソース統合、LLVM C++ APIを使ったコンパイラ本体のビルド |
| SKIP／未検証 | 正式ABI、EL2/EL3、MMU・Normal RAMマッピング、例外処理、割込み、SMP、実機AArch64 |
| SKIP／未検証 | libc、アロケータ、Rust alloc、外部crateを必要とするプログラム |

次はAceIS/Abissの最小言語仕様・エラー条件と、SIMD関数の境界・整列・オーバーフロー契約を確定し、この足場に独立テストを追加する。一般の非整列ロードを直接検証する場合は、Normal RAMを設定する正式な起動・メモリ仕様を先に決める。今回はそこまで実装せず、追加LLM性能実験も行わない。

参照：[QEMU 10.2.1 virt](https://raw.githubusercontent.com/qemu/qemu/v10.2.1/docs/system/arm/virt.rst)、[QEMU 10.2.1 GDB](https://raw.githubusercontent.com/qemu/qemu/v10.2.1/docs/system/gdb.rst)、[Rust bare-metal target](https://doc.rust-lang.org/rustc/platform-support/aarch64-unknown-none.html)、[Ubuntu snapshot](https://snapshot.ubuntu.com/)。
