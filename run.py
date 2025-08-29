import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

load_dotenv()

# File System Paths
OUTPUTS_DIR = Path('outputs')
K6_DIR = OUTPUTS_DIR / 'k6'
DOCKER_LOG_FILE = OUTPUTS_DIR / 'docker-compose.log'
DOCKER_RESET_LOG_FILE = OUTPUTS_DIR / 'docker-compose-reset.log'

# Docker Container Groups
PROXY_CONTAINERS = ['go-proxy', 'java-proxy', 'node-proxy']
METRICS_CONTAINERS = ['influxdb', 'telegraf']
SERVER_CONTAINERS = ['target-server', *PROXY_CONTAINERS]
ALL_LOG_CONTAINERS = [*SERVER_CONTAINERS, *METRICS_CONTAINERS]

# Test Script Configuration
TEST_SCRIPTS = [
    'image-1k',
    'image-5k',
    'image-10k',
    'smoke-1k',
    'smoke-5k',
    'smoke-10k',
    'injection-1k',
    'injection-5k',
    'injection-10k',
    'soak-1k',
    'soak-5k',
    'soak-10k',
]

# Global log option
LOG_OPTION = 'both'
_log_processes: List[Any] = []

def get_separator() -> str:
    try:
        width = shutil.get_terminal_size().columns
        return '-' * width
    except OSError:
        return '-' * 80


def _execute_with_header(title: str, func: Callable, *args: Any, **kwargs: Any) -> Any:
    separator = get_separator()
    print(f'\n\n{separator}')
    print(title)
    print(separator)
    result = func(*args, **kwargs)
    print(separator)
    return result


def run_command(command: List[str], logfile: Optional[Path] = None, log_option: str = 'both') -> int:
    command_name = command[0]
    if not shutil.which(command_name):
        print(f"Error: Command '{command_name}' not found. Is it installed and in your PATH?")
        return 1

    cmd_str = shlex.join(command)
    print(f'🛫 Started: `{cmd_str}`')

    try:
        # For 'console' or when no logfile is provided, subprocess.run is simple
        if log_option == 'console' or not logfile:
            process = subprocess.run(command, text=True, check=False)
            return_code = process.returncode
        # For 'file' and 'both' logging
        else:
            logfile.parent.mkdir(parents=True, exist_ok=True)
            with open(logfile, 'a', encoding='utf-8') as f:
                if log_option == 'file':
                    process = subprocess.run(command, stdout=f, stderr=f, text=True, check=False)
                    return_code = process.returncode
                elif log_option == 'both':
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        encoding='utf-8'
                    )
                    if process.stdout:
                        for line in iter(process.stdout.readline, ''):
                            sys.stdout.write(line)
                            f.write(line)
                        process.stdout.close()
                    process.wait()
                    return_code = process.returncode
                else:
                    return_code = 1

        print(f'🛬 Finished: `{cmd_str}`')
        return return_code

    except Exception as e:
        print(f'An error occurred while running `{cmd_str}`: {e}')
        return 1


def valid_env_exists() -> None:
    if not Path('.env').is_file():
        print('Error: .env file not found. Please read the README.md for setup instructions.')
        sys.exit(1)


def logging_setup() -> None:
    if OUTPUTS_DIR.exists():
        shutil.rmtree(OUTPUTS_DIR)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    K6_DIR.mkdir(parents=True, exist_ok=True)


def generate_certificates() -> None:
    certs_to_generate: Dict[str, Dict[str, str]] = {
        'target-server': {'subj': '/CN=localhost', 'sans': 'DNS:localhost,DNS:target-server'},
        'go-proxy': {'subj': '/CN=localhost'},
        'java-proxy': {'subj': '/CN=localhost'},
        'node-proxy': {'subj': '/CN=localhost'},
    }

    def _generate() -> None:
        for service, config in certs_to_generate.items():
            cert_path, key_path = Path(service) / 'cert.pem', Path(service) / 'key.pem'
            if cert_path.exists() and key_path.exists():
                print(f'Certificates for {service} already exist.')
            else:
                print(f'Generating certificates for {service}...')
                command = [
                    'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(key_path), '-out', str(cert_path), '-subj', config['subj']
                ]
                if 'sans' in config:
                    command.extend(['-addext', f'subjectAltName = {config["sans"]}'])
                run_command(command)

    _execute_with_header('Checking for SSL certificates...', _generate)


def docker_start_containers() -> None:
    _execute_with_header(
        'Starting containers...', run_command,
        ['docker-compose', 'up', '-d'], DOCKER_LOG_FILE, LOG_OPTION
    )


def docker_stop_containers() -> None:
    _execute_with_header(
        'Stopping containers...', run_command,
        ['docker-compose', 'stop'], DOCKER_LOG_FILE, LOG_OPTION
    )


