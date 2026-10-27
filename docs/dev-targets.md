# x86-64 / AArch64開発環境 Phase 2C

2026-10-27に構築・実行。LLVM 21の共通C++ APIから両ターゲットのELFオブジェクトを生成し、リンク・実行できる最小経路を確認した。AceISのフロントエンド、独自バックエンド、正式ブート仕様の完成を意味しない。

## 構成と固定版

| 項目 | 採用・実測値 |
|---|---|
| 親 | `project-kiss-aarch64-dev:phase1-20261027` |
| 親ID | `sha256:ea44c479096d2aa12f67e8bf182872afaf41706a35b4b04556529e51a02beb65` |
| 新規子 | `project-kiss-x86-dev:phase2c-20261027` |
| 子ID | `sha256:0a456a372f24c98967fd525b76d67f36c1abab02034585d2eaa4bd82642b35c4` |
| Clang / Clang++ / LLVM / LLD | **21.1.8**、親から継承。再インストールなし |
| QEMU system x86 / AArch64 | **10.2.1**、Ubuntu `1:10.2.1+ds-1ubuntu3.3` |
| GDB / CMake / Ninja | 17.1 / 4.2.3 / 1.13.2 |
| Ubuntu snapshot | `20261027T090000Z` |
| 新規依存 | qemu-system-x86、必須のSeaBIOS・iPXE。推奨パッケージは導入しない |

親のIDを各操作前に照合し、テスト前にはRootFSレイヤーの継承も照合する。既存タグへの上書きは拒否する。子内APTは固定snapshot、署名/TLS検証有効、`--no-upgrade`、取得上限256MiB。既存LLVM/Rustやホストのパッケージは変更しない。

依存全版は`targets/packages.tsv`、取得計画は`package-uris.txt`、主要取得量は`download-bytes.json`に保存する。LLVM 22パッケージ不在、実行ツール21.1.8、LLVM C++ヘッダーの21.1.8、`LLVM_DIR`を検査する。Rustは既存AArch64回帰時だけ使用し、版・ターゲットとも既存構成を維持する。

## 共通部分とターゲット依存部分

`dev/common/llvm-api-smoke.cpp`の同じ小プログラムを使用する。共通のi64加算IRを構築し、`verifyModule`、TargetMachine、ELFオブジェクト出力を検証する。IRの加算には`nsw/nuw`を付けず、2^64剰余を契約とする。

ターゲット依存はtriple、CPU/features、TargetMachineとそのDataLayout。選択はx86-64 / SSE2とCortex-A53 / strict-alignの2分岐のみ。CMakeはLLVM共有ライブラリ`LLVM-21`へリンクする。

生成した同じ加算関数を、共通の既知値5件（通常値、繰上がり、符号境界、64ビット周回など）で確認する。x86-64はLinux ELFのネイティブ実行とbare-metal QEMU、AArch64は既存の環境検証用start/UARTを読み取り専用で再利用してQEMU実行する。既存AArch64スモーク実装をリファクタリングしない。

スカラー参照は`dev/common/reference.c`の別翻訳単位で、ベクトル化を無効にしてコンパイルする。新しいSSE/AVXテストでは符号なし32ビット加算、長さ0～257、オフセット0～3要素、3入力パターン、末尾と出力カナリアを比較する。各ISA 3,096ケース。

## x86-64起動とデバッグ

`dev/x86_64/smoke/`は**環境検証専用**であり、AceIS/Abissのブート仕様・ABI・正式ランタイムではない。

