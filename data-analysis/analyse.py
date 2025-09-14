import shutil
from pathlib import Path
from typing import Dict

import comparative_analysis
import config
import data_loader
import visualizer


def setup_output_directories() -> Dict[str, Path]:
    if config.OUTPUT_DIR.exists():
        print(f"🧹 Clearing previous output directory: '{config.OUTPUT_DIR}'")
        shutil.rmtree(config.OUTPUT_DIR)

    table_output_dir = config.OUTPUT_DIR / "tables"
    graph_output_dir = config.OUTPUT_DIR / "graphs"
    statements_output_dir = config.OUTPUT_DIR / "statements"

    dirs = {
        "summary_tables": table_output_dir / "summary",
        "summary_graphs": graph_output_dir / "summary",
        "proxy_graphs": graph_output_dir / "proxy",
        "comparison_direct_graphs": graph_output_dir / "comparison-direct",
        "comparison_correlation_graphs": graph_output_dir / "comparison-correlation",
        "comparison_users_graphs": graph_output_dir / "comparison-users",
        "comparative_statements": statements_output_dir / "comparative",
        "cross_proxy_statements": statements_output_dir / "cross-proxy",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    print(f"✨ Created fresh output directory structure in: '{config.OUTPUT_DIR}'")
    return dirs


def main() -> None:
    dirs = setup_output_directories()

    summary_df = data_loader.load_summary_from_files()
    if summary_df.empty:
        print("\n❌ No valid summary data was loaded. Halting analysis.")
        return

    summary_df = data_loader.add_docker_stats_from_influxdb(summary_df)
    k6_timeseries_df = data_loader.load_k6_timeseries_from_influxdb(summary_df)

    print("\n🚀 Starting visualisation and table generation...")
    visualizer.generate_k6_summary_and_visuals(summary_df, dirs)
    visualizer.generate_docker_summary_table(summary_df, dirs["summary_tables"])
    visualizer.generate_user_specific_tables(summary_df, dirs["summary_tables"])
    visualizer.generate_kpi_tables(summary_df, dirs["summary_tables"])

    visualizer.generate_docker_stats_visualizations(summary_df, dirs["proxy_graphs"])
    visualizer.generate_docker_comparison_visualizations(summary_df, dirs["comparison_direct_graphs"])
    visualizer.generate_correlation_plots(summary_df, dirs["comparison_correlation_graphs"])

    if not k6_timeseries_df.empty:
        visualizer.generate_k6_visualizations(summary_df, k6_timeseries_df, dirs["proxy_graphs"])
        visualizer.generate_comparison_visualizations(summary_df, k6_timeseries_df, dirs["comparison_direct_graphs"])
        visualizer.generate_user_load_k6_comparison_visualizations(summary_df, k6_timeseries_df, dirs["comparison_users_graphs"])
        visualizer.generate_docker_user_load_comparison_visualizations(summary_df, dirs["comparison_users_graphs"])
    else:
        print("⚠️ k6 time-series data is empty. Skipping related visualizations.")

    comparative_analysis.run_analysis(summary_df, dirs["comparative_statements"], dirs["cross_proxy_statements"])

    print("\n🎉 Analysis complete!")


if __name__ == "__main__":
    main()