def docker_clean_containers() -> None:
    _execute_with_header(
        'Stopping and cleaning containers...', run_command,
        ['docker-compose', 'down', '-v', '--rmi', 'all', '--remove-orphans'], DOCKER_LOG_FILE, LOG_OPTION
    )


def docker_purge_containers() -> None:
    def _purge() -> None:
        print('Current containers on your system:')
        subprocess.run(['docker', 'ps', '-a'])
        reply = input('Are you sure you want to purge everything? (y/n) ').lower().strip()
        if reply != 'y':
            print('Purge operation cancelled.')
            return

        print('Stopping all running containers...')
        stop_result = subprocess.run(['docker', 'ps', '-q'], capture_output=True, text=True)
        running_ids = stop_result.stdout.strip().split()
        if running_ids:
            run_command(['docker', 'stop', *running_ids], DOCKER_LOG_FILE, LOG_OPTION)
        else:
            print('No running containers to stop.')

        print('Removing all containers...')
        rm_result = subprocess.run(['docker', 'ps', '-a', '-q'], capture_output=True, text=True)
        all_ids = rm_result.stdout.strip().split()
        if all_ids:
            run_command(['docker', 'rm', *all_ids], DOCKER_LOG_FILE, LOG_OPTION)
            print('All containers have been removed.')
        else:
            print('No containers to remove.')

    _execute_with_header('Purging containers...', _purge)


def docker_takedown(*containers: str) -> None:
    if not containers:
        print('Warning: No containers specified for takedown.')
        return
    _execute_with_header(
        f'Taking down containers: {', '.join(containers)}...', run_command,
        ['docker-compose', 'stop', *containers], DOCKER_LOG_FILE, LOG_OPTION
    )


def docker_shell(container_name: str) -> None:
    def _shell() -> None:
        print('NOTE: Interactive shell sessions are not logged to a file.')
        shell_path = '//bin/sh' if container_name != 'influxdb' else 'sh'
        command = ['docker-compose', 'exec', container_name, shell_path]
        cmd_str = ' '.join(command)
        print(f'🛫 Started: `{cmd_str}`')
        try:
            subprocess.run(command, check=False)
        except Exception as e:
            print(f'An error occurred: {e}')
        print(f'\n🛬 Exited shell: `{cmd_str}`')

    _execute_with_header(f'Entering shell for container {container_name}...', _shell)


def docker_create_proxy_users() -> None:
    def _create() -> None:
        users = [
            ('GO_PROXY_ADMIN_ID', 'GO_PROXY_ADMIN_SECRET'),
            ('JAVA_PROXY_ADMIN_ID', 'JAVA_PROXY_ADMIN_SECRET'),
            ('NODE_PROXY_ADMIN_ID', 'NODE_PROXY_ADMIN_SECRET'),
        ]
        for id_env, secret_env in users:
            user_id, user_secret = os.getenv(id_env), os.getenv(secret_env)
            if user_id and user_secret:
                run_command([
                    'docker-compose', 'exec', 'target-server',
                    '//app/create_proxy_user', '--id', user_id, '--secret', user_secret
                ])
            else:
                print(f'Warning: Environment variables {id_env} or {secret_env} not set.')

    _execute_with_header('Creating/updating proxy users in the database...', _create)


def check_containers_running(container_names: List[str]) -> None:
    _execute_with_header(
        f'Checking status of required containers: {", ".join(container_names)}...',
        _check_and_start,
        container_names
    )


def _check_and_start(container_names: List[str]) -> None:
    try:
        cmd = ['docker-compose', 'ps', '--services', '--filter', 'status=running']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        running_containers = set(result.stdout.strip().split('\n'))

        missing_containers = [name for name in container_names if name not in running_containers]

        if not missing_containers:
            print('✅ All required containers are already running.')
        else:
            print(f'🟡 The following required containers are not running: {", ".join(missing_containers)}.')
            print('Attempting to start services...')
            docker_start_containers()
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f'An error occurred while checking container status: {e}')
        print('Attempting to start services as a fallback...')
        docker_start_containers()


def reset_data_dirs() -> None:
    def _reset() -> None:
        run_command(['docker-compose', 'stop', 'influxdb'], DOCKER_RESET_LOG_FILE, LOG_OPTION)
        try:
            if Path('influxdb/data').exists():
                shutil.rmtree('influxdb/data')
                print('Removed influxdb/data')
            if K6_DIR.exists():
                shutil.rmtree(K6_DIR)
                print(f'Removed {K6_DIR}')
        except OSError as e:
            print(f'Error removing directories: {e}')

    _execute_with_header('Stopping containers and resetting InfluxDB data...', _reset)


