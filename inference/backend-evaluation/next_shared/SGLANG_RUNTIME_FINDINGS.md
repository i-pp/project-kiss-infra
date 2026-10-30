# SGLang gfx1151 runtime follow-up

公式完成imageは存在する。AMD Verified Publisherの`rocm/sgl-dev:v0.5.22-rocm724-gfx1151-20261029`を公開Docker Hubで確認した。固定候補は`rocm/sgl-dev@sha256:be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230`、linux/amd64。[公式tag JSON](https://hub.docker.com/v2/repositories/rocm/sgl-dev/tags/v0.5.22-rocm724-gfx1151-20261029)は圧縮合計13,667,503,350 bytes（Hub表示12.73GB）を返す。展開後容量は未確認。過去の「完成image未発見、自前build必須」という前提は更新する。

[公式AMD GPU docs](https://docs.sglang.io/docs/hardware-platforms/amd_gpu)はgfx1151専用nightlyを案内し、Instinct/CDNA用imageと区別している。[固定imageの履歴](https://hub.docker.com/layers/rocm/sgl-dev/v0.5.22-rocm724-gfx1151-20261029/images/sha256-be68e8ebeb73195116dc3506b3fc96616f3668a5495f7bcb27ac6a30d2bae230)でgfx1151、ROCm7.2.4、torch2.9.1、Triton3.5.1、AITER固定commit、AITER無効、compressed-tensors0.15.0のbuild指定を確認した。これらは実インストール版の検査ではない。

SGLang v0.5.22の固定source候補は`baa9befa381511cd4d56f83980951e5a45fffc6d`。[recipe](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/docker/rocm-gfx1151.Dockerfile)と公開image履歴は整合するが、`COPY .`のexact commitを示すsource labelは公開履歴に無かった。tag名だけで完全一致とは判定しない。registry manifestを直接読む限定確認はUNAUTHORIZEDだったため、image config JSONのlabels確認は未完。layer/binary取得やtoken発行はしていない。[SGLang source license](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/LICENSE)はApache-2.0。image全体のbase/依存licenseは別物で、全体license確認済みとはしない。

Next共用量子化は引き続きsource上の候補である。[HIP選択](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/python/sglang/srt/layers/quantization/compressed_tensors/compressed_tensors.py)はWNA16 MoEをTritonへ回し、[実装](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/python/sglang/srt/layers/quantization/compressed_tensors/schemes/compressed_tensors_wNa16_moe.py)は当該方式を持つ。[Qwen3Nextモデル](https://github.com/sgl-project/sglang/blob/baa9befa381511cd4d56f83980951e5a45fffc6d/python/sglang/srt/models/qwen3_next.py)も存在する。MoEだけINT4/group32、通常linearをBF16に保つcyankiwi checkpointを使う方針は維持できる。ただしimage commit・実依存・GDN/INT4 JIT・ロード資源の実機PASSではない。

次は固定digest imageの取得を個別承認し、人間ホスト側でsource/package実版と展開容量を確認してoperator recordへ記録する。既存の有限runnerの標準seccomp/private IPC/nonroot/read-only/internal owned-IP方針を維持し、公式起動例のunconfined/host IPCをコピーしない。自前buildはsource不一致等が判明した場合の代替で、既存固定recipe/base候補を使えるが完成容量はunknown。新imageの使用を即READYとせず、同じ1POST試験の前提を揃える。

今回のpull/build/run/重み取得/推論/サービス変更はすべて0。詳細は[metadata](official-image-metadata.json)。
