# Extractable components — SPPF Dashboard

Caveat: this repo has **no reusable component files**. Its UI is inline HTML
strings composed from CSS classes in `src/output/theme.py::inject_css()`. So the
extractable units below are *patterns* — each is defined once in the stylesheet
and re-instantiated across views. Source paths point at the class definition
(`theme.py`) plus a representative call site.

## Layout components (appear on most pages)

### Sidebar
- Source: `src/output/sidebar.py` (`render_sidebar`), styling in `src/output/theme.py:312-447`
- Category: layout
- Description: Persistent left panel — brand block, two-tier radio nav, global filters, disclaimer footnote
- Extractable props: `activeView` (string, default: "Insights & Actions"), `auditExpanded` (boolean, default: false), `disabledFilters` (string[], default: [])
- Hardcoded: 🔬 SPPF wordmark, "Silent Patient Pool Finder", "IQVIA Market Access Intelligence", the 3 + 8 nav labels and emoji, the disclaimer text, "v2.0 — 7-Dimension Framework", all CSS

### PageBanner
- Source: `src/output/theme.py:177-182` (`.banner`); call sites `views/insights.py:96`, `views/market_overview.py:33`, `views/hcp_targeting.py:48`, `views/campaign_measurement.py:21`
- Category: layout
- Description: Full-width gradient page header — eyebrow title, hero statistic, fine-print note; opens every view
- Extractable props: `title` (string), `stat` (string), `note` (string), `showInfoIcon` (boolean, default: false)
- Hardcoded: navy→cyan 135° gradient, 16px radius, 1.4rem 2rem padding, type scale (1rem/2.4rem/.75rem)

### AppShell
- Source: `src/output/dashboard.py`; container styling `src/output/theme.py:146-148`
- Category: layout
- Description: Page background `#F0F6FC`, 1600px max-width content column, Streamlit chrome hidden, sidebar beside it
- Extractable props: `sidebarCollapsed` (boolean, default: false)
- Hardcoded: max-width, padding, `#MainMenu/footer/header` suppression

### SidebarCollapseToggle
- Source: `src/output/theme.py:320-361`
- Category: layout
- Description: Restyled Streamlit collapse/expand control — 34px pale-blue button with border and shadow, hover inverts
- Extractable props: `collapsed` (boolean, default: false)
- Hardcoded: 34×34px, `#DEEEF9` fill, `#0077C8` border, 8px radius, 20px icon

## Basic components (used across pages)

### KpiCard
- Source: `src/output/theme.py:150-152` (`.card`) + `.label`/`.big-num`/`.sub`; call sites `views/geographic.py:38-41`, `views/market_overview.py:46-52`, `views/payer_landscape.py:46-49`
- Category: basic
- Description: White metric tile — small caps label, large numeral, sub-note, optional coloured 3px top border and info badge
- Extractable props: `label` (string), `value` (string), `sub` (string), `accentColor` (string, default: "#0077C8"), `showInfoIcon` (boolean, default: true), `tooltip` (string)
- Hardcoded: white fill, `#C8DDEF` border, 10px radius, shadow, .7rem label / 2rem value / .74rem sub

### KpiCardDark
- Source: `src/output/theme.py:153-155` (`.card-dark`); call sites `views/market_overview.py:46`, `views/geographic.py:38`, `views/campaign_measurement.py:92`
- Category: basic
- Description: Gradient navy KPI tile used as the first/primary metric in a row
- Extractable props: `label` (string), `value` (string), `sub` (string)
- Hardcoded: `linear-gradient(135deg,#003087,#0077C8)`, white text, `.label-w`/`.big-num-w`/`.sub-w` classes

### KpiCardBlue
- Source: `src/output/theme.py:156-158` (`.card-blue`); call site `views/payer_landscape.py:46`
- Category: basic
- Description: Muted slate-blue gradient variant of the dark KPI tile
- Extractable props: `label` (string), `value` (string), `sub` (string)
- Hardcoded: `linear-gradient(135deg,#1E3A5F,#2D6A9F)`

