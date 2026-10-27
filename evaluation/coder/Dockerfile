FROM ubuntu:26.04@sha256:19fcd1bf268f02b60aca3bd30bd8a6d9a11759a430e32921833e65f16d87348a

# Host packages are untouched. Refuse an unexpectedly large package download.
RUN apt-get update \
 && apt-get --print-uris --yes --no-install-recommends install \
      build-essential rustc gcc-aarch64-linux-gnu libc6-dev-arm64-cross \
      binutils-aarch64-linux-gnu qemu-user python3 > /tmp/package-uris \
 && awk '$3 ~ /^[0-9]+$/ {bytes += $3} END {print "Package download bytes:", bytes; if (bytes > 1073741824 || bytes == 0) exit 1}' /tmp/package-uris \
 && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      build-essential rustc gcc-aarch64-linux-gnu libc6-dev-arm64-cross \
      binutils-aarch64-linux-gnu qemu-user python3 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
