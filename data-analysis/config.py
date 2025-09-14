import re
from pathlib import Path
from typing import Dict, List, Pattern

CONFIG_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = CONFIG_DIR.parent

ROOT_DATA_DIR: Path = PROJECT_ROOT / "outputs-k6"
OUTPUT_DIR: Path = PROJECT_ROOT / "data-analysis" / "output"

EXPECTED_TEST_DURATION_S: int = 300
TEST_DURATION_TOLERANCE_S: int = 45

PROXY_COLORS: Dict[str, str] = {
    'Go': 'green',
    'Java': 'red',
    'Node': 'blue',
    'Target Server': 'orange',
    'Influxdb': 'purple'
}

RELEVANT_CONTAINERS: List[str] = [
    'go-proxy',
    'java-proxy',
    'node-proxy',
    'target-server',
    'influxdb'
]

INFLUX_HOST: str = "localhost"
INFLUX_PORT: int = 8086
INFLUX_USERNAME: str = "user"
INFLUX_PASSWORD: str = "password"
INFLUX_K6_DATABASE: str = "k6"

INFLUX_DOCKER_DATABASE: str = "dockerstats"
DOCKER_CONTAINER_TAG_KEY: str = 'io.telegraf.group.name'

SUMMARY_FILENAME_PATTERN: Pattern[str] = re.compile(
    r"k6-summary-(?P<proxy_name>go-proxy|java-proxy|node-proxy)-(?P<test_name>.+).json"
)
K6_OUT_FILENAME_PATTERN: Pattern[str] = re.compile(
    r"k6-out-(?P<proxy_name>go-proxy|java-proxy|node-proxy)-(?P<test_name>.+).json"
)
TEST_NAME_PATTERN: Pattern[str] = re.compile(
    r"(?P<test_type>soak|image|injection|smoke|soak-for-go-target|soak-for-python-target)-(?P<users>\d+k)"
)

COMPARATIVE_METRICS_MAP: Dict[str, str] = {
    "Average RPS": "rps",
    "Total Requests": "total_reqs",
    "Failure Count": "fail_count",
    "Failure Rate": "fail_rate",
    "Error Rate": "error_rate",
    "Check Pass Rate": "checks_pass_rate",
    "Check Pass Count": "checks_pass_count",
    "Check Fail Count": "checks_fail_count",
    "P95 Duration (ms)": "duration_p95",
    "P90 Duration (ms)": "duration_p90",
    "Average Duration (ms)": "duration_avg",
    "Median Duration (ms)": "duration_med",
    "Min Duration (ms)": "duration_min",
    "Max Duration (ms)": "duration_max",
    "P95 TTFB (ms)": "waiting_p95",
    "P90 TTFB (ms)": "waiting_p90",
    "Average TTFB (ms)": "waiting_avg",
    "Median TTFB (ms)": "waiting_med",
    "Min TTFB (ms)": "waiting_min",
    "Max TTFB (ms)": "waiting_max",
    "P95 Connection Time (ms)": "connecting_p95",
    "P90 Connection Time (ms)": "connecting_p90",
    "Average Connection Time (ms)": "connecting_avg",
    "Median Connection Time (ms)": "connecting_med",
    "Min Connection Time (ms)": "connecting_min",
    "Max Connection Time (ms)": "connecting_max",
    "Average Iteration Duration (ms)": "iteration_duration_avg",
    "Min Iteration Duration (ms)": "iteration_duration_min",
    "Max Iteration Duration (ms)": "iteration_duration_max",
    "Average CPU Usage (%)": "avg_cpu",
    "CPU Usage (%)": "cpu_perc_float",
    "Min CPU Usage (%)": "min_cpu",
    "Max CPU Usage (%)": "max_cpu",
    "Average Memory Usage (MiB)": "avg_mem_mib",
    "Memory (MiB)": "mem_usage_mib",
    "Min Memory Usage (MiB)": "min_mem_mib",
    "Max Memory Usage (MiB)": "max_mem_mib"
}

METRIC_COLUMN_TO_HUMAN_NAME_MAP: Dict[str, str] = {v: k for k, v in COMPARATIVE_METRICS_MAP.items()}

K6_METRICS_TO_PARSE: List[str] = [
    'http_req_duration', 'http_req_blocked', 'http_req_connecting',
    'http_req_receiving', 'http_req_sending', 'http_req_tls_handshaking',
    'http_req_waiting', 'iteration_duration'
]

KPI_COLUMNS: List[str] = [
    'test_type', 'users', 'rps', 'duration_p95', 'fail_rate',
    'fail_count', 'avg_cpu', 'avg_mem_mib'
]

SUMMARY_GRAPH_METRICS: List[str] = [
    'rps', 'duration_p95', 'fail_count', 'avg_cpu', 'avg_mem_mib'
]
