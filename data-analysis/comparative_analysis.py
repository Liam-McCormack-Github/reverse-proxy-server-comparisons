from pathlib import Path
from typing import List

import pandas as pd

import config


def generate_comparative_statements(summary_df: pd.DataFrame) -> List[str]:
    statements = ["\nComparative Metric Statements (Intra-Proxy)"]

    metrics_to_compare = config.COMPARATIVE_METRICS_MAP

    for test_type in sorted(summary_df['test_type'].unique()):
        for proxy in sorted(summary_df['proxy'].unique()):
            df_filtered = summary_df[(summary_df['proxy'] == proxy) & (summary_df['test_type'] == test_type)].copy()
            if len(df_filtered) < 2:
                continue

            df_filtered['users_numeric'] = df_filtered['users'].str.replace('k', '').astype(int)
            df_filtered = df_filtered.sort_values('users_numeric')

            statements.append(f"\nComparisons for {proxy} ({test_type.title()} test) as User Load Increases")

            for metric_name, metric_col in metrics_to_compare.items():
                if metric_col not in df_filtered.columns or df_filtered[metric_col].isnull().all():
                    continue

                df_metric = df_filtered.dropna(subset=[metric_col])
                if len(df_metric) < 2:
                    continue

                parts = []
                for i in range(len(df_metric) - 1):
                    row_old, row_new = df_metric.iloc[i], df_metric.iloc[i + 1]
                    val_old, val_new = row_old[metric_col], row_new[metric_col]

                    if pd.isna(val_old) or pd.isna(val_new):
                        continue

                    is_count = "Count" in metric_name or "Requests" in metric_name

                    if is_count:
                        val_old_str, val_new_str = f"{val_old:,.0f}", f"{val_new:,.0f}"
                    else:
                        val_old_str, val_new_str = f"{val_old:.5f}", f"{val_new:.5f}"

                    if val_old > 0:
                        pct_change = ((val_new - val_old) / val_old) * 100
                        change_type = "increase" if pct_change >= 0 else "decrease"

                        if any(keyword in metric_name for keyword in [
                            "Latency", "TTFB", "Connection Time", "CPU", "Memory",
                            "Failure", "Duration", "Time", "Usage"
                        ]):
                            trend = "worsening" if pct_change > 0 else "improving" if pct_change < 0 else "stable"
                        else:
                            trend = "improving" if pct_change > 0 else "worsening" if pct_change < 0 else "stable"

                        part = (f"from {row_old['users']} to {row_new['users']}: {abs(pct_change):.5f}% {change_type} "f"({trend}, from {val_old_str} to {val_new_str})")
                    else:
                        part = f"from {row_old['users']} to {row_new['users']}: changed from {val_old_str} to {val_new_str}"

                    parts.append(part)

                if parts:
                    statement = f"\t{metric_name}: " + "; ".join(parts) + "."
                    statements.append(statement.replace('0.00000', '0.0'))

    return statements


def generate_cross_proxy_statements(summary_df: pd.DataFrame) -> List[str]:
    statements = ["\nCross-Proxy Comparative Statements (Pairwise Comparisons)"]

    metrics_to_compare = config.COMPARATIVE_METRICS_MAP

    for (test_type, users), group in summary_df.groupby(['test_type', 'users']):
        if len(group) < 2:
            continue

        statements.append(f"\nComparison for {test_type.title()} Test @ {users} Users")

        for metric_name, metric_col in metrics_to_compare.items():
            if metric_col not in group.columns or group[metric_col].isnull().all():
                continue

            df_metric = group.dropna(subset=[metric_col])
            if len(df_metric) < 2:
                continue

            parts = []
            proxies = df_metric['proxy'].tolist()
            values = df_metric[metric_col].tolist()

            pairs = []
            for i in range(len(proxies)):
                for j in range(i + 1, len(proxies)):
                    pairs.append((i, j))

            pairs.sort()

            for i, j in pairs:
                proxy1, proxy2 = proxies[i], proxies[j]
                val1, val2 = values[i], values[j]

                if pd.isna(val1) or pd.isna(val2):
                    continue

                is_count = "Count" in metric_name or "Requests" in metric_name

                if is_count:
                    val1_str, val2_str = f"{val1:,.0f}", f"{val2:,.0f}"
                else:
                    val1_str, val2_str = f"{val1:.5f}", f"{val2:.5f}"

                if val1 > 0 and val2 > 0:
                    if any(keyword in metric_name for keyword in [
                        "Latency", "TTFB", "Connection Time", "CPU", "Memory",
                        "Failure", "Duration", "Time", "Usage"
                    ]):
                        if val1 < val2:
                            pct_diff = ((val2 - val1) / val1) * 100
                            part = f"{proxy1} was {pct_diff:.5f}% better than {proxy2} ({val1_str} vs {val2_str})"
                        else:
                            pct_diff = ((val1 - val2) / val2) * 100
                            part = f"{proxy2} was {pct_diff:.5f}% better than {proxy1} ({val2_str} vs {val1_str})"
                    else:
                        if val1 > val2:
                            pct_diff = ((val1 - val2) / val2) * 100
                            part = f"{proxy1} was {pct_diff:.5f}% better than {proxy2} ({val1_str} vs {val2_str})"
                        else:
                            pct_diff = ((val2 - val1) / val1) * 100
                            part = f"{proxy2} was {pct_diff:.5f}% better than {proxy1} ({val2_str} vs {val1_str})"
                else:
                    part = f"{proxy1} ({val1_str}) vs {proxy2} ({val2_str})"

                parts.append(part)

            if parts:
                statement = f"\t{metric_name}: " + "; ".join(parts) + "."
                statements.append(statement.replace('0.00000', '0.0'))

    return statements


def run_analysis(summary_df: pd.DataFrame, comparative_dir: Path, cross_proxy_dir: Path):
    print("\n📊 Starting Comparative Analysis Statements...")
    if summary_df.empty:
        print(" -> ⚠️ Summary DataFrame is empty. Skipping statement generation.")
        return

    comparative_statements = generate_comparative_statements(summary_df)
    cross_proxy_statements = generate_cross_proxy_statements(summary_df)

    try:
        comp_output_path = comparative_dir / "comparative_analysis_log.txt"
        with open(comp_output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(s.lstrip('\n') for s in comparative_statements))
        print(f"\n -> ✅ Saved comparative analysis statements to: {comp_output_path}")
    except IOError as e:
        print(f" -> ❌ Error writing comparative statements to file: {e}")

    try:
        cross_output_path = cross_proxy_dir / "cross_proxy_analysis_log.txt"
        with open(cross_output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(s.lstrip('\n') for s in cross_proxy_statements))
        print(f" -> ✅ Saved cross-proxy analysis statements to: {cross_output_path}")
    except IOError as e:
        print(f" -> ❌ Error writing cross-proxy statements to file: {e}")

    print("\n✅ Comparative analysis statements complete!")
