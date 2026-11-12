# Supply an already-inspected immutable base through the reviewed build wrapper.
# No package installation or model/vendor bytes are included in this source image.
ARG LAF_CORE_BASE
FROM ${LAF_CORE_BASE}
WORKDIR /app
COPY inference/aceis_service/__init__.py inference/aceis_service/__init__.py
COPY inference/aceis_service/core.py inference/aceis_service/core.py
COPY inference/aceis_service/server.py inference/aceis_service/server.py
COPY inference/aceis_service/npu_bridge.py inference/aceis_service/npu_bridge.py
COPY inference/aceis_service/lifecycle.py inference/aceis_service/lifecycle.py
COPY inference/aceis_service/lifecycle_client.py inference/aceis_service/lifecycle_client.py
COPY inference/aceis_service/lifecycle_uds.py inference/aceis_service/lifecycle_uds.py
COPY inference/aceis_service/core_backends.py inference/aceis_service/core_backends.py
COPY inference/aceis_service/core_flash_worker.py inference/aceis_service/core_flash_worker.py
COPY inference/aceis_service/core_server.py inference/aceis_service/core_server.py
ENV PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
USER 1000:1000
ENTRYPOINT ["python3", "-B", "-m", "inference.aceis_service.core_server"]
