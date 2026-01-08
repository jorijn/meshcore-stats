# Pytest slow test report (>2s)

Command:
`MPLCONFIGDIR=/tmp/matplotlib uv run pytest --durations=0 -q`

Result: 1135 passed in 117.80s
Total time saved vs previous run: 16.07s

Sorted by total duration per test (setup + call + teardown), only tests >2s.

| Duration (s) | Saved vs previous (s) | Test | Slow phase(s) | Why it is slow |
| --- | --- | --- | --- | --- |
| 43.75 | +3.07 | tests/integration/test_rendering_pipeline.py::TestChartRenderingPipeline::test_renders_all_chart_periods | setup:43.74s, call:0.01s | First test triggers module-scoped chart cache: inserts 30 days of metrics and renders all charts for both roles; Matplotlib rendering dominates. |
| 36.00 | +1.62 | tests/integration/test_reports_pipeline.py::TestReportGenerationPipeline::test_generates_monthly_reports | setup:35.83s, call:0.17s | First test triggers module-scoped reports DB cache: inserts 30 days of metrics; monthly aggregation and formatting follow. |
| 7.61 | +0.43 | tests/html/test_write_site.py::TestWriteSite::test_creates_output_directory | setup:7.58s, call:0.03s | First test triggers module-scoped HTML DB cache (7 days of data) and runs write_site to render full HTML output. |
| 6.83 | +0.12 | tests/integration/test_rendering_pipeline.py::TestFullRenderingChain::test_empty_database_renders_gracefully | call:6.82s, setup:0.01s | Calls render_all_charts for both roles even with empty DB; chart rendering and asset writes take time. |

Notes:
- Yearly aggregation tests now run under 2s after skipping months with no data.
- Several report pipeline and HTML write_site tests remain below 2s due to shared DB caches.