### SectionHeader
- Source: `src/output/theme.py:160-164` (`.ch` + `.sec-head` + `.sec-sub`); call sites `views/insights.py:107`, `views/market_overview.py:109`, `views/payer_landscape.py:56`
- Category: basic
- Description: Cyan left-rule label block above a chart or table — heading plus one-line explainer, no card box
- Extractable props: `heading` (string), `sub` (string), `showInfoIcon` (boolean, default: true), `tooltip` (string)
- Hardcoded: 3px `#00A9E0` left border, `rgba(0,169,224,.04)` tint, `0 6px 6px 0` radius

### TierPill
- Source: `src/output/theme.py:137-140` (`_tier_pill`) + `:184-210` (`.pill`, `.tier-*`)
- Category: basic
- Description: Rounded status badge — Priority / Emerging / Developing
- Extractable props: `tier` ("Priority" | "Emerging" | "Developing", default: "Developing")
- Hardcoded: the three colour pairs, 20px radius, .72rem/700

### ScoreBar
- Source: `src/output/theme.py:130-134` (`_score_bar`) + `:195-198` (`.sbar-*`)
- Category: basic
- Description: Inline 0–100 progress bar with the numeral right-aligned beside it; used in table cells
- Extractable props: `value` (number, default: 0), `color` (string, default: "#0077C8")
- Hardcoded: 5px track height, `#C8DDEF` track, 3px radius, .79rem numeral

### DimensionBar
- Source: `src/output/theme.py:200-206` (`.dim-*`); call sites `views/seven_dim.py:104`, `views/state_drilldown.py:78`
- Category: basic
- Description: One 7-dimension row — emoji, fixed-width name, coloured fill bar with a black national-average marker, value, and green/red delta
- Extractable props: `dimension` (one of the 7 keys), `value` (number), `benchmark` (number), `showDelta` (boolean, default: true)
- Hardcoded: `DIM_COLORS`/`DIM_ICONS`/`DIM_LABELS` maps, 7px track, 7.5rem name column, delta colours `#16a34a`/`#dc2626`

### DataTable
- Source: `src/output/theme.py:187-193` (`.tbl`); call sites `views/state_drilldown.py:334`, `views/insights.py:298`, `views/investment_planner.py:184`, `views/hcp_targeting.py:99`
- Category: basic
- Description: Ranked county/prescriber table — tinted header row, hairline row borders, hover fill; cells embed ScoreBar and TierPill; usually followed by a CSV download button
- Extractable props: `columns` (string[]), `rowCount` (number, default: 20), `showDownload` (boolean, default: true)
- Hardcoded: `#F0F6FC` header fill, `#C8DDEF` borders, .83rem body / .67rem header type

### InfoBadge (tooltip)
- Source: `src/output/theme.py:97-107` (`_iicon`) + `:239-310` (`.info-tip` and `.tip-r`/`.tip-l`)
- Category: basic
- Description: 15px gradient circle with an italic serif "i"; hover reveals a 240px dark tooltip bubble with caret
- Extractable props: `tip` (string), `placement` ("default" | "tip-r" | "tip-l", default: "default"), `inline` (boolean, default: false)
- Hardcoded: 15px size, gradient, bubble width/colour/shadow, .18s fade

### EntityCard
- Source: call site `views/insights.py:124-141` (composed from `.card`)
- Description: Ranked county card — rank eyebrow, county name, state, tier pill + score /100, estimated pool, recommended program; coloured left border by program
- Category: basic
- Extractable props: `rank` (number), `title` (string), `subtitle` (string), `tier` (string), `score` (number), `accentColor` (string)
- Hardcoded: 215px min-height, eyebrow letter-spacing .04em, "/100" suffix

### EmptyState
- Source: call sites `views/hcp_targeting.py:23-26`, `views/campaign_measurement.py:60-62`
- Category: basic
- Description: Centred card explaining why a view has nothing to show and what to run
- Extractable props: `icon` (string), `heading` (string), `body` (string)
- Hardcoded: `.card` with 2rem padding, centre alignment, `.sec-head` heading

## Not extractable
Charts are Plotly figures, not markup — their shared styling lives in
`_stplot()` (`theme.py:110-127`), which is the thing to keep consistent, not a
component. Streamlit natives (`st.radio`, `st.expander`, `st.tabs`,
`st.selectbox`, `st.slider`, `st.download_button`) are restyled by CSS selectors
only and can't be extracted as markup.
