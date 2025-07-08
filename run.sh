#!/bin/bash

terminal_width=$(tput cols);
separator=$(printf '%*s' "$terminal_width" | tr ' ' '-');

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
    echo "  continue              Starts containers"
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

    # Generate certs for the target-server
    if [ ! -f "target-server/cert.pem" ] || [ ! -f "target-server/key.pem" ]; then
        echo "Generating certificates for target-server..."
        (cd target-server && openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout key.pem -out cert.pem \
            -subj "//CN=localhost")
    else
        echo "Certificates for target-server already exist."
    fi

    # Generate certs for the go-proxy
    if [ ! -f "go-proxy/cert.pem" ] || [ ! -f "go-proxy/key.pem" ]; then
        echo "Generating certificates for go-proxy..."
        (cd go-proxy && openssl req -x509 -newkey rsa:2048 -nodes \
            -keyout key.pem -out cert.pem \
            -subj "//CN=localhost")
    else
        echo "Certificates for go-proxy already exist."
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


dockerTests() {
    local proxy_name="$1"

    if [ -z "$proxy_name" ]; then
        echo "Error: Missing proxy name."
        usage
        exit 1
    fi

    echo -e "\n\n$separator"
    echo "Running Python tests for ${proxy_name} proxy..."
    echo "$separator"
    case "$LOG_OPTION" in
        "console")
            # docker-compose run ????
            ;;
        "file")
            # docker-compose run ???? > "outputs/${proxy_name}-tests.log" 2>&1
            ;;
        "both")
            # docker-compose run ???? 2>&1 | tee -a "outputs/${proxy_name}-tests.log"
            ;;
    esac
    echo "$separator"
}


dockerLogs() {
    local containers_name="$1"
    if [ -z "$containers_name" ]; then
        echo "Error: Missing container name."
        usage
        exit 1
    fi

    # Use printf to create the padded prefix.
    local prefix
    prefix=$(printf "%-14s" "$containers_name")

    # This helper function reads each line from the input
    # and prepends the padded prefix. It's more robust than 'sed'
    # in some cross-platform environments.
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
            # The 2>&1 redirects stderr to stdout so 'add_prefix' processes both.
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
    docker-compose exec ${containers_name} /bin/sh
    echo "$separator"
}


dockerCreateProxyUsers() {
    echo -e "\n\n$separator"
    echo "Creating/updating proxy users in the database..."
    echo "$separator"
    export $(grep -v '^#' .env | xargs)
    docker-compose exec target-server /bin/sh -c "python create_proxy_user.py --id $GO_PROXY_ADMIN_ID --secret $GO_PROXY_ADMIN_SECRET"
    docker-compose exec target-server /bin/sh -c "python create_proxy_user.py --id $JAVA_PROXY_ADMIN_ID --secret $JAVA_PROXY_ADMIN_SECRET"
    docker-compose exec target-server /bin/sh -c "python create_proxy_user.py --id $NODE_PROXY_ADMIN_ID --secret $NODE_PROXY_ADMIN_SECRET"
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
        target-server|go-proxy|node-proxy|java-proxy)
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
    continue)
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
        dockerTests "$TARGET_PROXY"
        ;;
    logs)
        dockerLogs "$TARGET_CONTAINER"
        ;;
    logAll)
        logAll
        ;;
    shell)
        dockerShell "$TARGET_CONTAINER"
        ;;
    *)
        usage
        ;;
esac