- Clang/LLD 21でELF64をリンクし、llvm-objcopyでMultibootのアドレス指定ヘッダー付きflatイメージへ変換する。
- QEMUのMultiboot ELF読み込み経路はx86-64 ELFを拒否するため、ELF64直接起動を前提にしない。ELF64は逆アセンブルとGDBシンボルに使う。[QEMU 10.2.1実装](https://raw.githubusercontent.com/qemu/qemu/v10.2.1/hw/i386/multiboot.c)
- 32ビットprotected modeからlong modeへ移行し、低位1GiBをidentity mapする最小ページテーブルを使う。1CPU、ゲストRAM128MiB、割込み無効。一般のメモリ管理・例外処理ではない。
- `pc-i440fx-10.2` / `qemu64` / TCGを機能一覧と実行で確認した。KVMやCPU機能の強制追加は使わない。
- COM1出力を取得し、BSS・データ・16バイト整列スタック、LLVM API生成関数、SSE2を確認する。
- QEMU/GDBは同一コンテナ内のUNIXソケットで接続。リセット停止、64ビット入口、ブレークポイント、ステップ、レジスタ・既知メモリ値を検査する。TCPポートやSYS_PTRACEは追加しない。

## 実効隔離

Composeは独立した`project-kiss-dev-x86`プロジェクト。新子イメージの検証と、旧親イメージを使うAArch64回帰を順に実行する。

| 項目 | 実測・設定 |
|---|---|
| ユーザー | 非root、本機UID/GID `1000:973` |
| 権限 | CapEff=0、NoNewPrivs=1、Seccomp=2、`docker-default (enforce)` |
| 通信 | `network_mode: none`、loのみ、外向き接続失敗を実測 |
| デバイス | GPU、KVM、Dockerソケットなし |
| 読み取り専用 | rootfs、共通/x86/AArch64ソース |
| cgroup | CPU 2、RAM 4GiB、追加swap 0、PID 256 |
| ファイル等 | core 0、通常ファイル上限128MiB、/tmp上限256MiB |
| 実行上限 | 各コマンドの時間上限と出力1MiB、各サービス全体600秒、Dockerログ2MiB×2本 |

新設した`.cache/dev-x86_64/`と`logs/dev-targets/`だけを成果物・ログの書込先に使う。旧AArch64の作業キャッシュ・Cargoキャッシュ・過去ログには書き込まない。モデル、ホストsysroot、ホーム、認証情報はマウントしない。

## 実行結果

ログroot：`logs/dev-targets/20261027T133548Z/`

最終テスト：`test-20261027T134756351193Z/`

| 項目 | 結果 | 根拠 |
|---|---|---|
| 実効隔離 | PASS | UID/capability/seccomp/AppArmor、cgroup、read-only、loのみ、外部通信失敗 |
| LLVM 21共通C++ API | PASS | 共通IRからX86/AArch64のオブジェクトを生成、e_machine・IR・逆アセンブル記録 |
| x86-64 ELF/リンク/ネイティブ | PASS | LLD 21、生成関数の既知値5件 |
| x86-64 QEMU起動 | PASS | Multiboot→long mode、COM1、生成関数・SSE2・完了マーカー |
| x86-64 GDB | PASS | RIP移動、CR0/CR3/CR4、既知メモリ、3地点の停止 |
| AArch64 API生成ELF実行 | PASS | 共通関数の既知値5件、LLD 21、Cortex-A53でUART出力 |
| 既存AArch64回帰 | PASS | 旧スクリプト・旧イメージの8項目全てPASS |
| 既存環境保護 | PASS | 67ソース、644ログ、モデル情報、元イメージ/キャッシュID、コンテナ状態等を照合 |

SIMDは実機ネイティブとQEMUを分ける。

| 環境 | SSE2 | AVX2 | AVX-512F |
|---|---|---|---|
| 実機上のコンテナ | PASS、3,096ケース | PASS、3,096ケース | PASS、3,096ケース |
| QEMU qemu64 | PASS、3,096ケース | SKIP | SKIP |

実機はAMD Ryzen AI MAX+ 395。実行時CPUIDでSSE2/AVX/AVX2/AVX512F/XSAVE/OSXSAVEを確認し、XGETBVのXCR0は`743`（`0x2e7`）。AVX系の状態ビットを確認した後に該当関数を呼び出し、比較成功後だけPASSを出力する。逆アセンブルでSSE2の`paddd`、AVX2のYMM、AVX-512FのZMM命令も確認した。**AVX-512全サブセットの検証ではなくFを使う整数加算の検証**。

QEMUではAVX/AVX2/AVX512F/XSAVE/OSXSAVEがなく、XCR0は0。そのためAVX2/AVX-512Fは理由付きSKIPとし、実行しない。ホストCPUの対応をQEMU対応として扱わない。小さな検証用ゲストはSSE状態だけを有効にしている。

初回のビルド・テストはFAILなし。CMakeは未導入の任意機能LibEdit/zstd/CURLを報告するが、今回の共有LLVM API・コード生成・リンクは成功しており、これらを追加導入しなかった。今後FAILが起きた場合も新しいrunへ診断を保存し、旧環境を変更して回避しない。

## 時間と容量

| 対象 | 実測 |
|---|---|
| 両ターゲット新規テスト | 4.352秒、cgroupメモリピーク154,820,608 bytes |
| 既存AArch64回帰 | 2.466秒、cgroupメモリピーク67,317,760 bytes |
| LLVM APIビルド・オブジェクト生成 | 1.834秒（上記の内数） |
| x86 QEMU機能確認・実行 | 0.287秒（上記の内数） |
| x86 GDB検証 | 0.353秒（上記の内数） |
| AArch64 APIビルド・実行 | 0.448秒（上記の内数） |
| パッケージ取得 | 12,682,460 bytes |
| 子イメージ論理サイズ | 3,886,129,191 bytes、親共有分を含む |
| 追加レイヤー論理サイズ | 93,164,862 bytes、約88.85MiB |

時間は小規模スモークの値で、コンパイラやCPUの性能比較ではない。ネイティブ実行は約1msの記録粒度で、ISA別の速度評価は行っていない。Dockerイメージとビルドキャッシュは共有領域を含むので合算しない。ホストFS使用量差分、成果物・ログ容量、全体の結果は`summary.json`に記録する。FS差分は作業中の他プロセスの活動も含む。

## 再現手順

リポジトリルートで通常のDocker利用ユーザーとして実行する。

```sh
TARGET_RUN="logs/dev-targets/$(date -u +%Y%m%dT%H%M%S%NZ)"
sh scripts/dev-x86_64.sh snapshot "$TARGET_RUN"
# 子イメージがまだない初回だけ実行
sh scripts/dev-x86_64.sh build "$TARGET_RUN"
sh scripts/dev-x86_64.sh test "$TARGET_RUN"
sh scripts/dev-x86_64.sh verify "$TARGET_RUN"
```

既存子イメージでの再検証ではbuildを省く。再ビルドする場合は既存タグを上書きせず、`DEV_IMAGE=project-kiss-x86-dev:<新しいタグ>`をexportしてから操作する。親IDや固定版が合わなければ停止する。

`test`は新規両ターゲット検証と、**既存`test-dev-aarch64.py`そのものを旧イメージで実行する回帰**を必ず順に実行する。各サービスの`report.json`にコマンド・時間・結果・失敗情報、`source-sha256.json`と`image.json`に識別情報を保存する。失敗時もログを残し、run全体を成功扱いしない。

## 既存環境への影響と未検証

旧AArch64ソース・イメージ・テストは変更していない。推論コンテナの設定・起動時刻・healthy状態を維持し、モデルのサイズ/mtime、既存ログのSHA-256、既存Dockerイメージ・キャッシュID、ホストのパッケージDB・主要設定を照合した。モデル18GBの全内容ハッシュは再計算していない。

変更は新規ファイル群とREADMEへの追記のみ。Gitへのステージング・コミット・pushは行わない。Webサイト、LLM性能実験、ホスト設定・ドライバ・BIOSは対象外。

未検証は、実際のAceIS言語処理、正式ABI/ブート、最適化の正当性、例外/割込み/SMP、AVX状態の保存復元、QEMUの別CPUモデルやAVX対応モデル、AVX-512F以外のサブセット、x86 bare-metal Rust、実機AArch64、大規模LLVMアプリケーション・任意LLVM機能。

次のPoCは、言語・整数演算・エラー・ABIの小さな仕様を先に定め、今回の共通IR→オブジェクト→独立実行検査の経路に載せる。検証用起動コードを正式設計へ昇格させる作業は含めない。

参照：[LLVM 21オブジェクト生成](https://releases.llvm.org/21.1.0/docs/tutorial/MyFirstLanguageFrontend/LangImpl08.html)、[QEMU 10.2.1 Multiboot](https://raw.githubusercontent.com/qemu/qemu/v10.2.1/hw/i386/multiboot.c)。
