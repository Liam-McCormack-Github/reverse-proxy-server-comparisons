import re
from pathlib import Path
from typing import Dict, List, Pattern

# Directory and Path Configuration
CONFIG_DIR: Path = Path(__file__).resolve().parent
PROJECT_ROOT: Path = CONFIG_DIR.parent

ROOT_DATA_DIR: Path = PROJECT_ROOT / "outputs-k6"
OUTPUT_DIR: Path = PROJECT_ROOT / "data-analysis" / "output"

# Test Run Validation
EXPECTED_TEST_DURATION_S: int = 300
TEST_DURATION_TOLERANCE_S: int = 45

# Visualization and Container Configuration
PROXY_COLORS: Dict[str, str] = {
    'Go': 'green', 'Java': 'red', 'Node': 'blue',
    'Target Server': 'orange', 'Influxdb': 'purple'
}

RELEVANT_CONTAINERS: List[str] = [
    'go-proxy',
    'java-proxy',
    'node-proxy',
    'target-server',
    'influxdb'
]

# InfluxDB Configuration
INFLUX_HOST: str = "localhost"
INFLUX_PORT: int = 8086
INFLUX_USERNAME: str = "user"
INFLUX_PASSWORD: str = "password"
INFLUX_K6_DATABASE: str = "k6"

INFLUX_DOCKER_DATABASE: str = "dockerstats"
DOCKER_CONTAINER_TAG_KEY: str = 'io.telegraf.group.name'

# Filename Parsing Patterns (Regex)
SUMMARY_FILENAME_PATTERN: Pattern[str] = re.compile(
    r"k6-summary-(?P<proxy_name>go-proxy|java-proxy|node-proxy)-(?P<test_name>.+).json"
)
K6_OUT_FILENAME_PATTERN: Pattern[str] = re.compile(
    r"k6-out-(?P<proxy_name>go-proxy|java-proxy|node-proxy)-(?P<test_name>.+).json"
)
TEST_NAME_PATTERN: Pattern[str] = re.compile(
    r"(?P<test_type>soak|image|injection|smoke)-(?P<users>\d+k)"
)
