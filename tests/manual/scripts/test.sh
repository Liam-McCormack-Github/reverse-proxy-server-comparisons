#!/bin/sh

run_health_test() {
    local proxy_name=$1
    local proxy_port=$2
    local proxy_service_name="${proxy_name}-proxy"

    echo -e "\n\n"
    echo "Running 'health' test on '$proxy_name'"
    if curl -k "https://$proxy_service_name:$proxy_port/index.html"; then
        echo "✅ Health check PASSED"
    else
        echo "❌ Health check FAILED"
    fi
}

run_stream_test() {
    local proxy_name=$1
    local proxy_port=$2
    local proxy_service_name="${proxy_name}-proxy"

    echo -e "\n\n"
    echo "Running 'stream' test on '$proxy_name'"
    wget -q --no-check-certificate "https://$proxy_service_name:$proxy_port/stream" -O /dev/null &
    WGET_PID=$!
    echo "Stream is running in the background (PID: $WGET_PID). Press [Enter] to stop."
    read -r
    echo "Stopping stream..."
    
    if kill -0 $WGET_PID > /dev/null 2>&1; then
        kill $WGET_PID
        echo "Stream stopped."
    else
        echo "Stream process (PID: $WGET_PID) was already stopped."
    fi
}

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <go|java|node|all> [test_name_1] [test_name_2] ..."
    echo "Available tests: health, stream"
    exit 1
fi

TARGET=$1
shift
TESTS_TO_RUN="$@"

PROXIES_TO_TEST=""
if [ "$TARGET" = "all" ]; then
    PROXIES_TO_TEST="go java node"
else
    PROXIES_TO_TEST=$TARGET
fi

for proxy in $PROXIES_TO_TEST; do
    echo -e "\n\n"
    echo "========================================="
    echo "  TARGET PROXY: $proxy"
    echo "========================================="

    PROXY_PORT=""
    case "$proxy" in
        go)   
            PROXY_PORT=$GO_PROXY_SERVER_PORT 
            ;;
        java) 
            PROXY_PORT=$JAVA_PROXY_SERVER_PORT 
            ;;
        node) 
            PROXY_PORT=$NODE_PROXY_SERVER_PORT 
            ;;
        *)
            echo "Unknown proxy '$proxy' in list. Skipping."
            continue
            ;;
    esac

    if [ -z "$PROXY_PORT" ]; then
        echo "Error: Port for proxy '$proxy' is not set in the environment. Skipping."
        continue
    fi

    for test_name in $TESTS_TO_RUN; do
        case "$test_name" in
            health) 
                run_health_test "$proxy" "$PROXY_PORT"
                ;;
            stream) 
                run_stream_test "$proxy" "$PROXY_PORT"
                ;;
            *) 
                echo "Warning: Unknown test '$test_name'. Skipping."
                ;;
        esac
    done
done