# A Comparative Analysis of Modern Concurrency Models

This project contains the software artifacts for an MSc research project. It involves implementing and benchmarking three reverse proxy servers, built in **Go**, **Java (with Virtual Threads)**, and **Node.js (TypeScript)** to compare the performance, resource efficiency, and developer ergonomics of their respective concurrency models.

---

### Key Technologies 🛠️

- **Proxies**: Go, Java (JDK 21+), Node.js (TypeScript)

- **Containerisation**: Docker & Docker Compose

- **Load Testing**: Grafana k6

- **Metrics & Monitoring**: InfluxDB & Telegraf

- **Control Script**: Python

---

### Prerequisites

Before you begin, ensure you have the following installed:

- **Docker & Docker Compose**: For running the containerised services.

- **Python 3.10+ & Pip**: For running the project's control script.

- **Grafana k6**: The load testing tool.

- **OpenSSL**: For generating TLS certificates (often included with Git).

---

### Installation & Setup ⚙️

1. **Clone the Repository**:

   ```
   git clone <your-repository-url>
   cd <your-project-directory>
   ```

2. **Install Python Dependencies**: Set up a virtual environment and install the required packages.

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Create an Environment File**: Copy the template to create your local configuration file. You can customise the ports and credentials here if needed.

   ```
   cp .env-template .env
   ```

---

### Usage 🚀

All project operations are handled by the main Python script, **`run.py`**.

#### Starting the Environment

To build all Docker images, generate certificates, and start the entire application stack (proxies, target server, and monitoring tools), run:

```
python run.py start
```

#### Running Performance Tests

The script provides a powerful, automated way to run the benchmark suite.

- **Run the Full Test Suite (Recommended)**: This command will automatically cycle through each proxy, run all defined `k6` test scripts against it, and save the results. **This will delete any previous test data.**

  ```
  python run.py testAll
  ```

- **Run a Single Test**: To run a specific test script against a specific proxy:

  ```
  # Syntax: python run.py test <proxy-name> <script-name>
  python run.py test go-proxy image-10k
  ```

#### Analysing Results

After running tests, the collected data (from InfluxDB and the `outputs-k6` directory) can be processed by the analysis script. This will generate visualisations and data summaries.

```
python run.py analyse
```

#### Other Useful Commands

- **View Logs**: Stream the logs for a specific container.

  ```
  # Syntax: python run.py logs <container-name>
  python run.py logs go-proxy
  ```

- **Stop the Environment**: Stop all running containers without deleting data.

  ```
  python run.py stop
  ```

- **Clean Up**: Stop and remove all containers, networks, and volumes associated with the project.

  ```
  python run.py clean
  ```
