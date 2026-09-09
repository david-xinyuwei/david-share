# MiMo-V2.5-Pro serving stack on AMD MI300X (gfx942).
#
# Layers the verified delta on top of the AMD ROCm SGLang dev image. The delta is
# shipped as prebuilt trees so the CK page-64 / head-192 JIT objects do not have
# to be recompiled on first run. See STACK.txt for exact commits.
#
# Pinned by digest, not by tag: rocm/sgl-dev:v0.5.11-rocm720-mi30x-20260510 could
# be repushed upstream, which would silently change the base underneath a rebuild.
FROM rocm/sgl-dev@sha256:8f8dc55398855764d339ff4e2695b9c3c298704999051acaa1a67993fdff62e5

# SGLang fork carrying AMD commit 878fff156:
#   "bugfix(MTP): Fix HIP non-greedy EAGLE verification for MTP topk=1"
COPY runtime/sglang_0625 /sgl-workspace/sglang_0625

# AITER fork 3f4ab482a with composable_kernel af7118e34 plus ck_tile.patch,
# which adds the page_size=64 / head_dim=192 fmha_batch_prefill kernel.
COPY runtime/aiter_0625 /sgl-workspace/aiter_0625

# Prebuilt AITER JIT objects, including
# fmha_batch_prefill_d192_fp8bf16_group_ps64_..._vectorized_sglang.
COPY runtime/dot-aiter /root/.aiter

# AMD script set sealed 2026-07-28/29, including the FlyDSL wheels.
COPY decode_server_scripts /data/xisun/decode_server_scripts
COPY swebench /opt/mimo-swebench

RUN /opt/venv/bin/pip install --no-deps --force-reinstall \
        /data/xisun/decode_server_scripts/flydsl-0.2.4-cp310-cp310-manylinux_2_27_x86_64.whl \
        /data/xisun/decode_server_scripts/mimo_flydsl_kernels-0.1.0+c99d5cd-py3-none-any.whl \
 && /opt/venv/bin/pip install --no-deps -e /sgl-workspace/sglang_0625/python \
 && /opt/venv/bin/pip install --no-deps -e /sgl-workspace/aiter_0625

ENV SGLANG_ROOT=/sgl-workspace/sglang_0625
WORKDIR /sgl-workspace/sglang_0625
