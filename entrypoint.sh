#!/bin/bash
set -e

# 设置时区
if [ -n "$TZ" ]; then
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
fi

run_update() {
    echo "Running subscription updates..."
    bash /app/run.sh
}

if [ "$1" = "once" ]; then
    run_update
    exit 0
fi

# 循环运行更新
UPDATE_INTERVAL=${UPDATE_INTERVAL:-21600}
while true; do
    run_update
    echo "Sleeping for ${UPDATE_INTERVAL} seconds..."
    sleep ${UPDATE_INTERVAL}
done