def analyse() -> None:
    check_containers_running(METRICS_CONTAINERS)
    _execute_with_header('Starting analysis...', run_command, [sys.executable, 'data-analysis/analyse.py'])


def docker_save_logs_to_zip(output_dir: Path) -> None:
    def _archive() -> None:
        services_result = subprocess.run(
            ['docker-compose', 'config', '--services'],
            capture_output=True, text=True, check=True
        )
        services = services_result.stdout.strip().split('\n')
        temp_log_dir = output_dir / 'temp_logs'
        temp_log_dir.mkdir(exist_ok=True)
        for service in services:
            print(f"   -> Capturing logs for '{service}'...")
            with open(temp_log_dir / f'{service}.log', 'w', encoding='utf-8') as f:
                subprocess.run(
                    ['docker-compose', 'logs', '--no-color', service],
                    stdout=f, stderr=subprocess.STDOUT
                )
        zip_path = output_dir / 'docker-logs.zip'
        print(f"\n   -> Creating zip file at '{zip_path}'...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in temp_log_dir.glob('*.log'):
                zipf.write(file, arcname=file.name)
        shutil.rmtree(temp_log_dir)
        print('✅ Successfully created log archive.')

    _execute_with_header('📦 Archiving container logs...', _archive)


def k6_test(proxy_name: str, script_name: str) -> None:
    def _run_test() -> None:
        # Environment setup
        influx_user, influx_pass = os.getenv('INFLUXDB_ADMIN_USER'), os.getenv('INFLUXDB_ADMIN_PASSWORD')
        influx_url = f'http://{influx_user}:{influx_pass}@127.0.0.1:8086/k6'
        current_timestamp = int(time.time())
        test_run_id = f'{proxy_name}-{script_name}-{current_timestamp}'
        test_dir = K6_DIR / str(current_timestamp)
        test_dir.mkdir(parents=True, exist_ok=True)

        print(f"🚀 Running test: '{script_name}.js' against proxy: '{proxy_name}'...")

        # Copy artifacts
        shutil.copy(f'tests/k6/{script_name}.js', test_dir)
        shutil.copy('docker-compose.yml', test_dir)
        shutil.copy('.env', test_dir)

        # Log system state
        processes_file = test_dir / f'processes-before-{proxy_name}-test.csv'
        print(f'📝 Logging current processes to {processes_file}')
        try:
            with open(processes_file, 'w', encoding='utf-8') as f:
                cmd = ['tasklist', '/fo', 'csv'] if sys.platform == 'win32' else ['ps', 'aux']
                subprocess.run(cmd, stdout=f, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f'Could not log processes: {e}.')

        # Execute k6
        print('⚙️  Starting k6 test...')
        start_time = int(time.time())
        k6_command = [
            'k6', 'run',
            '--summary-export', str(test_dir / f'k6-summary-{proxy_name}-{script_name}.json'),
            '--tag', f'test_run_id={test_run_id}', '--out', f'influxdb={influx_url}',
            '--env', f'PROXY_TARGET={proxy_name}', f'tests/k6/{script_name}.js'
        ]
        run_command(k6_command)
        time.sleep(5)
        end_time = int(time.time())

        # Archive results
        docker_save_logs_to_zip(test_dir)
        metadata = {'test_id': test_run_id, 'start_time': start_time, 'end_time': end_time}
        metadata_file = test_dir / f'k6-out-{proxy_name}-{script_name}.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        print(f'\n✅ Test complete. Metadata saved to {metadata_file}')
        print(f"▶️   Finished Test: '{script_name}.js' for Proxy: '{proxy_name}'")

    separator = get_separator()
    print(f'\n\n{separator}')
    print(f"Starting Test: '{script_name}.js' for Proxy: '{proxy_name}'")
    print(separator)
    _run_test()
    print(separator)




def _cleanup_log_processes(sig: int, frame: object) -> None:
    print('\nCaught Ctrl+C... killing all background log processes')
    for p in _log_processes:
        if p.is_alive():
            p.terminate()
    sys.exit(0)


def docker_logs(container_name: str) -> None:
    prefix = f'{container_name:<14} | '
    logfile = OUTPUTS_DIR / f'{container_name}.log'
    command = ['docker-compose', 'logs', '-f', container_name, '--no-log-prefix']
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, encoding='utf-8'
        )
        with open(logfile, 'a', encoding='utf-8') as f:
            if process.stdout:
                for line in iter(process.stdout.readline, ''):
                    prefixed_line = f'{prefix}{line}'
                    sys.stdout.write(prefixed_line)
                    f.write(prefixed_line)
        process.stdout.close()
        process.wait()
    except KeyboardInterrupt:
        print(f'\nStopping logs for {container_name}.')
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            process.wait()


