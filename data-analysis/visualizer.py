from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns

import config

FLOAT_FORMAT = '{:.5f}'
PERCENT_FORMAT = '{:.2%}'
COUNT_FORMAT = '{:,.0f}'

K6_FORMAT_MAP = {
    'rps': FLOAT_FORMAT,
    'fail_rate': PERCENT_FORMAT,
    'fail_count': COUNT_FORMAT,
    'iterations_rate': FLOAT_FORMAT,
    'data_sent_mb_s': FLOAT_FORMAT,
    'data_recv_mb_s': FLOAT_FORMAT,
}

METRICS_TO_FORMAT_AS_FLOAT = [
    'duration', 'latency', 'connecting', 'receiving',
    'sending', 'waiting', 'blocked', 'handshaking'
]


def _save_plot(fig: plt.Figure, path: Path, title: str) -> None:
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> ✅ Saved graph: {path.name} ({title})")


def _format_duration_axis(ax: plt.Axes) -> None:
    formatter = mticker.FuncFormatter(lambda s, _: f'{int(s // 60)}:{int(s % 60):02d}')
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(60))


def _style_legend(legend) -> None:
    if legend:
        frame = legend.get_frame()
        frame.set_edgecolor('black')
        frame.set_facecolor('white')


def _apply_column_formats(df: pd.DataFrame, format_map: Dict[str, str]) -> pd.DataFrame:
    df_copy = df.copy()
    for col, fmt in format_map.items():
        if col in df_copy.columns:
            def format_cell(x):
                if pd.notnull(x):
                    formatted = fmt.format(x)
                    return '0.0' if formatted == FLOAT_FORMAT.format(0) else formatted
                return x

            df_copy[col] = df_copy[col].apply(format_cell)
    return df_copy


def _build_format_map(base_map: Dict[str, str], df_columns: List[str], float_metrics: List[str]) -> Dict[str, str]:
    format_map = base_map.copy()
    float_cols = [c for c in df_columns if any(metric in c for metric in float_metrics)]
    for col in float_cols:
        format_map[col] = FLOAT_FORMAT
    return format_map


def _prepare_docker_comparison_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    if 'docker_stats_df' not in summary_df.columns:
        return pd.DataFrame()

    all_proxy_stats = [
        row.get('docker_stats_df')[row.get('docker_stats_df')['name'] == f"{row['proxy'].lower()}-proxy"].assign(
            proxy=row['proxy'], test_type=row['test_type'], users=row['users']
        )
        for _, row in summary_df.iterrows() if row.get('docker_stats_df') is not None and not row.get('docker_stats_df').empty
    ]

    if not all_proxy_stats:
        return pd.DataFrame()

    return pd.concat(all_proxy_stats).reset_index()


def _create_timeseries_plot(df: pd.DataFrame, y_col: str, title: str, y_label: str, output_path: Path, hue_col: str = 'display_name') -> None:
    fig, ax = plt.subplots(figsize=(15, 7))

    unique_hues = df[hue_col].unique()
    is_user_load_hue = hue_col == 'Virtual Users'

    hue_order = None
    if not is_user_load_hue:
        relevant_proxies = [p for p in ['Go', 'Java', 'Node', 'Target Server', 'Influxdb'] if p in unique_hues]
        palette = {p: config.PROXY_COLORS[p] for p in relevant_proxies}
        hue_order = relevant_proxies
    else:
        palette = None
        hue_order = sorted(unique_hues, key=lambda x: int(x.replace('k', '')))

    sns.lineplot(data=df, x='relative_time', y=y_col, hue=hue_col, ax=ax, errorbar=None, palette=palette, hue_order=hue_order)

    ax.set_title(title, fontsize=16)
    ax.set_ylabel(y_label)
    ax.set_xlabel("Time (M:SS)")
    ax.set_ylim(bottom=0)
    legend_handle = sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1))
    _style_legend(legend_handle)
    _format_duration_axis(ax)
    plt.tight_layout(rect=[0, 0, 0.85, 1])
    _save_plot(fig, output_path, title)


