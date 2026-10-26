# Offline test runner for the Aider Polyglot exercises.
# Toolchains follow Aider's benchmark/Dockerfile (Python 3.11, Go 1.21.5, Rust, Node 20 + jest deps,
# OpenJDK 21, CMake + Boost); the Aider tool itself is not installed. Tests run with --network none.
FROM buildpack-deps:jammy

RUN apt-get update && apt-get install -y software-properties-common cmake libboost-all-dev \
    && add-apt-repository ppa:deadsnakes/ppa && apt-get update \
    && apt-get install -y python3.11 python3.11-venv python3.11-dev ca-certificates-java openjdk-21-jdk libtbb-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python3.11 -m venv /opt/py && /opt/py/bin/pip install --no-cache-dir pytest==8.3.3
ENV PATH="/opt/py/bin:${PATH}"

RUN curl -fsSL "https://golang.org/dl/go1.21.5.linux-amd64.tar.gz" -o /tmp/go.tgz \
    && tar -C /usr/local -xzf /tmp/go.tgz && rm /tmp/go.tgz
ENV PATH="/usr/local/go/bin:${PATH}"

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/* && mkdir -p /npm-install && cd /npm-install && npm init -y \
    && npm install jest @babel/core@7.25.2 @exercism/babel-preset-javascript@0.2.1 \
       @exercism/eslint-config-javascript@0.6.0 @types/jest@29.5.12 @types/node@20.12.12 \
       babel-jest@29.6.4 core-js@3.37.1 eslint@8.49.0

COPY npm-test.sh cpp-test.sh /judge/
RUN chmod +x /judge/*.sh

# Cache the Gradle wrapper distribution and JUnit/AssertJ so Java tests can run --offline.
COPY java-warmup /warmup/java
RUN cd /warmup/java && chmod +x gradlew && (./gradlew test --no-daemon -q || true) && rm -rf /warmup/java/build
ENV GRADLE_OPTS="-Dorg.gradle.daemon=false"

RUN python3 --version && go version && rustc --version && node --version && java -version 2>&1 | head -1 && cmake --version | head -1
