# 人間ホスト専用: 固定SGLang image取得・metadata記録

実装とCPU fake検証のみ完了。今回の実pull、Docker接続、image/container実行、GPU、推論、サービス変更はすべて0回。コード正本の配置とrootによる配置後CPU検証を終えてから、承認済みの人間ホスト端末で使う。

## 固定対象と最小コマンド

公式AMD image `rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230` のみ。公開tagは`v0.5.22-rocm724-gfx1151-20261029`、圧縮layer合計13,667,503,350 bytes。これは公開容量で、キャッシュを考慮した実通信量の実測ではない。展開容量は取得後のimage inspect Sizeに記録する。

配置先は `<PROJECT_ROOT>/inference/backend-evaluation/sglang_image_acquisition/`。固定sibling `host_trial/host_strata_trial.py` の既存HOST_CONTEXT guardを再利用する。現用private profileは、実在をrootが確認した `<PROJECT_ROOT>/agents/local_llm/.runtime/router-host-profile.json` のまま。

rootが実パスを入れて渡す人間端末の1コマンド:

```text
python3 -B <PROJECT_ROOT>/inference/backend-evaluation/sglang_image_acquisition/acquire_sglang_host.py --acquire-human-approved
```

`source`せず、対話端末へ`set -e`を貼らない。Python子プロセスが失敗して終了しても親の対話shellを終了させる命令はない。フラグ無しは固定対象のPREPARED表示だけ。任意image、URL、Docker context、socket、model、command、module pathのCLI引数はない。

## 実行範囲

- nonroot人間TTYかつ既存guardがHOST_CONTEXTと判定した場合だけ進む。Codex内からの実行やsudo/newgrp/group変更・認証設定を行わない。
- 固定`/usr/bin/docker --host unix:///var/run/docker.sock`でserver versionを読み、exact imageをinspectする。権限拒否/接続異常をnot-foundと混同せず停止。最初からexact imageがあればpull0回でmetadataだけ確認。
- exact imageが明示的に不存在の場合だけ、owner0600の永続intentを排他的に作って、固定digestの`pull --quiet`を最大1回、1800秒程度の上限で行う。空のprivate DOCKER_CONFIGを使い、既存credential helperやcontext、proxy等の環境を引き継がない。新しいcredentialは作らない。
- read-only metadataはimage ID、RepoDigests、linux/amd64、展開Size、Labels。source commit/dependency一致やlicense全体の内容検査・CPU container検査は後段であり、この完了判定には含めない。imageをrun/create/startしない。
- UUID別のowner0700 directoryへ0600のreceipt/intent/progress.jsonl/stdout/stderrを新規作成し、上書きしない。保存先はGit除外対象の `<PROJECT_ROOT>/agents/local_llm/.runtime/backend-runtime/sglang-image-acquisition/`。主要JSON/進捗/intentはfsyncする。進捗はステージと待機経過秒を表示する。

## 中断と再送禁止

Docker CLI timeout/SIGTERM/KeyboardInterruptでは、直接のCLIだけkill/waitする。これはdaemon側pullが止まった証拠ではない。`UNKNOWN_NO_RETRY`と永続intentを残す。CLIの終了すら未確認なら`clients_reaped=false`とする。通常SIGTERMは中断handlerへ流す。SIGKILLやホスト停止時のreceipt保存は保証しないが、先に作成したintentは残る。

別のrunが既存intentとimage不存在を観測したら新しいpullはしない。既存intentを消す復旧機能はない。imageが後で存在した場合は、再pullせずmetadataの読取照合だけでき、元intentは保全する。Dockerの既存imageやpartial layerを削除しない。失敗したらログを親へ返し、同じコマンドを盲目的に繰り返さない。

この取得処理は共有LLM生成lockを保持しない。30B unload/load、GPU device、namespace、container、サービス操作はない。Docker daemonによるimage展開のdisk/RAM負荷は発生し得るため、ホストの空き容量を事前に確認する。

## 検証

```text
python3 -B -m unittest discover -s <PREP_DIR>/sglang-image-acquisition -p 'test_*.py' -q
```

25件CPU fake PASS（独立レビュー24件＋配置前のdisk低容量回帰1件）、独立レビュー後の具体的指摘なし。timeout、Popen直後中断、Popen中断、kill拒否後wait、既存image pull0、権限拒否、永続intentによる二重pull防止、digest/platform/Size検証、0600、固定endpoint/環境を含む。実Docker/Popen/ネットワーク/GPUは呼ばない。

公開根拠: [固定tag JSON](https://hub.docker.com/v2/repositories/rocm/sgl-dev/tags/v0.5.22-rocm724-gfx1151-20261029)、[固定image履歴](https://hub.docker.com/layers/rocm/sgl-dev/v0.5.22-rocm724-gfx1151-20261029/images/sha256-be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230)。

追加の開始条件: project filesystemの空き64GiB未満ならpull intent作成前に停止する。この値はDockerRootDirが別filesystemの場合の空きや、展開量のhard quotaを保証しない。取得後にimage Sizeを記録し、未計測の容量を既知として扱わない。
