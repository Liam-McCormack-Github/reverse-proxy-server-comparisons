import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import seaborn as sns
from pathlib import Path
from typing import Dict
import config


# Plotting Helpers

def _save_plot(fig: plt.Figure, path: Path, title: str) -> None:
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  -> ✅ Saved graph: {path.name} ({title})")


def _format_duration_axis(ax: plt.Axes) -> None:
    formatter = mticker.FuncFormatter(lambda s, _: f'{int(s // 60)}:{int(s % 60):02d}')
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(60))


# Table Generators

def _generate_k6_summary_table(df: pd.DataFrame, output_dir: Path) -> None:
    print("📄 Generating k6 master summary table...")
    master_table = df.sort_values(by=['test_type', 'users', 'proxy']).reset_index(drop=True)
    
    if 'docker_stats_df' in master_table.columns:
        master_table = master_table.drop(columns=['docker_stats_df'])

    format_map = {
        'rps': '{:.2f}', 
        'fail_rate': '{:.2%}',
        'iterations_rate': '{:.2f}',
        'data_sent_mb_s': '{:.3f}',
        'data_recv_mb_s': '{:.3f}',
    }
    duration_metrics = [c for c in master_table.columns if 'duration' in c or 'latency' in c]
    for col in duration_metrics: format_map[col] = '{:.2f}'

    for col, fmt in format_map.items():
        if col in master_table.columns:
            master_table[col] = master_table[col].apply(lambda x: fmt.format(x) if pd.notnull(x) else x)

    csv_path = output_dir / "k6_master_summary_table.csv"
    master_table.to_csv(csv_path, index=False)
    print(f"  -> ✅ Saved k6 master summary table: {csv_path.name}")


