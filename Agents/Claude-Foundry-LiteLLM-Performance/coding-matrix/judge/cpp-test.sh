#!/bin/bash
# Same steps as Aider's benchmark/cpp-test.sh.
set -e

[ ! -d "build" ] && mkdir build
cd build
cmake -DEXERCISM_RUN_ALL_TESTS=1 -G "Unix Makefiles" ..
make
