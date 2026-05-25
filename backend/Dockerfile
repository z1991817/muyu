FROM rust:1.89-slim-bookworm AS rust-toolchain

FROM python:3.12-slim-bookworm

WORKDIR /app

RUN sed -i \
        -e 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' \
        -e 's|http://deb.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' \
        /etc/apt/sources.list.d/debian.sources

RUN apt-get update \
    && apt-get install -y --fix-missing -o Acquire::Retries=3 --no-install-recommends \
        curl ca-certificates pkg-config build-essential libssl-dev clang libclang-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=rust-toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup

ENV CARGO_HOME=/usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV PATH="/usr/local/cargo/bin:${PATH}"

COPY backend/seesea/seesea-core /tmp/seesea-core
COPY backend/seesea/seesea /tmp/seesea
RUN pip install --no-cache-dir /tmp/seesea-core /tmp/seesea \
    && rm -rf /tmp/seesea-core /tmp/seesea

COPY backend/pyproject.toml backend/README.md ./
COPY backend/app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
