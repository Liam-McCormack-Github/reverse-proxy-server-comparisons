#!/bin/bash

terminal_width=$(tput cols);
separator=$(printf '%*s' "$terminal_width" | tr ' ' '-');
current_timestamp=$(date +%s)

# --------------------------------------------------------------
# SETUP AND VALIDATION FUNCTIONS
# --------------------------------------------------------------


validEnvExists() {
    if [ ! -f .env ]; then
        echo "Error .env file not found. Please read the README.md for instructions on how to set up the environment."
        exit 1
    fi 
}


usage() {
    echo "Usage: ./run.sh <option> [flags]"
    echo ""
    echo "Options:"
    echo "  start                 Cleans and then starts containers"
    echo "  resume                Starts containers"
    echo "  stop                  Stop containers"
    echo "  clean                 Stop and remove containers"
    echo "  purge                 Stop and remove ALL containers on the system"
    echo ""
    echo "  test <proxy>   Run integration tests for a specific proxy"
    echo ""
    echo "  shell <container>     Enter a shell for a container"
    echo ""
    echo "  logAll                Get logs for all containers"
    echo "  logs <container>      Get logs for a specific container"
    echo ""
    echo "Flags:"    
    echo "  --log=console         Log to console"
    echo "  --log=file            Log to file"
    echo "  --log=both            Log to both console and file"
    echo ""
}


loggingSetup() {
    rm -rf outputs
    mkdir -p outputs
}


generateCertificates() {
    echo -e "\n\n$separator"
    echo "Checking for SSL certificates..."
    echo "$separator"

    # Define the certificate subject and the required hostnames
    subj="/CN=localhost"
    sans="DNS:localhost,DNS:target-server"

    # Generate certs for the target-server
    if [ -f "target-server/cert.pem" ] && [ -f "target-server/key.pem" ]; then
        echo "Certificates for target-server already exist."
    else
        echo "Generating certificates for target-server..."
        openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout "target-server/key.pem" \
            -out "target-server/cert.pem" \
            -subj "$subj" \
            -addext "subjectAltName = $sans"
    fi

    # Generate certs for the go-proxy
    if [ -f "go-proxy/cert.pem" ] && [ -f "go-proxy/key.pem" ]; then
        echo "Certificates for go-proxy already exist."
    else
        echo "Generating certificates for go-proxy..."
        # Note: The proxy's own certificate only needs to be valid for localhost
        openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout "go-proxy/key.pem" \
            -out "go-proxy/cert.pem" \
            -subj "/CN=localhost"
    fi
    
    # Generate certs for the java-proxy
    if [ -f "java-proxy/cert.pem" ] && [ -f "java-proxy/key.pem" ]; then
        echo "Certificates for java-proxy already exist."
    else
        echo "Generating certificates for java-proxy..."
        openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout "java-proxy/key.pem" \
            -out "java-proxy/cert.pem" \
            -subj "/CN=localhost"
    fi

    # Generate certs for the node-proxy
    if [ -f "node-proxy/cert.pem" ] && [ -f "node-proxy/key.pem" ]; then
        echo "Certificates for node-proxy already exist."
    else
        echo "Generating certificates for node-proxy..."
        openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout "node-proxy/key.pem" \
            -out "node-proxy/cert.pem" \
            -subj "/CN=localhost"
    fi

    echo "$separator"
}


# --------------------------------------------------------------
# DOCKER COMMAND FUNCTIONS
# --------------------------------------------------------------


dockerStartContainers() {
    echo -e "\n\n$separator"
    echo "Starting containers..."
    echo "$separator"
    case "$LOG_OPTION" in 
        "console")
            docker-compose up -d;
        ;;
        "file")
            docker-compose up -d > outputs/docker-compose.log 2>&1;
        ;;
        "both")
            docker-compose up -d 2>&1 | tee -a outputs/docker-compose.log;
        ;;
    esac
    echo "$separator"
}


dockerStopContainers() {
    echo -e "\n\n$separator"
    echo "Stopping containers..."
    echo "$separator"
    case "$LOG_OPTION" in 
        "console")
            docker-compose stop;
        ;;
        "file")
            docker-compose stop > outputs/docker-compose.log 2>&1;
        ;;
        "both")
            docker-compose stop 2>&1 | tee -a outputs/docker-compose.log;
        ;;
    esac
    echo "$separator"
}


