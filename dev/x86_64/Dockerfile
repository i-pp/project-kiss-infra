# SPDX-FileCopyrightText: 2026 I-plusplus Inc.
# SPDX-License-Identifier: LicenseRef-KOL-v1

# The host driver checks the immutable ID; never pull or overwrite the parent.
FROM project-kiss-aarch64-dev:phase1-20261027
USER root
COPY install.py versions.lock.json /tmp/kiss-x86-build/
RUN python3 /tmp/kiss-x86-build/install.py
USER 65534:65534
WORKDIR /work
