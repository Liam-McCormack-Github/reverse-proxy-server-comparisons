#!/bin/bash

terminal_width=$(tput cols);
separator=$(printf '%*s' "$terminal_width" | tr ' ' '-');

usage() {
    echo "Usage: ./run.sh <option> [flags]"
    echo ""
    echo "Options:"
    echo "  up                    Start containers"
    echo "  down                  Stop containers"
    echo "  clean                 Stop and remove containers"
    echo "  purge                 Stop and remove ALL containers on the system"
    echo "  test <go|java|node>   Run integration tests for a specific proxy"
    echo "  logs <target-server>   Get logs for a specific container"
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

dockerUpContainers() {
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

dockerDownContainers() {
    echo -e "\n\n$separator"
    echo "Stopping containers..."
    echo "$separator"
    case "$LOG_OPTION" in 
        "console")
            docker-compose down;
        ;;
        "file")
            docker-compose down > outputs/docker-compose.log 2>&1;
        ;;
        "both")
            docker-compose down 2>&1 | tee -a outputs/docker-compose.log;
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

    echo -e "\n\n$separator"
    echo "Logging outputs for container ${containers_name}..."
    echo "$separator"
    case "$LOG_OPTION" in
        "console")
            docker-compose logs -f "$containers_name"
            ;;
        "file")
            docker-compose logs -f "$containers_name" > "outputs/${containers_name}.log" 2>&1
            ;;
        "both")
            docker-compose logs -f "$containers_name" 2>&1 | tee -a "outputs/${containers_name}.log"
            ;;
    esac
    echo "$separator"
    
}

# Default values
COMMAND=$1
shift
LOG_OPTION="both"
TEST_TYPE=""
TARGET_CONTAINER=""

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --log=console|--log=file|--log=both|--log=colour)
            LOG_OPTION="${1#--log=}"
            ;;
        go|node|java)
            TEST_TYPE="$1"
            ;;
        target-server)
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
    up)
        loggingSetup
        dockerCleanContainers
        dockerUpContainers  
        ;;
    down)
        loggingSetup
        dockerDownContainers
        ;;
    clean)
        loggingSetup
        dockerCleanContainers
        ;;
    purge)
        loggingSetup
        dockerPurgeContainers
        ;;
    test)
        loggingSetup
        dockerTests "$TEST_TYPE"
        ;;
    logs)
        loggingSetup
        dockerLogs "$TARGET_CONTAINER"
        ;;
    *)
        echo "Invalid command: $COMMAND"
        usage
        ;;
esac