def _generate_k6_summary_table(df: pd.DataFrame, output_dir: Path) -> None:
    print("📄 Generating k6 master summary table...")
    master_table = df.copy()

    docker_cols_to_drop = ['docker_stats_df', 'avg_cpu', 'avg_mem_mib']
    docker_cols_to_drop.extend([col for col in master_table.columns if any(container in col for container in config.RELEVANT_CONTAINERS)])

    master_table.drop(columns=list(set(docker_cols_to_drop)), inplace=True, errors='ignore')
    master_table = master_table.sort_values(by=['test_type', 'users', 'proxy']).reset_index(drop=True)

    format_map = _build_format_map(K6_FORMAT_MAP, master_table.columns, METRICS_TO_FORMAT_AS_FLOAT)
    formatted_table = _apply_column_formats(master_table, format_map)

    csv_path = output_dir / "k6_master_summary_table.csv"
    formatted_table.to_csv(csv_path, index=False)
    print(f"  -> ✅ Saved k6 master summary table: {csv_path.name}")


def generate_docker_summary_table(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty: return
    print("🐳 Generating Docker stats master summary table...")

    df_copy = summary_df.copy()
    metrics = {
        'cpu_during_avg': 'proxy_cpu_during_avg', 'cpu_during_min': 'proxy_cpu_during_min', 'cpu_during_max': 'proxy_cpu_during_max',
        'mem_during_avg': 'proxy_mem_during_avg', 'mem_during_min': 'proxy_mem_during_min', 'mem_during_max': 'proxy_mem_during_max'
    }

    for source_suffix, target_col in metrics.items():
        df_copy[target_col] = df_copy.apply(
            lambda row: row.get(f"{row['proxy'].lower()}-proxy_{source_suffix}"), axis=1
        )

    original_docker_cols = [c for c in summary_df.columns if any(cn in c for cn in config.RELEVANT_CONTAINERS)]
    if not original_docker_cols:
        print("  -> No Docker summary columns found to create table.")
        return

    id_cols = ['proxy', 'test_type', 'users', 'test_id']
    new_proxy_cols = list(metrics.values())
    final_cols = id_cols + new_proxy_cols + sorted([c for c in original_docker_cols if c not in new_proxy_cols])
    docker_table = df_copy[final_cols].sort_values(by=['test_type', 'users', 'proxy'])

    cols_to_format = {col: FLOAT_FORMAT for col in docker_table.columns if 'cpu' in col or 'mem' in col}
    formatted_table = _apply_column_formats(docker_table, cols_to_format)

    csv_path = output_dir / "docker_master_summary_table.csv"
    formatted_table.to_csv(csv_path, index=False)
    print(f"  -> ✅ Saved Docker stats master summary table: {csv_path.name}")


def generate_user_specific_tables(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty: return
    print("📄 Generating separate k6 and Docker tables for each user load...")

    all_docker_cols = [c for c in summary_df.columns if any(cn in c for cn in config.RELEVANT_CONTAINERS)] + ['docker_stats_df']

    for users in sorted(summary_df['users'].unique()):
        user_df = summary_df[summary_df['users'] == users]

        # K6 Table
        k6_df = user_df.drop(columns=all_docker_cols, errors='ignore')
        k6_format_map = _build_format_map(K6_FORMAT_MAP, k6_df.columns, METRICS_TO_FORMAT_AS_FLOAT)
        formatted_k6_df = _apply_column_formats(k6_df, k6_format_map)
        k6_csv_path = output_dir / f"k6_summary_{users}_users.csv"
        formatted_k6_df.sort_values(by=['test_type', 'proxy']).to_csv(k6_csv_path, index=False)
        print(f"  -> ✅ Saved k6-specific table: {k6_csv_path.name}")

        # Docker Table
        id_cols = ['proxy', 'test_type', 'users', 'test_id']
        during_cols = [c for c in all_docker_cols if '_during_' in c]
        if not during_cols:
            print(f"  -> ⚠️  No 'during' Docker stats found for {users} users. Skipping Docker table.")
            continue

        docker_df = user_df[id_cols + sorted(during_cols)]
        docker_format_map = {col: FLOAT_FORMAT for col in docker_df.columns if 'cpu' in col or 'mem' in col}
        formatted_docker_df = _apply_column_formats(docker_df, docker_format_map)
        docker_csv_path = output_dir / f"docker_summary_during_{users}_users.csv"
        formatted_docker_df.sort_values(by=['test_type', 'proxy']).to_csv(docker_csv_path, index=False)
        print(f"  -> ✅ Saved Docker-specific table: {docker_csv_path.name}")


def generate_kpi_tables(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty: return
    print("📄 Generating KPI summary tables...")

    kpi_cols = [col for col in config.KPI_COLUMNS if col in summary_df.columns]
    if len(kpi_cols) <= 2:
        print("  -> ⚠️  Not enough KPI columns available to generate tables.")
        return

    kpi_format_map = {
        'rps': FLOAT_FORMAT, 'duration_p95': FLOAT_FORMAT, 'fail_rate': PERCENT_FORMAT,
        'fail_count': COUNT_FORMAT, 'avg_cpu': FLOAT_FORMAT, 'avg_mem_mib': FLOAT_FORMAT
    }

    for proxy in sorted(summary_df['proxy'].unique()):
        proxy_df = summary_df[summary_df['proxy'] == proxy]
        kpi_df = proxy_df[kpi_cols].sort_values(by=['test_type', 'users']).reset_index(drop=True)

        formatted_kpi_df = _apply_column_formats(kpi_df, kpi_format_map)

        csv_path = output_dir / f"kpi_summary_{proxy}.csv"
        formatted_kpi_df.to_csv(csv_path, index=False)
        print(f"  -> ✅ Saved KPI table: {csv_path.name}")


def generate_k6_summary_and_visuals(df: pd.DataFrame, dirs: Dict[str, Path]) -> None:
    if df.empty: return
    _generate_k6_summary_table(df, dirs["summary_tables"])

    print("📊 Generating key metric summary graphs...")
    for metric in config.SUMMARY_GRAPH_METRICS:
        if metric not in df.columns: continue
        human_readable_metric = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get(metric, metric.replace("_", " ").title())
        g = sns.catplot(
            data=df, x='users', y=metric, hue='proxy', col='test_type',
            kind='bar', height=5, aspect=1.2, sharey=False, legend_out=True,
            hue_order=['Go', 'Java', 'Node'], palette=config.PROXY_COLORS, errorbar=None
        )
        g.figure.suptitle(f'{human_readable_metric} Comparison', y=1.03)
        g.set_titles("Test: {col_name}")
        g.set_xlabels("Virtual Users")
        g.set_ylabels(human_readable_metric)
        _style_legend(g.legend)
        for ax in g.axes.flat:
            for p in ax.patches:
                if p.get_height() > 0:
                    ax.text(p.get_x() + p.get_width() / 2.,
                            p.get_height(),
                            f'{p.get_height():.2f}',
                            fontsize=9,
                            color='black',
                            ha='center',
                            va='bottom')
        _save_plot(g.figure, dirs["summary_graphs"] / f"summary_average_{metric}.png", f'Avg {metric}')


def generate_docker_stats_visualizations(df: pd.DataFrame, output_dir: Path) -> None:
    if df.empty or 'docker_stats_df' not in df.columns: return
    print("🐳 Generating Docker stats time-series graphs...")
    name_map = {'go-proxy': 'Go', 'java-proxy': 'Java', 'node-proxy': 'Node', 'target-server': 'Target Server', 'influxdb': 'Influxdb'}

    cpu_label = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get('cpu_perc_float', 'CPU Usage (%)')
    mem_label = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get('mem_usage_mib', 'Memory (MiB)')

    for _, row in df.iterrows():
        stats_df, test_id = row.get('docker_stats_df'), row.get('test_id')
        if stats_df is None or stats_df.empty: continue

        system_df = stats_df.copy()
        system_df['display_name'] = system_df['name'].map(name_map)

        _create_timeseries_plot(system_df, 'cpu_perc_float', f"System {cpu_label}: {test_id}", cpu_label, output_dir / f"{test_id}_docker_cpu.png")
        _create_timeseries_plot(system_df, 'mem_usage_mib', f"System {mem_label}: {test_id}", mem_label, output_dir / f"{test_id}_docker_mem.png")


def generate_k6_visualizations(summary_df: pd.DataFrame, k6_df: pd.DataFrame, output_dir: Path) -> None:
    if k6_df.empty: return
    print("📈 Generating k6 time-series graphs...")
    merged_df = summary_df.merge(k6_df.reset_index(), on='test_id')

    for test_id, group in merged_df.groupby('test_id'):
        for metric in ['rps', 'error_rate']:
            human_readable_metric = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get(metric, metric.replace("_", " ").title())
            fig, ax = plt.subplots(figsize=(15, 7))
            metric_df = group[group['metric'] == metric]
            ax.plot(metric_df['relative_time'], metric_df['value'], label=human_readable_metric)
            ax.set_title(f"{human_readable_metric}: {test_id}", fontsize=16)
            ax.set_ylabel(human_readable_metric)
            ax.set_xlabel("Time (M:SS)")
            ax.set_ylim(bottom=0)
            _format_duration_axis(ax)
            plt.tight_layout()
            _save_plot(fig, output_dir / f"{test_id}_k6_{metric}.png", human_readable_metric)


def generate_comparison_visualizations(summary_df: pd.DataFrame, k6_df: pd.DataFrame, output_dir: Path) -> None:
    if k6_df.empty: return
    print("🔄 Generating k6 comparison time-series graphs (by proxy)...")
    merged_df = summary_df[['test_id', 'proxy', 'test_type', 'users']].merge(k6_df.reset_index(), on='test_id')
    for (test_type, users), group in merged_df.groupby(['test_type', 'users']):
        test_name = f"{test_type}-{users}"
        for metric in ['rps', 'error_rate']:
            human_readable_metric = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get(metric, metric.replace("_", " ").title())
            _create_timeseries_plot(group[group['metric'] == metric], 'value', f"{human_readable_metric} Comparison: {test_name}", human_readable_metric, output_dir / f"comparison_{metric}_{test_name}.png", hue_col='proxy')


def generate_docker_comparison_visualizations(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty: return
    print("🐳🔄 Generating Docker stats comparison graphs (by proxy)...")
    comparison_df = _prepare_docker_comparison_df(summary_df)
    if comparison_df.empty: return

    cpu_label = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get('cpu_perc_float', 'CPU Usage (%)')
    mem_label = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get('mem_usage_mib', 'Memory (MiB)')

    for (test_type, users), group in comparison_df.groupby(['test_type', 'users']):
        test_name = f"{test_type}-{users}"
        _create_timeseries_plot(group, 'cpu_perc_float', f"Proxy {cpu_label} Comparison: {test_name}", cpu_label, output_dir / f"comparison_docker_cpu_{test_name}.png", hue_col='proxy')
        _create_timeseries_plot(group, 'mem_usage_mib', f"Proxy {mem_label} Comparison: {test_name}", mem_label, output_dir / f"comparison_docker_mem_{test_name}.png", hue_col='proxy')


def generate_user_load_k6_comparison_visualizations(summary_df: pd.DataFrame, k6_df: pd.DataFrame, output_dir: Path) -> None:
    if k6_df.empty: return
    print("🔄 Generating k6 comparison time-series graphs (by user load)...")
    merged_df = summary_df[['test_id', 'proxy', 'test_type', 'users']].merge(k6_df.reset_index(), on='test_id')

    merged_df.rename(columns={'users': 'Virtual Users'}, inplace=True)

    for (proxy, test_type), group in merged_df.groupby(['proxy', 'test_type']):
        test_name = f"{proxy}-{test_type}"
        for metric in ['rps', 'error_rate']:
            human_readable_metric = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get(metric, metric.replace("_", " ").title())
            _create_timeseries_plot(group[group['metric'] == metric], 'value', f"{human_readable_metric} Comparison for {test_name}", human_readable_metric, output_dir / f"user_comparison_{metric}_{test_name}.png", hue_col='Virtual Users')


def generate_docker_user_load_comparison_visualizations(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty: return
    print("🐳🔄 Generating Docker stats comparison graphs (by user load)...")
    comparison_df = _prepare_docker_comparison_df(summary_df)
    if comparison_df.empty: return

    comparison_df.rename(columns={'users': 'Virtual Users'}, inplace=True)

    cpu_label = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get('cpu_perc_float', 'CPU Usage (%)')
    mem_label = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get('mem_usage_mib', 'Memory (MiB)')

    for (proxy, test_type), group in comparison_df.groupby(['proxy', 'test_type']):
        test_name = f"{proxy}-{test_type}"
        _create_timeseries_plot(group, 'cpu_perc_float', f"Proxy {cpu_label} Comparison for {test_name}", cpu_label, output_dir / f"user_comparison_docker_cpu_{test_name}.png", hue_col='Virtual Users')
        _create_timeseries_plot(group, 'mem_usage_mib', f"Proxy {mem_label} Comparison for {test_name}", mem_label, output_dir / f"user_comparison_docker_mem_{test_name}.png", hue_col='Virtual Users')


def generate_correlation_plots(summary_df: pd.DataFrame, output_dir: Path) -> None:
    required_cols = ['rps', 'fail_rate', 'avg_cpu', 'avg_mem_mib', 'proxy', 'test_type', 'users']
    if summary_df.empty or not all(col in summary_df.columns for col in required_cols): return
    print("📊 Generating performance vs. resource correlation plots...")

    df = summary_df.rename(columns={'proxy': 'Proxies', 'test_type': 'Test Types', 'users': 'Virtual Users'})
    df['fail_rate'] *= 100

    for user_load in sorted(df['Virtual Users'].unique()):
        df_user = df[df['Virtual Users'] == user_load]
        if df_user.empty: continue

        for p in [{'x': 'avg_cpu', 'y': 'rps'}, {'x': 'avg_mem_mib', 'y': 'rps'}, {'x': 'avg_cpu', 'y': 'fail_rate'}, {'x': 'avg_mem_mib', 'y': 'fail_rate'}]:
            y_metric_name = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get(p['y'], p['y'].replace('_', ' ').title())
            x_metric_name = config.METRIC_COLUMN_TO_HUMAN_NAME_MAP.get(p['x'], p['x'].replace('_', ' ').title())

            g = sns.relplot(
                data=df_user, x=p['x'], y=p['y'], hue='Proxies', style='Test Types',
                s=150, palette=config.PROXY_COLORS, hue_order=['Go', 'Java', 'Node'],
                kind='scatter', height=6, aspect=1.2
            )
            g.figure.suptitle(f"Correlation for {user_load} Users: {y_metric_name} vs. {x_metric_name}", y=1.03)
            g.set_ylabels(y_metric_name)
            g.set_xlabels(x_metric_name)
            _style_legend(g.legend)
            _save_plot(g.figure, output_dir / f"correlation_{p['y']}_vs_{p['x']}_{user_load}.png", f"Correlation {user_load} Users")