def _run_log_group(containers: List[str]) -> None:
    from multiprocessing import Process
    signal.signal(signal.SIGINT, _cleanup_log_processes)
    for container in containers:
        p = Process(target=docker_logs, args=(container,))
        p.start()
        _log_processes.append(p)
    for p in _log_processes:
        p.join()


def log_all() -> None: _run_log_group(ALL_LOG_CONTAINERS)


def log_metrics() -> None: _run_log_group(METRICS_CONTAINERS)


def log_servers() -> None: _run_log_group(SERVER_CONTAINERS)


def run_full_start() -> None:
    logging_setup()
    generate_certificates()
    docker_clean_containers()
    docker_start_containers()
    docker_create_proxy_users()


def run_all_tests() -> None:
    reset_data_dirs()
    logging_setup()
    generate_certificates()
    for proxy_to_test in PROXY_CONTAINERS:
        for script in TEST_SCRIPTS:
            separator = get_separator()
            print(f'\n{separator}')
            print(f"Preparing test run for proxy '{proxy_to_test}' with script '{script}.js'")
            print(separator)
            docker_clean_containers()
            docker_start_containers()
            docker_create_proxy_users()
            proxies_to_takedown = [p for p in PROXY_CONTAINERS if p != proxy_to_test]
            docker_takedown(*proxies_to_takedown)
            print('Waiting 60 seconds for services to stabilize...')
            time.sleep(60)
            k6_test(proxy_to_test, script)
    print('\n\n🎉🎉🎉 All test runs completed! 🎉🎉🎉\n\n')
    docker_takedown('telegraf')


def main() -> None:
    parser = argparse.ArgumentParser(description='Python script for managing docker containers and running tests.')
    parser.add_argument('--log', choices=['console', 'file', 'both'], default='both', help='Set logging option.')
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    subparsers.add_parser('start', help='Cleans and then starts containers.')
    subparsers.add_parser('resume', help='Starts containers without cleaning.')
    subparsers.add_parser('stop', help='Stop containers.')
    subparsers.add_parser('clean', help='Stop and remove containers.')
    subparsers.add_parser('purge', help='Stop and remove ALL containers on the system.')
    subparsers.add_parser('resetData', help='Stop containers and reset InfluxDB data.')
    subparsers.add_parser('createProxyUsers', help='Create/update proxy users in the database.')
    subparsers.add_parser('analyse', help='Run the data analysis script.')
    subparsers.add_parser('testAll', help='Run all integration tests for all proxies.')
    subparsers.add_parser('logAll', help='Get logs for all containers concurrently.')
    subparsers.add_parser('logMetrics', help='Get logs for metrics containers (influxdb, telegraf).')
    subparsers.add_parser('logServers', help='Get logs for server/proxy containers.')
    takedown_parser = subparsers.add_parser('takedown', help='Stop one or more specific containers.')
    takedown_parser.add_argument('containers', nargs='+', help='Name(s) of the container(s) to stop.')
    test_parser = subparsers.add_parser('test', help='Run a specific test for a specific proxy.')
    test_parser.add_argument('proxy', choices=PROXY_CONTAINERS, help='The proxy to test.')
    test_parser.add_argument('script', choices=TEST_SCRIPTS, help='The test script to run.')
    logs_parser = subparsers.add_parser('logs', help='Get logs for a specific container.')
    logs_parser.add_argument('container', help='The name of the container to get logs from.')
    shell_parser = subparsers.add_parser('shell', help='Enter a shell for a container.')
    shell_parser.add_argument('container', help='The name of the container to enter.')

    args = parser.parse_args()
    global LOG_OPTION
    LOG_OPTION = args.log
    valid_env_exists()

    # Map command strings to functions for clean dispatching
    commands: Dict[str, Callable] = {
        'start': run_full_start,
        'resume': docker_start_containers,
        'stop': docker_stop_containers,
        'clean': docker_clean_containers,
        'purge': docker_purge_containers,
        'resetData': reset_data_dirs,
        'createProxyUsers': docker_create_proxy_users,
        'analyse': analyse,
        'testAll': run_all_tests,
        'logAll': log_all,
        'logMetrics': log_metrics,
        'logServers': log_servers,
        'takedown': lambda: docker_takedown(*args.containers),
        'test': lambda: k6_test(args.proxy, args.script),
        'logs': lambda: docker_logs(args.container),
        'shell': lambda: docker_shell(args.container),
    }

    command_func = commands.get(args.command)
    if command_func:
        command_func()
    else:
        print(f"Error: Command '{args.command}' is not recognized.")
        sys.exit(1)


if __name__ == '__main__':
    main()
