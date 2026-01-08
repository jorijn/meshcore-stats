# Pytest slow test report (>2s)

Command:
`MPLCONFIGDIR=/tmp/matplotlib uv run pytest --durations=0 -q`

Result: 1135 passed in 133.87s
Total time saved vs previous run: 416.82s

Sorted by total duration per test (setup + call + teardown), only tests >2s.

| Duration (s) | Saved vs previous (s) | Test | Slow phase(s) | Why it is slow |
| --- | --- | --- | --- | --- |
| 46.82 | +34.96 | tests/integration/test_rendering_pipeline.py::TestChartRenderingPipeline::test_renders_all_chart_periods | setup:46.81s, call:0.01s | First test triggers module-scoped chart cache: inserts 30 days of metrics and renders all charts for both roles; Matplotlib rendering dominates. |
| 37.62 | +22.44 | tests/integration/test_reports_pipeline.py::TestReportGenerationPipeline::test_generates_monthly_reports | setup:37.43s, call:0.19s | First test triggers module-scoped reports DB cache: inserts 30 days of metrics; monthly aggregation and formatting follow. |
| 8.04 | +5.31 | tests/html/test_write_site.py::TestWriteSite::test_creates_output_directory | setup:8.02s, call:0.02s | First test triggers module-scoped HTML DB cache (7 days of data) and runs write_site to render full HTML output. |
| 6.95 | +1.01 | tests/integration/test_rendering_pipeline.py::TestFullRenderingChain::test_empty_database_renders_gracefully | call:6.87s, setup:0.08s | Calls render_all_charts for both roles even with empty DB; chart rendering and asset writes take time. |
| 4.84 | -2.15 | tests/reports/test_aggregation.py::TestAggregateYearly::test_handles_leap_year | call:4.83s, setup:0.01s | aggregate_yearly iterates months/days and runs daily DB queries; loop cost dominates even with limited data. |
| 3.87 | -0.78 | tests/reports/test_aggregation.py::TestAggregateYearly::test_returns_empty_for_no_data | call:3.86s, setup:0.01s | aggregate_yearly still loops through months/days and queries for each day despite no data. |
| 3.71 | -1.17 | tests/reports/test_aggregation.py::TestAggregateYearly::test_returns_yearly_aggregate | call:3.70s, setup:0.01s | aggregate_yearly loops months/days and aggregates daily data, which is query-heavy. |
| 3.46 | +1.48 | tests/reports/test_aggregation.py::TestAggregateYearly::test_aggregates_all_months | call:3.39s, setup:0.07s | aggregate_yearly iterates months/days and aggregates daily data; loop + DB reads dominate. |

Notes:
- Several report pipeline and HTML write_site tests dropped below 2s due to the shared DB cache and no longer appear here.