def generate_docker_summary_table(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty: return
    print("🐳 Generating Docker stats master summary table...")
    docker_cols = [c for c in summary_df.columns if any(cn in c for cn in config.RELEVANT_CONTAINERS)]
    if not docker_cols:
        print("  -> No Docker summary columns found to create table.")
        return

    id_cols = ['proxy', 'test_type', 'users', 'test_id']
    docker_table = summary_df[id_cols + sorted(docker_cols)].sort_values(by=['test_type', 'users', 'proxy'])

    for col in docker_cols:
        docker_table[col] = docker_table[col].apply(lambda x: f'{x:.2f}' if pd.notnull(x) else x)

    csv_path = output_dir / "docker_master_summary_table.csv"
    docker_table.to_csv(csv_path, index=False)
    print(f"  -> ✅ Saved Docker stats master summary table: {csv_path.name}")


# Plot Generators

def generate_k6_summary_and_visuals(df: pd.DataFrame, dirs: Dict[str, Path]) -> None:
    if df.empty: return
    _generate_k6_summary_table(df, dirs["summary_tables"])

    print("📊 Generating key metric summary graphs...")
    for metric in ['rps', 'latency_p95', 'avg_cpu', 'avg_mem_mib']:
        if metric not in df.columns: continue
        g = sns.catplot(data=df, x='users', y=metric, hue='proxy', col='test_type', kind='bar', height=5, aspect=1.2, sharey=False, legend_out=True, hue_order=['Go', 'Java', 'Node'], palette=config.PROXY_COLORS, errorbar=None)
        g.figure.suptitle(f'Average {metric.replace("_", " ").title()} Comparison', y=1.03)
        _save_plot(g.figure, dirs["summary_graphs"] / f"summary_avg_{metric}.png", f'Avg {metric}')


def generate_distribution_plots(df: pd.DataFrame, output_dir: Path) -> None:
    if df.empty: return
    print("📊 Generating distribution plots...")
    for metric in ['rps', 'latency_p95', 'avg_cpu', 'avg_mem_mib']:
        if metric not in df.columns: continue
        g = sns.catplot(data=df, x='users', y=metric, hue='proxy', col='test_type', kind='box', height=5, aspect=1.2, sharey=False, hue_order=['Go', 'Java', 'Node'], palette=config.PROXY_COLORS)
        g.figure.suptitle(f'Distribution of {metric.replace("_", " ").title()}', y=1.03)
        _save_plot(g.figure, output_dir / f"summary_dist_{metric}.png", f'Dist {metric}')


def _create_timeseries_plot(df: pd.DataFrame, y_col: str, title: str, y_label: str, output_path: Path, hue_col: str = 'display_name') -> None:
    fig, ax = plt.subplots(figsize=(15, 7))
    sns.lineplot(data=df, x='relative_time', y=y_col, hue=hue_col, ax=ax, palette=config.PROXY_COLORS, hue_order=['Go', 'Java', 'Node', 'Target Server', 'Influxdb'], errorbar=None)
    ax.set_title(title, fontsize=16)
    ax.set_ylabel(y_label)
    ax.set_xlabel("Time (M:SS)")
    ax.set_ylim(bottom=0)
    sns.move_legend(ax, "upper left", bbox_to_anchor=(1, 1))
    _format_duration_axis(ax)
    plt.tight_layout()
    _save_plot(fig, output_path, title)


def generate_docker_stats_visualizations(df: pd.DataFrame, output_dir: Path) -> None:
    if df.empty or 'docker_stats_df' not in df.columns: return
    print("🐳 Generating Docker stats time-series graphs...")
    name_map = {'go-proxy': 'Go', 'java-proxy': 'Java', 'node-proxy': 'Node', 'target-server': 'Target Server', 'influxdb': 'Influxdb'}
    for _, row in df.iterrows():
        stats_df, test_id = row.get('docker_stats_df'), row.get('test_id')
        if stats_df is None or stats_df.empty: continue

        system_df = stats_df.copy()
        system_df['display_name'] = system_df['name'].map(name_map)

        _create_timeseries_plot(system_df, 'cpu_perc_float', f"System CPU Usage: {test_id}", "CPU Usage (%)", output_dir / f"{test_id}_docker_cpu.png")
        _create_timeseries_plot(system_df, 'mem_usage_mib', f"System Memory Usage: {test_id}", "Memory (MiB)", output_dir / f"{test_id}_docker_mem.png")


def generate_k6_visualizations(summary_df: pd.DataFrame, k6_df: pd.DataFrame, output_dir: Path) -> None:
    if k6_df.empty: return
    print("📈 Generating k6 time-series graphs...")
    merged_df = summary_df.merge(k6_df.reset_index(), on='test_id')
    for test_id, group in merged_df.groupby('test_id'):
        for metric, title, y_label, color, path_suffix in [
            ('rps', 'Successful Requests (RPS)', 'Successes per Second', 'tab:green', 'k6_success.png'),
            ('error_rate', 'Error Rate', 'Failures per Second', 'tab:red', 'k6_errors.png')
        ]:
            fig, ax = plt.subplots(figsize=(15, 7))
            metric_df = group[group['metric'] == metric]
            ax.plot(metric_df['relative_time'], metric_df['value'], color=color, label=title)
            ax.set_title(f"{title}: {test_id}", fontsize=16)
            ax.set_ylabel(y_label)
            ax.set_xlabel("Time (M:SS)")
            ax.set_ylim(bottom=0)
            _format_duration_axis(ax)
            plt.tight_layout()
            _save_plot(fig, output_dir / f"{test_id}_{path_suffix}", title)


def generate_comparison_visualizations(summary_df: pd.DataFrame, k6_df: pd.DataFrame, output_dir: Path) -> None:
    if k6_df.empty: return
    print("🔄 Generating k6 comparison time-series graphs...")
    merged_df = summary_df[['test_id', 'proxy', 'test_type', 'users']].merge(k6_df.reset_index(), on='test_id')
    for (test_type, users), group in merged_df.groupby(['test_type', 'users']):
        test_name = f"{test_type}-{users}"
        _create_timeseries_plot(group[group['metric'] == 'rps'], 'value', f"RPS Comparison: {test_name}", "RPS", output_dir / f"comparison_rps_{test_name}.png", hue_col='proxy')
        _create_timeseries_plot(group[group['metric'] == 'error_rate'], 'value', f"Error Rate Comparison: {test_name}", "Failures per Second", output_dir / f"comparison_errors_{test_name}.png", hue_col='proxy')


def generate_docker_comparison_visualizations(summary_df: pd.DataFrame, output_dir: Path) -> None:
    if summary_df.empty or 'docker_stats_df' not in summary_df.columns: return
    print("🐳🔄 Generating Docker stats comparison graphs...")
    all_proxy_stats = [
        row.get('docker_stats_df')[row.get('docker_stats_df')['name'] == f"{row['proxy'].lower()}-proxy"].assign(proxy=row['proxy'], test_type=row['test_type'], users=row['users'])
        for _, row in summary_df.iterrows() if row.get('docker_stats_df') is not None and not row.get('docker_stats_df').empty
    ]
    if not all_proxy_stats: return

    comparison_df = pd.concat(all_proxy_stats).reset_index()
    for (test_type, users), group in comparison_df.groupby(['test_type', 'users']):
        test_name = f"{test_type}-{users}"
        _create_timeseries_plot(group, 'cpu_perc_float', f"Proxy CPU Comparison: {test_name}", "CPU Usage (%)", output_dir / f"comparison_docker_cpu_{test_name}.png", hue_col='proxy')
        _create_timeseries_plot(group, 'mem_usage_mib', f"Proxy Memory Comparison: {test_name}", "Memory (MiB)", output_dir / f"comparison_docker_mem_{test_name}.png", hue_col='proxy')


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
            g = sns.relplot(data=df_user, x=p['x'], y=p['y'], hue='Proxies', style='Test Types', s=150, palette=config.PROXY_COLORS, hue_order=['Go', 'Java', 'Node'], kind='scatter', height=6, aspect=1.2)
            g.figure.suptitle(f"Correlation for {user_load} Users: {p['y']} vs. {p['x']}", y=1.03)
            _save_plot(g.figure, output_dir / f"correlation_{p['y']}_vs_{p['x']}_{user_load}.png", f"Correlation {user_load} Users")
