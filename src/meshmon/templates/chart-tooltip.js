/**
 * Chart Tooltip Enhancement for MeshCore Stats
 *
 * Progressive enhancement: charts display fully without JavaScript.
 * This module adds interactive tooltips showing datetime and value on hover,
 * with an indicator dot that follows the data line.
 *
 * Data sources:
 * - Data points: path.dataset.points or svg.dataset.points (JSON array of {ts, v})
 * - Time range: svg.dataset.xStart, svg.dataset.xEnd (Unix timestamps)
 * - Value range: svg.dataset.yMin, svg.dataset.yMax
 * - Plot bounds: Derived from clipPath rect or line path bounding box
 */
(function () {
  'use strict';

  // ============================================================================
  // Configuration
  // ============================================================================

  var CONFIG = {
    tooltipOffset: 15,
    viewportPadding: 10,
    indicatorRadius: 5,
    indicatorStrokeWidth: 2,
    colors: {
      light: { fill: '#b45309', stroke: '#ffffff' },
      dark: { fill: '#f59e0b', stroke: '#0f1114' }
    }
  };

  /**
   * Metric display configuration keyed by firmware field name.
   * Each entry defines how to format values for that metric.
   */
  var METRIC_CONFIG = {
    // Companion metrics
    battery_mv: { label: 'Voltage', unit: 'V', decimals: 2 },
    uptime_secs: { label: 'Uptime', unit: 'days', decimals: 2 },
    contacts: { label: 'Contacts', unit: '', decimals: 0 },
    recv: { label: 'Received', unit: '/min', decimals: 1 },
    sent: { label: 'Sent', unit: '/min', decimals: 1 },

    // Repeater metrics
    bat: { label: 'Voltage', unit: 'V', decimals: 2 },
    bat_pct: { label: 'Charge', unit: '%', decimals: 0 },
    uptime: { label: 'Uptime', unit: 'days', decimals: 2 },
    last_rssi: { label: 'RSSI', unit: 'dBm', decimals: 0 },
    last_snr: { label: 'SNR', unit: 'dB', decimals: 1 },
    noise_floor: { label: 'Noise', unit: 'dBm', decimals: 0 },
    tx_queue_len: { label: 'Queue', unit: '', decimals: 0 },
    nb_recv: { label: 'Received', unit: '/min', decimals: 1 },
    nb_sent: { label: 'Sent', unit: '/min', decimals: 1 },
    airtime: { label: 'TX Air', unit: 's/min', decimals: 2 },
    rx_airtime: { label: 'RX Air', unit: 's/min', decimals: 2 },
    flood_dups: { label: 'Dropped', unit: '/min', decimals: 1 },
    direct_dups: { label: 'Dropped', unit: '/min', decimals: 1 },
    sent_flood: { label: 'Sent', unit: '/min', decimals: 1 },
    recv_flood: { label: 'Received', unit: '/min', decimals: 1 },
    sent_direct: { label: 'Sent', unit: '/min', decimals: 1 },
    recv_direct: { label: 'Received', unit: '/min', decimals: 1 }
  };

  // ============================================================================
  // Formatting Utilities
  // ============================================================================

  /**
   * Format a Unix timestamp as a localized date/time string.
   * Uses browser language preference for locale (determines 12/24 hour format).
   * Includes year only for year-period charts.
   */
  function formatTimestamp(timestamp, period) {
    var date = new Date(timestamp * 1000);
    var options = {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      timeZoneName: 'short'
    };

    if (period === 'year') {
      options.year = 'numeric';
    }

    // Use browser's language preference (navigator.language), not system locale
    // Empty array [] or undefined would use OS regional settings instead
    return date.toLocaleString(navigator.language, options);
  }

  /**
   * Format a numeric value with the appropriate decimals and unit for a metric.
   */
  function formatMetricValue(value, metric) {
    var config = METRIC_CONFIG[metric] || { label: metric, unit: '', decimals: 2 };
    var formatted = value.toFixed(config.decimals);
    return config.unit ? formatted + ' ' + config.unit : formatted;
  }

  // ============================================================================
  // Data Point Utilities
  // ============================================================================

  /**
   * Find the data point closest to the target timestamp.
   * Returns the point object or null if no points available.
   */
  function findClosestDataPoint(dataPoints, targetTimestamp) {
    if (!dataPoints || dataPoints.length === 0) {
      return null;
    }

    var closest = dataPoints[0];
    var minDiff = Math.abs(closest.ts - targetTimestamp);

    for (var i = 1; i < dataPoints.length; i++) {
      var diff = Math.abs(dataPoints[i].ts - targetTimestamp);
      if (diff < minDiff) {
        minDiff = diff;
        closest = dataPoints[i];
      }
    }

    return closest;
  }

  /**
   * Parse and cache data points on an SVG element.
   * Handles HTML entity encoding from server-side JSON embedding.
   */
  function getDataPoints(svg, rawJson) {
    if (svg._dataPoints) {
      return svg._dataPoints;
    }

    try {
      var json = rawJson.replace(/&quot;/g, '"');
      svg._dataPoints = JSON.parse(json);
      return svg._dataPoints;
    } catch (error) {
      console.warn('Chart tooltip: failed to parse data points', error);
      return null;
    }
  }

  // ============================================================================
  // SVG Coordinate Utilities
  // ============================================================================

  /**
   * Get and cache the plot area bounds for an SVG chart.
   * Prefers the clip path rect (defines full plot area) over line path bbox
   * (which only covers the actual data range).
   */
  function getPlotAreaBounds(svg, fallbackPath) {
    if (svg._plotArea) {
      return svg._plotArea;
    }

    var clipRect = svg.querySelector('clipPath rect');
    if (clipRect) {
      svg._plotArea = {
        x: parseFloat(clipRect.getAttribute('x')),
        y: parseFloat(clipRect.getAttribute('y')),
        width: parseFloat(clipRect.getAttribute('width')),
        height: parseFloat(clipRect.getAttribute('height'))
      };
    } else if (fallbackPath) {
      svg._plotArea = fallbackPath.getBBox();
    }

    return svg._plotArea;
  }

  /**
   * Find the chart line path element within an SVG.
   * Tries multiple selectors for compatibility with different SVG structures.
   */
  function findLinePath(svg) {
    return (
      svg.querySelector('#chart-line path') ||
      svg.querySelector('path#chart-line') ||
      svg.querySelector('[gid="chart-line"] path') ||
      svg.querySelector('path[gid="chart-line"]') ||
      svg.querySelector('path[data-points]')
    );
  }

  /**
   * Convert a screen X coordinate to SVG coordinate space.
   */
  function screenToSvgX(svg, clientX) {
    var svgRect = svg.getBoundingClientRect();
    var viewBox = svg.viewBox.baseVal;
    var scale = viewBox.width / svgRect.width;
    return (clientX - svgRect.left) * scale + viewBox.x;
  }

  /**
   * Map a timestamp to an X coordinate within the plot area.
   */
  function timestampToX(timestamp, xStart, xEnd, plotArea) {
    var relativePosition = (timestamp - xStart) / (xEnd - xStart);
    return plotArea.x + relativePosition * plotArea.width;
  }

  /**
   * Map a value to a Y coordinate within the plot area.
   * SVG Y-axis is inverted (0 at top), so higher values map to lower Y.
   */
  function valueToY(value, yMin, yMax, plotArea) {
    var ySpan = yMax - yMin || 1;
    var relativePosition = (value - yMin) / ySpan;
    return plotArea.y + plotArea.height - relativePosition * plotArea.height;
  }

  // ============================================================================
  // Tooltip Element
  // ============================================================================

  var tooltip = null;
  var tooltipTimeEl = null;
  var tooltipValueEl = null;

  /**
   * Create the tooltip DOM element (called once on init).
   */
  function createTooltipElement() {
    tooltip = document.createElement('div');
    tooltip.className = 'chart-tooltip';
    tooltip.innerHTML =
      '<div class="tooltip-time"></div>' + '<div class="tooltip-value"></div>';
    document.body.appendChild(tooltip);

    tooltipTimeEl = tooltip.querySelector('.tooltip-time');
    tooltipValueEl = tooltip.querySelector('.tooltip-value');
  }

  /**
   * Update tooltip content and position it near the cursor.
   */
  function showTooltip(event, timeText, valueText) {
    tooltipTimeEl.textContent = timeText;
    tooltipValueEl.textContent = valueText;

    var left = event.pageX + CONFIG.tooltipOffset;
    var top = event.pageY + CONFIG.tooltipOffset;

    // Keep tooltip within viewport
    var rect = tooltip.getBoundingClientRect();
    if (left + rect.width > window.innerWidth - CONFIG.viewportPadding) {
      left = event.pageX - rect.width - CONFIG.tooltipOffset;
    }
    if (top + rect.height > window.innerHeight - CONFIG.viewportPadding) {
      top = event.pageY - rect.height - CONFIG.tooltipOffset;
    }

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
    tooltip.classList.add('visible');
  }

  /**
   * Hide the tooltip.
   */
  function hideTooltip() {
    tooltip.classList.remove('visible');
  }

  // ============================================================================
  // Indicator Dot
  // ============================================================================

  var currentIndicator = null;
  var currentIndicatorSvg = null;

  /**
   * Get or create the indicator circle for an SVG chart.
   * Reuses existing indicator if still on the same chart.
   */
  function getIndicator(svg) {
    if (currentIndicatorSvg === svg && currentIndicator) {
      return currentIndicator;
    }

    // Remove indicator from previous chart
    if (currentIndicator && currentIndicator.parentNode) {
      currentIndicator.parentNode.removeChild(currentIndicator);
    }

    // Create new indicator circle
    var indicator = document.createElementNS(
      'http://www.w3.org/2000/svg',
      'circle'
    );
    indicator.setAttribute('r', CONFIG.indicatorRadius);
    indicator.setAttribute('class', 'chart-indicator');
    indicator.setAttribute('stroke-width', CONFIG.indicatorStrokeWidth);
    indicator.style.pointerEvents = 'none';

    // Apply theme-appropriate colors
    var theme = svg.dataset.theme === 'dark' ? 'dark' : 'light';
    indicator.setAttribute('fill', CONFIG.colors[theme].fill);
    indicator.setAttribute('stroke', CONFIG.colors[theme].stroke);

    svg.appendChild(indicator);
    currentIndicator = indicator;
    currentIndicatorSvg = svg;

    return indicator;
  }

  /**
   * Position the indicator at a specific data point.
   */
  function positionIndicator(svg, dataPoint, xStart, xEnd, yMin, yMax, plotArea) {
    var indicator = getIndicator(svg);
    var x = timestampToX(dataPoint.ts, xStart, xEnd, plotArea);
    var y = valueToY(dataPoint.v, yMin, yMax, plotArea);

    indicator.setAttribute('cx', x);
    indicator.setAttribute('cy', y);
    indicator.style.display = '';
  }

  /**
   * Hide the indicator dot.
   */
  function hideIndicator() {
    if (currentIndicator) {
      currentIndicator.style.display = 'none';
    }
  }

  // ============================================================================
  // Event Handlers
  // ============================================================================

  /**
   * Convert a touch event to a mouse-like event object.
   */
  function touchToMouseEvent(touchEvent) {
    var touch = touchEvent.touches[0];
    return {
      currentTarget: touchEvent.currentTarget,
      clientX: touch.clientX,
      clientY: touch.clientY,
      pageX: touch.pageX,
      pageY: touch.pageY
    };
  }

  /**
   * Handle pointer movement over a chart (mouse or touch).
   * Finds the closest data point and updates tooltip and indicator.
   */
  function handlePointerMove(event) {
    var svg = event.currentTarget;

    // Extract chart metadata
    var metric = svg.dataset.metric;
    var period = svg.dataset.period;
    var xStart = parseInt(svg.dataset.xStart, 10);
    var xEnd = parseInt(svg.dataset.xEnd, 10);
    var yMin = parseFloat(svg.dataset.yMin);
    var yMax = parseFloat(svg.dataset.yMax);

    // Find the line path and data points source
    var linePath = findLinePath(svg);
    if (!linePath) {
      return;
    }

    var rawPoints = linePath.dataset.points || svg.dataset.points;
    if (!rawPoints) {
      return;
    }

    // Parse data points (cached on svg element)
    var dataPoints = getDataPoints(svg, rawPoints);
    if (!dataPoints) {
      return;
    }

    // Get plot area bounds (cached on svg element)
    var plotArea = getPlotAreaBounds(svg, linePath);
    if (!plotArea) {
      return;
    }

    // Convert screen position to timestamp
    var svgX = screenToSvgX(svg, event.clientX);
    var relativeX = Math.max(0, Math.min(1, (svgX - plotArea.x) / plotArea.width));
    var targetTimestamp = xStart + relativeX * (xEnd - xStart);

    // Find and display closest data point
    var closestPoint = findClosestDataPoint(dataPoints, targetTimestamp);
    if (!closestPoint) {
      return;
    }

    showTooltip(
      event,
      formatTimestamp(closestPoint.ts, period),
      formatMetricValue(closestPoint.v, metric)
    );

    positionIndicator(svg, closestPoint, xStart, xEnd, yMin, yMax, plotArea);
  }

  /**
   * Handle pointer leaving the chart area.
   */
  function handlePointerLeave() {
    hideTooltip();
    hideIndicator();
  }

  /**
   * Handle touch start event.
   */
  function handleTouchStart(event) {
    handlePointerMove(touchToMouseEvent(event));
  }

  /**
   * Handle touch move event.
   */
  function handleTouchMove(event) {
    handlePointerMove(touchToMouseEvent(event));
  }

  // ============================================================================
  // Initialization
  // ============================================================================

  /**
   * Attach event listeners to all chart SVG elements.
   */
  function initializeChartTooltips() {
    createTooltipElement();

    var chartSvgs = document.querySelectorAll('svg[data-metric][data-period]');

    chartSvgs.forEach(function (svg) {
      // Desktop mouse events
      svg.addEventListener('mousemove', handlePointerMove);
      svg.addEventListener('mouseleave', handlePointerLeave);

      // Mobile touch events
      svg.addEventListener('touchstart', handleTouchStart, { passive: true });
      svg.addEventListener('touchmove', handleTouchMove, { passive: true });
      svg.addEventListener('touchend', handlePointerLeave);
      svg.addEventListener('touchcancel', handlePointerLeave);

      // Visual affordance for interactivity
      svg.style.cursor = 'crosshair';
      svg.style.touchAction = 'pan-y';
    });
  }

  // Run initialization when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeChartTooltips);
  } else {
    initializeChartTooltips();
  }
})();
