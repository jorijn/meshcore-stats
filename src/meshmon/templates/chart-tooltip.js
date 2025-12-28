/**
 * Chart tooltip enhancement for MeshCore Stats
 *
 * Progressive enhancement: charts work fully without JS,
 * but this adds interactive tooltips on hover.
 */
(function() {
  'use strict';

  // Create tooltip element
  const tooltip = document.createElement('div');
  tooltip.className = 'chart-tooltip';
  tooltip.innerHTML = '<div class="tooltip-time"></div><div class="tooltip-value"></div>';
  document.body.appendChild(tooltip);

  const tooltipTime = tooltip.querySelector('.tooltip-time');
  const tooltipValue = tooltip.querySelector('.tooltip-value');

  // Track the current indicator element
  let currentIndicator = null;
  let currentSvg = null;

  // Metric display labels and units
  const metricLabels = {
    'bat_v': { label: 'Voltage', unit: 'V', decimals: 2 },
    'bat_pct': { label: 'Battery', unit: '%', decimals: 0 },
    'rssi': { label: 'RSSI', unit: 'dBm', decimals: 0 },
    'snr': { label: 'SNR', unit: 'dB', decimals: 1 },
    'rx': { label: 'RX', unit: '/min', decimals: 1 },
    'tx': { label: 'TX', unit: '/min', decimals: 1 },
    'uptime': { label: 'Uptime', unit: 'days', decimals: 2 },
    'noise': { label: 'Noise', unit: 'dBm', decimals: 0 },
    'airtime': { label: 'Airtime', unit: 's/min', decimals: 2 },
    'rx_air': { label: 'RX Air', unit: 's/min', decimals: 2 },
    'contacts': { label: 'Contacts', unit: '', decimals: 0 },
    'txq': { label: 'TX Queue', unit: '', decimals: 0 },
    'fl_dups': { label: 'Flood Dups', unit: '/min', decimals: 1 },
    'di_dups': { label: 'Direct Dups', unit: '/min', decimals: 1 },
    'fl_tx': { label: 'Flood TX', unit: '/min', decimals: 1 },
    'fl_rx': { label: 'Flood RX', unit: '/min', decimals: 1 },
    'di_tx': { label: 'Direct TX', unit: '/min', decimals: 1 },
    'di_rx': { label: 'Direct RX', unit: '/min', decimals: 1 },
  };

  /**
   * Format a timestamp as a readable date/time string
   */
  function formatTime(ts, period) {
    const date = new Date(ts * 1000);
    const options = {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    };

    // For year view, include year
    if (period === 'year') {
      options.year = 'numeric';
    }

    return date.toLocaleString(undefined, options);
  }

  /**
   * Format a value with appropriate decimals and unit
   */
  function formatValue(value, metric) {
    const config = metricLabels[metric] || { label: metric, unit: '', decimals: 2 };
    const formatted = value.toFixed(config.decimals);
    return `${formatted}${config.unit ? ' ' + config.unit : ''}`;
  }

  /**
   * Find the closest data point to a timestamp, returning index too
   */
  function findClosestPoint(dataPoints, targetTs) {
    if (!dataPoints || dataPoints.length === 0) return null;

    let closestIdx = 0;
    let minDiff = Math.abs(dataPoints[0].ts - targetTs);

    for (let i = 1; i < dataPoints.length; i++) {
      const diff = Math.abs(dataPoints[i].ts - targetTs);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }

    return { point: dataPoints[closestIdx], index: closestIdx };
  }

  /**
   * Create or get the indicator circle for an SVG
   */
  function getIndicator(svg) {
    if (currentSvg === svg && currentIndicator) {
      return currentIndicator;
    }

    // Remove old indicator if switching charts
    if (currentIndicator && currentIndicator.parentNode) {
      currentIndicator.parentNode.removeChild(currentIndicator);
    }

    // Create new indicator as an SVG circle
    const indicator = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    indicator.setAttribute('r', '5');
    indicator.setAttribute('class', 'chart-indicator');
    indicator.style.pointerEvents = 'none';

    // Get theme from SVG data attribute for color
    const theme = svg.dataset.theme;
    if (theme === 'dark') {
      indicator.setAttribute('fill', '#f59e0b');
      indicator.setAttribute('stroke', '#0f1114');
    } else {
      indicator.setAttribute('fill', '#b45309');
      indicator.setAttribute('stroke', '#ffffff');
    }
    indicator.setAttribute('stroke-width', '2');

    svg.appendChild(indicator);
    currentIndicator = indicator;
    currentSvg = svg;

    return indicator;
  }

  /**
   * Hide and clean up the indicator
   */
  function hideIndicator() {
    if (currentIndicator) {
      currentIndicator.style.display = 'none';
    }
  }

  /**
   * Position tooltip near the mouse cursor
   */
  function positionTooltip(event) {
    const offset = 15;
    let left = event.pageX + offset;
    let top = event.pageY + offset;

    // Keep tooltip on screen
    const rect = tooltip.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (left + rect.width > viewportWidth - 10) {
      left = event.pageX - rect.width - offset;
    }
    if (top + rect.height > viewportHeight - 10) {
      top = event.pageY - rect.height - offset;
    }

    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }

  /**
   * Handle mouse move over chart SVG
   */
  function handleMouseMove(event) {
    const svg = event.currentTarget;
    const metric = svg.dataset.metric;
    const period = svg.dataset.period;
    const xStart = parseInt(svg.dataset.xStart, 10);
    const xEnd = parseInt(svg.dataset.xEnd, 10);
    const yMin = parseFloat(svg.dataset.yMin);
    const yMax = parseFloat(svg.dataset.yMax);

    // Find the data element (path for line charts, rect for bar charts)
    const dataElement = svg.querySelector('path[data-points], rect[data-points]');
    if (!dataElement) return;

    // Parse and cache data points and element coordinates on first access
    if (!dataElement._dataPoints) {
      try {
        const json = dataElement.dataset.points.replace(/&quot;/g, '"');
        dataElement._dataPoints = JSON.parse(json);
      } catch (e) {
        console.warn('Failed to parse chart data:', e);
        return;
      }
    }

    // Cache the element's bounding box for coordinate mapping
    if (!dataElement._pathBox) {
      dataElement._pathBox = dataElement.getBBox();
    }

    const pathBox = dataElement._pathBox;

    // Get mouse position in SVG coordinate space
    const svgRect = svg.getBoundingClientRect();
    const viewBox = svg.viewBox.baseVal;

    // Convert screen X coordinate to SVG coordinate
    const scaleX = viewBox.width / svgRect.width;
    const svgX = (event.clientX - svgRect.left) * scaleX + viewBox.x;

    // Calculate relative X position within the plot area (pathBox)
    const relX = (svgX - pathBox.x) / pathBox.width;

    // Clamp to plot area bounds
    const clampedRelX = Math.max(0, Math.min(1, relX));

    // Map relative X position to timestamp using the chart's X-axis range
    const targetTs = xStart + clampedRelX * (xEnd - xStart);

    // Find closest data point by timestamp
    const result = findClosestPoint(dataElement._dataPoints, targetTs);
    if (!result) return;

    const { point } = result;

    // Update tooltip content
    tooltipTime.textContent = formatTime(point.ts, period);
    tooltipValue.textContent = formatValue(point.v, metric);

    // Position and show tooltip
    positionTooltip(event);
    tooltip.classList.add('visible');

    // Position the indicator at the data point
    const indicator = getIndicator(svg);

    // Calculate X position: map timestamp to path coordinate space
    const pointRelX = (point.ts - xStart) / (xEnd - xStart);
    const indicatorX = pathBox.x + pointRelX * pathBox.width;

    // Calculate Y position using the actual Y-axis range from the chart
    const ySpan = yMax - yMin || 1;
    // Y is inverted in SVG (0 at top)
    const pointRelY = 1 - (point.v - yMin) / ySpan;
    const indicatorY = pathBox.y + pointRelY * pathBox.height;

    indicator.setAttribute('cx', indicatorX);
    indicator.setAttribute('cy', indicatorY);
    indicator.style.display = '';
  }

  /**
   * Hide tooltip when leaving chart
   */
  function handleMouseLeave() {
    tooltip.classList.remove('visible');
    hideIndicator();
  }

  /**
   * Handle touch events for mobile
   */
  function handleTouchStart(event) {
    // Prevent scrolling while interacting with chart
    event.preventDefault();

    // Convert touch to mouse-like event
    const touch = event.touches[0];
    const mouseEvent = {
      currentTarget: event.currentTarget,
      clientX: touch.clientX,
      clientY: touch.clientY,
      pageX: touch.pageX,
      pageY: touch.pageY
    };

    handleMouseMove(mouseEvent);
  }

  function handleTouchMove(event) {
    event.preventDefault();

    const touch = event.touches[0];
    const mouseEvent = {
      currentTarget: event.currentTarget,
      clientX: touch.clientX,
      clientY: touch.clientY,
      pageX: touch.pageX,
      pageY: touch.pageY
    };

    handleMouseMove(mouseEvent);
  }

  function handleTouchEnd() {
    handleMouseLeave();
  }

  /**
   * Initialize tooltips for all chart SVGs
   */
  function initTooltips() {
    // Find all chart SVGs with data attributes
    const chartSvgs = document.querySelectorAll('svg[data-metric][data-period]');

    chartSvgs.forEach(function(svg) {
      // Mouse events for desktop
      svg.addEventListener('mousemove', handleMouseMove);
      svg.addEventListener('mouseleave', handleMouseLeave);

      // Touch events for mobile
      svg.addEventListener('touchstart', handleTouchStart, { passive: false });
      svg.addEventListener('touchmove', handleTouchMove, { passive: false });
      svg.addEventListener('touchend', handleTouchEnd);
      svg.addEventListener('touchcancel', handleTouchEnd);

      // Set cursor to indicate interactivity
      svg.style.cursor = 'crosshair';
    });

    if (chartSvgs.length > 0) {
      console.log('Chart tooltips initialized for', chartSvgs.length, 'charts');
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTooltips);
  } else {
    initTooltips();
  }
})();