dockerCleanContainers() {
    echo -e "\n\n$separator"
    echo "Stopping and cleaning containers..."
    echo "$separator"
    case "$LOG_OPTION" in 
        "console")
            docker-compose down -v --rmi all --remove-orphans;
        ;;
        "file")
            docker-compose down -v --rmi all --remove-orphans > outputs/docker-compose.log 2>&1;
        ;;
        "both")
            docker-compose down -v --rmi all --remove-orphans 2>&1 | tee -a outputs/docker-compose.log;
        ;;
    esac
    echo "$separator"
}


dockerPurgeContainers() {
    echo -e "\n\n$separator"
    echo "Purging containers..."
    echo "$separator"
    echo "Current containers on your system:"
    docker ps -a
    read -p "Are you sure you want to purge everything? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Stopping all running containers..."
        if [ -n "$(docker ps -q)" ]; then
            case "$LOG_OPTION" in 
                "console")
                    docker stop $(docker ps -q);
                ;;
                "file")
                    docker stop $(docker ps -q) > outputs/docker-compose.log 2>&1;
                ;;
                "both")
                    docker stop $(docker ps -q) 2>&1 | tee -a outputs/docker-compose.log;
                ;;
            esac
        else
            echo "No running containers to stop."
        fi
        echo "Removing all containers..."
        if [ -n "$(docker ps -a -q)" ]; then
            case "$LOG_OPTION" in 
                "console")
                    docker rm $(docker ps -q);
                ;;
                "file")
                    docker rm $(docker ps -q) > outputs/docker-compose.log 2>&1;
                ;;
                "both")
                    docker rm $(docker ps -q) 2>&1 | tee -a outputs/docker-compose.log;
                ;;
            esac
            echo "All containers have been removed."
        else
            echo "No containers to remove."
        fi
    else
        echo "Purge operation cancelled."
    fi
    echo "$separator"
}


k6Tests() {
    local proxy_name="$1"
    local test_scripts=("soak") # Update this with tests from tests/k6/*.js
    local k6_dir="outputs-k6"

    if [ -z "$proxy_name" ]; then
        echo "Error: Missing proxy name for 'test' command."
        usage
        exit 1
    fi

    echo -e "\n\n$separator"
    echo "Starting Full Test Suite for Proxy: $proxy_name"
    echo "$separator"

    
    mkdir -p ${k6_dir}
    mkdir -p ${k6_dir}/${current_timestamp}

    for test_script in "${test_scripts[@]}"; do
        echo "🚀 Running test: '${test_script}.js' against proxy: '${proxy_name}'..."
        cp "tests/k6/${test_script}.js" "${k6_dir}/${current_timestamp}/"
        echo "📝 Logging current processes..."
        tasklist //v //fo csv > "${k6_dir}/${current_timestamp}/processes-before-${proxy_name}-test.csv"

        # Call the local k6 binary
        k6 run --quiet --summary-export="${k6_dir}/${current_timestamp}/summary_run_${proxy_name}.json" --out json="${k6_dir}/${current_timestamp}/metrics_run_${proxy_name}.json" --env PROXY_TARGET="$proxy_name" "tests/k6/${test_script}.js" 2>&1 | tee -a "${k6_dir}/${current_timestamp}/k6_log_run_${proxy_name}.log"

        if [ $? -eq 0 ]; then
            echo "✅ Completed test: '${test_script}.js' for proxy: '${proxy_name}'."
        else
            echo "❌ FAILED test: '${test_script}.js' for proxy: '${proxy_name}'."
        fi
        echo "$separator"
    done
    
    echo "▶️  Finished Full Test Suite for Proxy: $proxy_name"
    echo "$separator"
}


