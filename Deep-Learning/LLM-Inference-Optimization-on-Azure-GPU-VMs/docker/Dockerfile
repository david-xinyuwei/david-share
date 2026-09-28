# Serving runtime for MiMo-V2.5-Pro on Azure ND MI300X v5, rebuilt from public sources.
#
# Pins the commits of the final runtime (see ../upstream/SOURCES.lock.json).
# That runtime was not throughput-tested in this repository; the published runs
# used the earlier stack named in each README section. A clean build of these
# instructions succeeded on a CPU-only VM on 2026-09-28; see
# ../evidence/docker-build-20260928.json. Starting a server needs MI300X GPUs.

# Pinned by digest: a re-pushed tag must not change the base image.
FROM rocm/sgl-dev@sha256:8f8dc55398855764d339ff4e2695b9c3c298704999051acaa1a67993fdff62e5

# Every pin carries a PIN_ prefix: the base image sets ENV AITER_COMMIT (and other
# names), and an inherited ENV silently overrides an ARG of the same name.
ARG PIN_SGLANG_REPO=https://github.com/sammysun0711/sglang
ARG PIN_SGLANG_COMMIT=878fff15647fe3dabb32aa3a335b0ad16e3ee878
ARG PIN_AITER_REPO=https://github.com/sammysun0711/aiter
ARG PIN_AITER_COMMIT=3f4ab482a2986919c784e469e23cfac7f93bb153
ARG PIN_CK_COMMIT=af7118e342580ecd3f71edce7b1d0ba465012ecf
ARG PIN_FLYDSL_REPO=https://github.com/sammysun0711/FlyDSL
ARG PIN_FLYDSL_KERNELS_COMMIT=c99d5cd97864c11e459cff9169d387d312790782
ARG PIN_FLYDSL_WHEEL=flydsl-0.2.4-cp310-cp310-manylinux_2_27_x86_64.whl
ARG PIN_FLYDSL_WHEEL_SHA256=9749643a5155a1837b0fbbe4a39e4900fd672a91cdf12d2d9e084977bbcf5c3d

ENV PIP=/opt/venv/bin/pip PY=/opt/venv/bin/python

# Serving engine: the fork carries the FlyDSL dispatch, the vectorized-5D
# target-verify path, the MTP fixes and the CK A8W8 switch.
RUN git clone --filter=blob:none "$PIN_SGLANG_REPO" /sgl-workspace/sglang-pinned \
 && git -C /sgl-workspace/sglang-pinned checkout "$PIN_SGLANG_COMMIT" \
 && $PIP install --no-deps -e /sgl-workspace/sglang-pinned/python

# Kernel library: AITER plus the temporary composable_kernel patch that adds
# the head-192 / page-64 FP8 batch-prefill tile.
RUN git clone --filter=blob:none "$PIN_AITER_REPO" /sgl-workspace/aiter-pinned \
 && cd /sgl-workspace/aiter-pinned \
 && git checkout "$PIN_AITER_COMMIT" \
 && git submodule update --init 3rdparty/composable_kernel \
 && test "$(git -C 3rdparty/composable_kernel rev-parse HEAD)" = "$PIN_CK_COMMIT" \
 && git -C 3rdparty/composable_kernel apply --check < patches/composable_kernel/mimo_fp8_page64_head192_batch_prefill.patch \
 && git -C 3rdparty/composable_kernel apply < patches/composable_kernel/mimo_fp8_page64_head192_batch_prefill.patch \
 && $PIP install --no-deps -e /sgl-workspace/aiter-pinned

# FlyDSL runtime from PyPI and the kernel sources at the pinned commit.
# The measured runtime installed a wheel whose kernels/ tree is byte-identical
# to kernels/ at this commit.
RUN $PIP download --no-deps --only-binary=:all: --dest /tmp/flydsl-wheel "flydsl==0.2.4" \
 && test -f "/tmp/flydsl-wheel/$PIN_FLYDSL_WHEEL" \
 && echo "$PIN_FLYDSL_WHEEL_SHA256  /tmp/flydsl-wheel/$PIN_FLYDSL_WHEEL" | sha256sum -c - \
 && $PIP install --no-deps "/tmp/flydsl-wheel/$PIN_FLYDSL_WHEEL" \
 && rm -rf /tmp/flydsl-wheel \
 && git clone --filter=blob:none "$PIN_FLYDSL_REPO" /tmp/flydsl \
 && git -C /tmp/flydsl checkout "$PIN_FLYDSL_KERNELS_COMMIT" \
 && cp -r /tmp/flydsl/kernels "$($PY -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')/kernels" \
 && rm -rf /tmp/flydsl

RUN $PY -c "import sglang, aiter, flydsl, kernels.attention.pa_decode_tile; print('runtime imports ok')" \
 && test "$(git -C /sgl-workspace/sglang-pinned rev-parse HEAD)" = "$PIN_SGLANG_COMMIT" \
 && test "$(git -C /sgl-workspace/aiter-pinned rev-parse HEAD)" = "$PIN_AITER_COMMIT"

ENV SGLANG_ROOT=/sgl-workspace/sglang-pinned
WORKDIR /sgl-workspace/sglang-pinned
