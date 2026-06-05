FROM alpine:latest

RUN apk add --no-cache bash curl python3 py3-yaml git ca-certificates tzdata && \
    ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    echo "Asia/Shanghai" > /etc/timezone

WORKDIR /app

RUN mkdir -p /app/tools && \
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        DOWNLOAD_ARCH="Linux_x86_64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then \
        DOWNLOAD_ARCH="Linux_arm64"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    curl -sL "https://github.com/faceair/clash-speedtest/releases/download/v1.8.8/clash-speedtest_${DOWNLOAD_ARCH}.tar.gz" -o /tmp/clash-speedtest.tar.gz && \
    tar -zxf /tmp/clash-speedtest.tar.gz -C /app/tools && \
    chmod +x /app/tools/clash-speedtest && \
    rm -f /tmp/clash-speedtest.tar.gz

COPY . /app

ENV PATH="/app/tools:${PATH}"
ENV ENABLE_SPEEDTEST=false
ENV UPDATE_INTERVAL=21600

ENTRYPOINT ["/app/entrypoint.sh"]
