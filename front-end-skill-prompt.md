Base directory for this skill: /Users/jorijn/.claude/plugins/cache/claude-code-plugins/frontend-design/1.0.0/skills/frontend-design

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.

ARGUMENTS: ## Project: MeshCore Stats Dashboard - Complete Frontend Redesign

Create a complete frontend redesign for a LoRa mesh network monitoring dashboard. This monitors solar-powered radio nodes in the Netherlands. Write all output to `/Users/jorijn/Development/meshcore-stats/redesign/` directory.

### CRITICAL CONSTRAINTS
- You MUST NOT look at or reference ANY existing HTML/CSS in this project
- Create everything from scratch based ONLY on the data and requirements below
- Be creative and distinctive - avoid generic dashboard aesthetics
- Output static HTML/CSS files (no JavaScript frameworks, minimal vanilla JS for theme detection only)

### DESIGN DIRECTION
- **Minimalist, data-focused, typography-driven**
- **Full data density** - show all metrics, but group logically and order by importance
- **Dark & light mode** via CSS `prefers-color-scheme` media query ONLY (no toggle buttons)
- **Emphasize**: Solar-powered nature, LoRa radio technology
- **Sidebar approach inspiration**: Consider a layout where node info and latest snapshot data sits alongside charts (like weather.jorijn.com), but challenge this - be creative about what works best for this specific data

### WHAT YOU'RE MONITORING

**The Network:**
- 1 Companion node (local, USB-connected to a server)
- 1 Repeater node (remote, solar-powered Seeed SenseCAP P1-Pro)
- Location: Oosterhout, The Netherlands (51.6674°N, 4.8597°E, 10m elevation)
- Radio: MeshCore EU/UK Narrow preset (869.618 MHz, 62.5 kHz BW, SF8, CR8)
- Communication: LoRa (Long Range radio)

### DATA TO DISPLAY

#### Repeater Node (Primary - Solar-powered remote device)
**Critical metrics (highest priority):**
- Battery voltage: 3.0-4.2V range
- Battery percentage: 0-100%
- RSSI: Signal strength in dBm (negative values, e.g., -80 dBm)
- SNR: Signal-to-noise ratio in dB (e.g., 12.25 dB)
- Uptime: Days since reboot

**Secondary metrics:**
- Noise floor: Background RF noise in dBm
- TX queue length: Pending transmissions

**Traffic metrics (counters, displayed as rates):**
- rx/tx: Total packets received/transmitted (packets/min)
- airtime/rx_air: TX/RX airtime (seconds/min)
- fl_tx/fl_rx: Flood packets TX/RX
- di_tx/di_rx: Direct packets TX/RX
- fl_dups/di_dups: Duplicate packets (flood/direct)

**Snapshot metadata:**
- Node name: "jorijn.com Repeater N"
- Public key prefix: "4a84535b9e5f"
- Last update timestamp

#### Companion Node (Secondary - Local USB device)
**Metrics:**
- Battery voltage & percentage
- Contacts count (known mesh nodes)
- rx/tx packets
- Uptime

**Additional snapshot data:**
- Device model: "Elecrow ThinkNode-M1"
- Firmware: "v1.11.0-6d32193"
- Radio settings (freq, bandwidth, SF, CR)
- Contact list with names

### STATUS INDICATOR
Based on data freshness:
- Online (green): Data < 30 minutes old
- Stale (yellow): Data 30 min - 2 hours old
- Offline (red): Data > 2 hours old

### PAGE STRUCTURE

#### Main Dashboard Pages (8 total)
Create templates for these time periods:
- day.html, week.html, month.html, year.html (for Repeater at root)
- companion/day.html, week.html, month.html, year.html

Each page needs:
- Navigation between nodes (Repeater/Companion)
- Navigation between time periods (Day/Week/Month/Year)
- Latest snapshot data display
- Node information section
- Charts grid (pre-rendered PNG images at 800x280px)

Charts are already generated as PNG files at paths like:
- `/assets/repeater/{metric}_{period}_{theme}.png`
- `/assets/companion/{metric}_{period}_{theme}.png`

Where metric is: bat_v, bat_pct, rx, tx, rssi, snr, uptime, noise, airtime, rx_air, fl_dups, di_dups, fl_tx, fl_rx, di_tx, di_rx, txq (repeater) or bat_v, bat_pct, contacts, rx, tx, uptime (companion)

Period is: day, week, month, year
Theme is: light, dark

Use picture element with source media queries to swap light/dark chart images based on prefers-color-scheme.

#### Reports Section
- /reports/index.html - Archive listing of all available reports
- /reports/repeater/2025/index.html - Yearly report template
- /reports/repeater/2025/12/index.html - Monthly report template
- Same structure for companion

Reports display aggregated statistics in table format:
**Monthly reports show daily rows with:**
- Date
- Battery: mean voltage, %, min/max with times
- Signal: RSSI, SNR, noise floor (means)
- Packets: RX total, TX total
- Airtime total

**Yearly reports show monthly rows with:**
- Month
- Battery: mean, high/low with dates
- Signal: RSSI, SNR means
- Packets: RX/TX totals

Reports are data-dense archive pages - can use compact table formatting.

### RRDTOOL CHART COLOR PALETTE

Create a matching color palette for the RRD charts. The charts are generated with rrdtool and need these color definitions:

```python
# Format needed - hex colors without #
CHART_THEMES = {
    "light": {
        "back": "ffffff",      # Background
        "canvas": "ffffff",    # Chart area background
        "font": "1e293b",      # Text color
        "axis": "64748b",      # Axis labels
        "frame": "e2e8f0",     # Chart frame
        "arrow": "64748b",     # Axis arrows
        "grid": "e2e8f0",      # Grid lines
        "mgrid": "cbd5e1",     # Major grid lines
        "line": "2563eb",      # Data line color
        "area": "2563eb40",    # Area fill (with alpha)
    },
    "dark": {
        # ... dark theme colors
    }
}
```

Output this as a separate file: `redesign/chart_colors.py` with the color definitions that match your HTML/CSS design.

### DELIVERABLES

Create these files in `/Users/jorijn/Development/meshcore-stats/redesign/`:

1. `styles.css` - Complete stylesheet with light/dark themes via prefers-color-scheme
2. `day.html` - Repeater day view (main entry point template)
3. `week.html` - Repeater week view template
4. `month.html` - Repeater month view template  
5. `year.html` - Repeater year view template
6. `companion/day.html` - Companion day view template
7. `companion/week.html` - Companion week view template
8. `companion/month.html` - Companion month view template
9. `companion/year.html` - Companion year view template
10. `reports/index.html` - Reports archive listing
11. `reports/monthly.html` - Monthly report template
12. `reports/yearly.html` - Yearly report template
13. `chart_colors.py` - RRDtool color palette matching the design

### PLACEHOLDER DATA
Use realistic placeholder data based on the actual values I've shown you. For example:
- Battery: 4.08V, 85%
- RSSI: -80 dBm
- SNR: 12.25 dB
- Uptime: 11.6 days
- Node name: "jorijn.com Repeater N"
- Etc.

### DESIGN NOTES
- This is for monitoring radio equipment - the aesthetic should reflect that context
- Solar-powered means battery life is critical - make battery status prominent
- LoRa is long-range, low-power radio - signal quality matters
- The Netherlands location can subtly inform the design if relevant
- Charts are the main content - they should be prominent and easy to scan
- Typography should be distinctive but highly legible for data
- Consider how radio operators, weather stations, or scientific monitoring dashboards present data

Be bold and creative. Make unexpected choices. Avoid the generic "dashboard with cards" look that AI tends to produce.
