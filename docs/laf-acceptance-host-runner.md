# Isolated EVO container acceptance runner

The reviewed candidate now has an actual host-only integration path for its v2
model manager, dedicated persistent engine store, and Core container. It was run
on EVO-X3 with two explicitly named small test models. This is not a portable
installer, complete Quick Start, production selection, or target-model acceptance.

Safe local inspection from the candidate source directory:

```sh
python3 -B -m inference.acceptance_container.run
LAF_MODEL_STATE_DIR=/home/y-ooya/laf-expanded-acceptance-20261108/integration-runtime/registry \
  python3 -B -m inference.local_platform.cli model list
LAF_MODEL_STATE_DIR=/home/y-ooya/laf-expanded-acceptance-20261108/integration-runtime/registry \
  python3 -B -m inference.local_platform.cli model status
python3 -B -m unittest -v \
  inference.acceptance_container.test_engine \
  inference.acceptance_container.test_run \
  inference.acceptance_container.test_store
```

The first command is plan-only. Mutation requires the explicit `--execute` flag,
existing source/license/digest evidence, the exact named EVO resources, and owner
authorization for the maintenance. It must not be run as a generic launch script.
A prior journal prevents replay. The narrowly scoped `--resume-after-download`
path accepts only the observed first audit-format failure after both downloads
were confirmed, no pending model operation and successful original restoration.
It retains the first journal and cannot invoke install/pull.

Core still has no Docker or host PID authority. The host adapter derives the
endpoint from exact fixed container image/name/owner, mounts, devices and limits;
it does not accept a caller-supplied URL. Acquisition used the existing standard
bridge with no published ports, then that container was removed. Runtime pairs
were created only on the existing Internal=true network. There were no host
network, firewall, driver or security-setting changes.

The runtime client is outside Core and connects through a private owner-only UDS
bind. Core contacts Ollama by private HTTP. The existing host NPU agent is mounted
through its private read-only socket directory. This is not a PC-to-PC TCP test.

Ollama0.40.15 produces two exact manifest-v2 symlinks. The auditor accepts only
catalog-derived literal relative targets into the verified store and rejects all
other symlinks, hardlinks and special files. Every descriptor blob and the raw
manifest blobs are checked for exact SHA256 and bytes. Store snapshots include
hashes, links, inode/device and mtime; all19 entries matched after both runtime
pair deletions/recreations. The manager registry was unchanged.

First-run auditing stopped safely after both successful pulls because the initial
auditor had rejected every symlink. The original service and scheduler were
restored before fixing the auditor. The reviewed resume reused the same completed
downloads, performed no install/pull, and passed the actual inference/persistence
stages. No journal was deleted and no uncertain download was replayed.

Original service unit/drop-in/config/source selection was not edited. Final
verification confirmed ready/fault=null/queue0/active=null, Flash resident,
coder-next selected, the same production provider and unchanged configuration
hashes. NPU retained its original process. Test containers were removed; the
~503MB dedicated model store and its private registry remain for future use.

The evidence package contains the exact scope, raw journals/resources/engine logs,
model provenance snapshots, hashes, independent reviews and216 passing tests.
Those tests include fake providers; actual small-model GPU inference and two NPU
requests are separately evidenced. No publication, push, target model container
acceptance, clean-host provisioning, long soak, pressure or crash test is claimed.
