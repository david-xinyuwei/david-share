#!/bin/bash
# AMD-standard PD infrastructure setup for MI300X containers
# Components: etcd + ROCm-aware UCX + ROCm-aware OpenMPI
# Reference: https://github.com/sammysun0711/llm-distributed-inference/tree/main/sglang/scripts
set -e

WORKDIR=/sgl-workspace
cd $WORKDIR

echo "=============================="
echo "Step 1/4: Install etcd v3.6.0-rc.5"
echo "=============================="
if command -v etcd &>/dev/null; then
    echo "etcd already installed: $(etcd --version | head -1)"
else
    apt-get update -qq && apt-get install -y -qq wget flex > /dev/null 2>&1
    wget -q https://github.com/etcd-io/etcd/releases/download/v3.6.0-rc.5/etcd-v3.6.0-rc.5-linux-amd64.tar.gz -O /tmp/etcd.tar.gz
    tar --no-same-owner -xf /tmp/etcd.tar.gz -C /usr/local/bin/ --strip-components=1 && rm /tmp/etcd.tar.gz
    echo "etcd installed: $(etcd --version | head -1)"
fi

echo "=============================="
echo "Step 2/4: Build ROCm-aware UCX v1.18.1"
echo "=============================="
if [ -f /opt/ucx/bin/ucx_info ]; then
    echo "UCX already installed: $(/opt/ucx/bin/ucx_info -v 2>&1 | head -1)"
else
    cd $WORKDIR
    if [ ! -d ucx ]; then
        git clone https://github.com/openucx/ucx.git -b v1.18.1 --depth 1
    fi
    cd ucx
    ./autogen.sh
    ./configure --with-rocm=/opt/rocm --enable-mt --prefix=/opt/ucx
    make -j $(nproc)
    make install
    echo 'export PATH=/opt/ucx/bin:$PATH' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/opt/ucx/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
    export PATH=/opt/ucx/bin:$PATH
    export LD_LIBRARY_PATH=/opt/ucx/lib:$LD_LIBRARY_PATH
    echo "UCX installed: $(ucx_info -v 2>&1 | head -1)"
    cd $WORKDIR
fi

echo "=============================="
echo "Step 3/4: Build ROCm-aware OpenMPI v5.0.x"
echo "=============================="
if [ -f /opt/ompi/bin/mpirun ]; then
    echo "OpenMPI already installed: $(/opt/ompi/bin/mpirun --version 2>&1 | head -1)"
else
    cd $WORKDIR
    if [ ! -d ompi ]; then
        git clone --recursive https://github.com/open-mpi/ompi.git -b v5.0.x --depth 1
    fi
    cd ompi
    ./autogen.pl
    ./configure --prefix=/opt/ompi --with-rocm=/opt/rocm --with-ucx=/opt/ucx
    make -j $(nproc)
    make install
    echo 'export PATH=/opt/ompi/bin:$PATH' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/opt/ompi/lib:$LD_LIBRARY_PATH' >> ~/.bashrc
    export PATH=/opt/ompi/bin:$PATH
    export LD_LIBRARY_PATH=/opt/ompi/lib:$LD_LIBRARY_PATH
    echo "OpenMPI installed: $(/opt/ompi/bin/mpirun --version 2>&1 | head -1)"
    cd $WORKDIR
fi

echo "=============================="
echo "Step 4/4: Verification"
echo "=============================="
echo "--- etcd ---"
etcd --version 2>&1 | head -1
echo "--- UCX ---"
/opt/ucx/bin/ucx_info -v 2>&1 | grep -E "version|configured"
echo "--- OpenMPI ---"
/opt/ompi/bin/ompi_info 2>&1 | grep -E "extensions|MPI version" | head -3
echo "=============================="
echo "ALL DONE at $(date)"
echo "=============================="
