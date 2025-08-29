import json
import pandas as pd
from typing import Any, Dict, List, Optional
import config
from influxdb import DataFrameClient


def _get_metric(metrics: Dict[str, Any], metric_name: str, sub_key: str) -> Optional[Any]:
    return metrics.get(metric_name, {}).get(sub_key)


def _parse_k6_out_file(directory: config.Path) -> Optional[Dict[str, Any]]:
    for file_path in directory.iterdir():
        if config.K6_OUT_FILENAME_PATTERN.match(file_path.name):
            with open(file_path, 'r', encoding='utf-8') as f:
                out_data = json.load(f)
                start_dt = pd.to_datetime(out_data['start_time'], unit='s', utc=True)
                end_dt = pd.to_datetime(out_data['end_time'], unit='s', utc=True)
                duration = (end_dt - start_dt).total_seconds()

                if abs(duration - config.EXPECTED_TEST_DURATION_S) > config.TEST_DURATION_TOLERANCE_S:
                    print(f"⚠️  Skipping {directory.name}: Invalid duration. Got {duration:.2f}s, expected {config.EXPECTED_TEST_DURATION_S}s.")
                    return None

                return {
                    'test_id': out_data['test_id'],
                    'start_time_ts': out_data['start_time'],
                    'start_time': start_dt.isoformat().replace('+00:00', 'Z'),
                    'end_time': end_dt.isoformat().replace('+00:00', 'Z'),
                }
    return None


def _parse_summary_file(directory: config.Path, run_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    for file_path in directory.iterdir():
        summary_match = config.SUMMARY_FILENAME_PATTERN.match(file_path.name)
        if not summary_match:
            continue

        proxy_name_raw, test_name = summary_match.groups()
        proxy_name = proxy_name_raw.replace('-proxy', '').capitalize()
        test_match = config.TEST_NAME_PATTERN.match(test_name)
        if test_match:
            run_info.update({'proxy': proxy_name, **test_match.groupdict()})

        with open(file_path, 'r', encoding='utf-8') as f:
            metrics = json.load(f).get('metrics', {})

        run_info.update({
            'total_reqs': _get_metric(metrics, 'http_reqs', 'count'),
            'rps': _get_metric(metrics, 'http_reqs', 'rate'),
            'fail_rate': _get_metric(metrics, 'http_req_failed', 'value'),
            'data_sent_mb_s': (_get_metric(metrics, 'data_sent', 'rate') or 0) / (1024 * 1024),
            'data_recv_mb_s': (_get_metric(metrics, 'data_received', 'rate') or 0) / (1024 * 1024),
            'iterations_count': _get_metric(metrics, 'iterations', 'count'),
            'iterations_rate': _get_metric(metrics, 'iterations', 'rate'),
            'vus_min': _get_metric(metrics, 'vus', 'min'),
            'vus_max': _get_metric(metrics, 'vus', 'max'),
        })

        for metric_base in ['http_req_duration', 'http_req_blocked', 'http_req_tls_handshaking']:
            for sub_key in ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)']:
                clean_key = sub_key.replace('(', '').replace(')', '')
                col_name = f"{metric_base.replace('http_req_', '')}_{clean_key}"
                run_info[col_name] = _get_metric(metrics, metric_base, sub_key)
        return run_info
    return None


def load_summary_from_files() -> pd.DataFrame:
    all_runs_data: List[Dict[str, Any]] = []
    print(f"🔎 Scanning for k6 summary files in: '{config.ROOT_DATA_DIR}'")

    if not config.ROOT_DATA_DIR.exists():
        print(f"❌ Root data directory not found at '{config.ROOT_DATA_DIR}'")
        return pd.DataFrame()

    for timestamp_dir in sorted(config.ROOT_DATA_DIR.iterdir()):
        if not timestamp_dir.is_dir():
            continue
        run_info = _parse_k6_out_file(timestamp_dir)
        if run_info:
            full_run_data = _parse_summary_file(timestamp_dir, run_info)
            if full_run_data:
                all_runs_data.append(full_run_data)

    if not all_runs_data:
        print("⚠️ No valid k6 summary files were found and loaded.")
        return pd.DataFrame()

    print("✅ k6 summary file loading complete.")
    return pd.DataFrame(all_runs_data)