dockerLogs() {
    local containers_name="$1"
    if [ -z "$containers_name" ]; then
        echo "Error: Missing container name."
        usage
        exit 1
    fi

    local prefix
    prefix=$(printf "%-14s" "$containers_name")

    add_prefix() {
        while IFS= read -r line; do
            echo "${prefix} | ${line}"
        done
    }

    case "$LOG_OPTION" in
        "console")
            docker-compose logs -f "$containers_name" --no-log-prefix | add_prefix
            ;;
        "file")
            docker-compose logs -f "$containers_name" --no-log-prefix 2>&1 | add_prefix > "outputs/${containers_name}.log"
            ;;
        "both")
            docker-compose logs -f "$containers_name" --no-log-prefix 2>&1 | add_prefix | tee -a "outputs/${containers_name}.log"
            ;;
    esac
}


dockerShell() {
    local containers_name="$1"
    if [ -z "$containers_name" ]; then
        echo "Error: Missing container name."
        usage
        exit 1
    fi
    echo -e "\n\n$separator"
    echo "Entering shell for container ${containers_name}..."
    echo "$separator"
    docker-compose exec ${containers_name} //bin/sh
    echo "$separator"
}


dockerCreateProxyUsers() {
    echo -e "\n\n$separator"
    echo "Creating/updating proxy users in the database..."
    echo "$separator"
    export $(grep -v '^#' .env | xargs)

    # python-target-server
    # docker-compose exec target-server //bin/sh -c "python create_proxy_user.py --id $GO_PROXY_ADMIN_ID --secret $GO_PROXY_ADMIN_SECRET"
    # docker-compose exec target-server //bin/sh -c "python create_proxy_user.py --id $JAVA_PROXY_ADMIN_ID --secret $JAVA_PROXY_ADMIN_SECRET"
    # docker-compose exec target-server //bin/sh -c "python create_proxy_user.py --id $NODE_PROXY_ADMIN_ID --secret $NODE_PROXY_ADMIN_SECRET"
    
    # go-target-server
    docker-compose exec target-server //app/create_proxy_user --id $GO_PROXY_ADMIN_ID --secret $GO_PROXY_ADMIN_SECRET
    docker-compose exec target-server //app/create_proxy_user --id $JAVA_PROXY_ADMIN_ID --secret $JAVA_PROXY_ADMIN_SECRET
    docker-compose exec target-server //app/create_proxy_user --id $NODE_PROXY_ADMIN_ID --secret $NODE_PROXY_ADMIN_SECRET
    echo "$separator"
}


logAll() {
    pids=()
    cleanup() {
    echo -e "\nCaught Ctrl+C... killing all background processes"
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null
    done
    exit 1
    }
    trap cleanup SIGINT
    dockerLogs "target-server" &
    pids+=($!)
    dockerLogs "go-proxy" &
    pids+=($!)
    dockerLogs "java-proxy" &
    pids+=($!)
    dockerLogs "node-proxy" &
    pids+=($!)
    wait
}

# Default values
COMMAND=$1
shift
LOG_OPTION="both"
TARGET_PROXY=""
TARGET_CONTAINER=""

# Check if .env file exists
validEnvExists

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --log=console|--log=file|--log=both|--log=colour)
            LOG_OPTION="${1#--log=}"
            ;;
        go|node|java)
            TARGET_PROXY="$1"
            ;;
        target-server|go-proxy|node-proxy|java-proxy|manual-test)
            TARGET_CONTAINER="$1"
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
    shift
done

case "$COMMAND" in
    start)
        loggingSetup
        generateCertificates
        dockerCleanContainers
        dockerStartContainers  
        dockerCreateProxyUsers
        ;;
    resume)
        dockerStartContainers  
        ;;
    stop)
        dockerStopContainers
        ;;
    clean)
        dockerCleanContainers
        ;;
    purge)
        dockerPurgeContainers
        ;;
    test)
        k6Tests "$TARGET_PROXY"
        ;;
    testAll)
        k6Tests "go-proxy"
        k6Tests "java-proxy"
        k6Tests "node-proxy"
        ;;
    logs)
        dockerLogs "$TARGET_CONTAINER"
        ;;
    logAll)
        logAll
        ;;
    createProxyUsers)
        dockerCreateProxyUsers
        ;;
    shell)
        dockerShell "$TARGET_CONTAINER"
        ;;
    *)
        usage
        ;;
esac