def _calculate_detailed_docker_stats(stats_df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> Dict[str, float]:
    """Calculates aggregated stats for before, during, and after the test window."""
    detailed_stats: Dict[str, float] = {}
    periods = {
        'before': stats_df[stats_df['time'] < start_dt],
        'during': stats_df[(stats_df['time'] >= start_dt) & (stats_df['time'] <= end_dt)],
        'after': stats_df[stats_df['time'] > end_dt]
    }
    metrics_to_calc = {'cpu': 'cpu_perc_float', 'mem': 'mem_usage_mib'}
    aggregations = {'avg': 'mean', 'min': 'min', 'max': 'max', 'p90': lambda x: x.quantile(0.90), 'p95': lambda x: x.quantile(0.95)}

    for container_name in stats_df['name'].unique():
        for period_name, period_df in periods.items():
            container_df = period_df[period_df['name'] == container_name]
            if container_df.empty: continue
            for metric_prefix, metric_col in metrics_to_calc.items():
                for agg_name, agg_func in aggregations.items():
                    col_name = f"{container_name}_{metric_prefix}_{period_name}_{agg_name}"
                    detailed_stats[col_name] = container_df[metric_col].agg(agg_func)
    return detailed_stats


def add_docker_stats_from_influxdb(summary_df: pd.DataFrame) -> pd.DataFrame:
    if summary_df.empty: return summary_df
    print("🔌 Connecting to InfluxDB to fetch Telegraf Docker stats...")
    try:
        client = DataFrameClient(host=config.INFLUX_HOST, port=config.INFLUX_PORT, username=config.INFLUX_USERNAME, password=config.INFLUX_PASSWORD, database=config.INFLUX_DOCKER_DATABASE)
        client.ping()
    except Exception as e:
        print(f"❌ Could not connect to InfluxDB for Docker stats: {e}")
        return summary_df

    stats_list = []
    for _, row in summary_df.iterrows():
        try:
            start_dt, end_dt = pd.to_datetime(row['start_time']), pd.to_datetime(row['end_time'])
            buffer = pd.Timedelta(seconds=60)
            query_start = (start_dt - buffer).isoformat().replace('+00:00', 'Z')
            query_end = (end_dt + buffer).isoformat().replace('+00:00', 'Z')
            tag_key = config.DOCKER_CONTAINER_TAG_KEY

            cpu_query = f"SELECT mean(\"usage_percent\") AS cpu_perc_float FROM \"docker_container_cpu\" WHERE time >= '{query_start}' AND time <= '{query_end}' GROUP BY time(1s), \"{tag_key}\" fill(previous)"
            mem_query = f"SELECT mean(\"usage\") AS mem_bytes FROM \"docker_container_mem\" WHERE time >= '{query_start}' AND time <= '{query_end}' GROUP BY time(1s), \"{tag_key}\" fill(previous)"

            cpu_result, mem_result = client.query(cpu_query), client.query(mem_query)
            if not cpu_result or not mem_result:
                print(f"⚠️  No Telegraf Docker data for test_id {row.get('test_id', 'N/A')}")
                stats_list.append({'docker_stats_df': pd.DataFrame()});
                continue

            cpu_dfs = [df.assign(name=dict(tags)[tag_key]) for (_, tags), df in cpu_result.items() if tags and tag_key in dict(tags)]
            mem_dfs = [df.assign(name=dict(tags)[tag_key]) for (_, tags), df in mem_result.items() if tags and tag_key in dict(tags)]

            if not cpu_dfs or not mem_dfs:
                print(f"⚠️  Incomplete or untagged Telegraf data for test_id {row.get('test_id', 'N/A')}")
                stats_list.append({'docker_stats_df': pd.DataFrame()})
                continue

            combined_cpu = pd.concat(cpu_dfs).reset_index().rename(columns={'index': 'time'})
            combined_mem = pd.concat(mem_dfs).reset_index().rename(columns={'index': 'time'})
            stats_df = pd.merge(combined_cpu, combined_mem, on=['time', 'name'], how='outer').ffill().bfill()
            
            stats_df['mem_usage_mib'] = stats_df['mem_bytes'] / (1024 * 1024)
            stats_df['relative_time'] = (stats_df['time'] - stats_df['time'].min()).dt.total_seconds()
            stats_df = stats_df[stats_df['name'].isin(config.RELEVANT_CONTAINERS)].copy()

            detailed_stats = _calculate_detailed_docker_stats(stats_df, start_dt, end_dt)
            proxy_container = f"{row['proxy'].lower()}-proxy"
            during_df = stats_df[(stats_df['time'] >= start_dt) & (stats_df['time'] <= end_dt)]
            proxy_during_df = during_df[during_df['name'] == proxy_container]

            stats_list.append({
                'docker_stats_df': stats_df.set_index('relative_time'),
                'avg_cpu': proxy_during_df['cpu_perc_float'].mean(),
                'avg_mem_mib': proxy_during_df['mem_usage_mib'].mean(),
                **detailed_stats
            })
        except Exception as e:
            print(f"⚠️  Error processing Telegraf data for test_id '{row.get('test_id', 'N/A')}': {e}")
            stats_list.append({'docker_stats_df': pd.DataFrame()})

    print("✅ Telegraf Docker stats query complete.")
    return summary_df.join(pd.DataFrame(stats_list, index=summary_df.index))


def load_k6_timeseries_from_influxdb(summary_df: pd.DataFrame) -> pd.DataFrame:
    print("🔌 Connecting to InfluxDB to fetch k6 time-series data...")
    try:
        client = DataFrameClient(host=config.INFLUX_HOST, port=config.INFLUX_PORT, username=config.INFLUX_USERNAME, password=config.INFLUX_PASSWORD, database=config.INFLUX_K6_DATABASE)
        client.ping()
    except Exception as e:
        print(f"❌ Could not connect to InfluxDB for k6: {e}");
        return pd.DataFrame()

    all_timeseries_data = []
    for _, row in summary_df.iterrows():
        test_id, start_time, end_time = row['test_id'], row['start_time'], row['end_time']
        for metric, metric_name in [("http_reqs", "rps"), ("http_req_failed", "error_rate")]:
            query = f"SELECT sum(\"value\") FROM \"{metric}\" WHERE \"test_run_id\" = '{test_id}' AND time >= '{start_time}' AND time <= '{end_time}' GROUP BY time(1s) fill(0)"
            try:
                result = client.query(query)
                if metric in result:
                    df = result[metric].rename(columns={'sum': 'value'})
                    df['relative_time'] = (df.index - df.index.min()).total_seconds()
                    df['test_id'] = test_id
                    df['metric'] = metric_name
                    all_timeseries_data.append(df.reset_index(drop=True))
            except Exception as e:
                print(f"⚠️  Error querying k6 metric '{metric}', test_id '{test_id}': {e}")

    if not all_timeseries_data:
        print("⚠️ No k6 time-series data was found in InfluxDB.");
        return pd.DataFrame()

    print("✅ k6 time-series query complete.")
    return pd.concat(all_timeseries_data).set_index(['test_id', 'metric', 'relative_time'])
