# QueueSense — Walt Disney World Orlando Trip Studio

QueueSense is a historical-data planning prototype for a Disney travel company's **itinerary product manager**. Visitors provide trip preferences; the system proposes a route; the manager reviews or adjusts it; and the approved itinerary is delivered on the Travel plan page. Hotel and early-entry information affects only the final operational guidance. It does not change the historical pressure score or route recommendation.

> If the itinerary product manager sees a planned park visit with a historical pressure index at or above 1.10×, they will review the park assignment and either adjust the route or prepare a lower-pressure backup, while preserving the group's constraints.

Historical pressure is planning evidence, not actual waiting minutes or a prediction of future queues.

## Step 1 — Dataset and Decision-Maker

### Kaggle historical dataset

- **Dataset:** [Walt Disney World Wait Times and Crowd Calendar](https://www.kaggle.com/datasets/chadwambles/walt-disney-world-wait-times)
- **Uploader:** Chad Wambles
- **Place:** Walt Disney World Resort area, Orlando, Florida, United States
- **License shown on Kaggle:** CC BY 4.0
- **Period:** January 1, 2015 through September 30, 2026
- **Main file:** [`data/calendar_enriched.csv`](data/calendar_enriched.csv), about 1.2 MB
- **Shape:** 16,682 rows × 17 columns
- **Row definition:** one park × calendar date
- **Parks:** Magic Kingdom, Epcot, Hollywood Studios, and Animal Kingdom
- **Data character:** compiled historical/observational data, not synthetic data

Approximate sizes use rounded decimal MB/KB so line-ending conversions do not make the documentation stale. The Kaggle description attributes the compiled snapshot to scraped Queue-Times historical statistics and calendar pages. It is not presented here as an official Disney release or as TouringPlans data, and QueueSense has not independently reproduced the uploader's full collection and transformation process.

`crowd_rel_to_year` is a processed park-day crowd index relative to that park's mean in the corresponding source year. `1.00` means that park-year mean; it is not attendance or an attraction's posted or actual wait. The source label `ride_avg_wait` is described only as a **source average**, never as a future prediction. `operating_minutes` is incomplete and is not used by the route recommendation.

### Primary decision-maker and business context

The single primary user is the **itinerary product manager**. Every Monday, the manager prepares future group itineraries, reviews the proposed park assignment, checks the historical pressure and must-do park coverage, and decides whether to approve the route, adjust it, or prepare a backup. Visitors supply dates and preferences; they are not the dashboard's primary decision-maker.

### Companion data

| File | Rows | Approximate size | App use |
|---|---:|---:|---|
| [`data/ride_stats.csv`](data/ride_stats.csv) | 2,022 | 151 KB | Uses 83 active, all-time `ride_avg_wait` rows to associate attractions with parks and rank preparation priorities. |
| [`data/ll_classification.csv`](data/ll_classification.csv) | 51 | 2.7 KB | Magic Kingdom snapshot labels: 18 `multi_pass`, 2 `single_pass`, 14 `none`, and 17 `exclude`. Forty of the 83 active ride rows match; the other 43 display “Verify access.” |

Other Kaggle companion tables were inspected but are not shipped: `park_stats.csv` repeats calendar aggregations; `coverage_by_year.csv` is reproduced in EDA; and `chained_index.csv` and `ll_split_index.csv` are intermediate summaries rather than direct decision inputs.

### Public live source

The header calls the free [Queue-Times API](https://queue-times.com/en-US/pages/api) for the four Orlando park IDs. A request occurs only when Streamlit executes after an interaction or page reload, and each result is cached for 300 seconds. An idle page does **not** refresh itself every five minutes.

The header shows the source date and time in Eastern Time, returned park coverage, and the denominator used for the open-attraction median. A timestamp more than 15 minutes old is marked stale; fewer than four responding parks is marked partial; and total API failure leaves historical planning available. Missing wait values remain missing, valid zero values remain zero, and a response with no open attractions is not presented as a normal `0 min` median. Live status is kept separate from future historical planning.

## Step 2 — Why a Dashboard

### 1. Who uses it, and how often?

The itinerary product manager uses QueueSense during the weekly Monday review of future group itineraries. Live conditions may be checked again before an operational change, but the dashboard is not intended for continuous monitoring.

### 2. What decision does it support?

It supports one recurring decision: which accepted parks should be assigned to the group's dates, in what order, and whether any historically higher-pressure visit needs an adjustment or backup while preserving ticket and must-do constraints.

### 3. What happens without it, and what does that cost?

Without the dashboard, the manager must manually match dates to parks, find the parks associated with selected must-dos, compare several route options, and check constraints in separate places. This creates repeated work and increases the risk of missing a constraint or comparing alternatives with inconsistent definitions. QueueSense does not claim a specific number of hours saved or a financial return.

### 4. Why a dashboard rather than an email, report, or alert?

An email or fixed report cannot conveniently recalculate a new combination of dates, trip length, accepted parks, ticket access, pace, and must-dos. The interactive dashboard supports like-for-like route comparison and optional manager adjustment. Alerts and official notifications are better for sudden closures, severe weather, major ride downtime, or rule changes; they complement rather than replace routine route comparison.

## Step 3 — Metrics, Charts, Filters, and Layout

### EDA findings

The executable analysis is in [`notebooks/eda.ipynb`](notebooks/eda.ipynb). It checks shape, types, missingness, duplicates, date coverage, park balance, distributions, weekday differences, comparison-cell sizes, attraction coverage, and pass-label coverage.

- No duplicate `park_name × date` rows were found.
- `operating_minutes` is the only column with missing values: 630 rows. It is excluded from recommendations.
- Park coverage is balanced: Magic Kingdom 4,173 rows, Animal Kingdom 4,173, Hollywood Studios 4,169, and Epcot 4,167.
- The full range contains 118–124 missing calendar dates per park, largely around disrupted operations. Dates are not imputed.
- 2020–2021 are excluded from the reference because of operating disruption. Partial 2026 is excluded because it is unfinished.
- The fixed reference contains 13,142 park-days from 2015–2019 and 2022–2025; the raw CSV remains unchanged.
- Reference `crowd_rel_to_year` has median 1.02, interquartile range 0.642–1.331, and range 0.000–3.148.
- Park × calendar month × weekday produces 336 comparison cells with 36–41 observations each.
- The active attraction summary covers 83 attractions: 40 Magic Kingdom, 18 Epcot, 15 Hollywood Studios, and 10 Animal Kingdom.
- Pass labels cover only the 40 active Magic Kingdom matches; labels are not inferred for the other 43 attractions.

### Three headline KPIs

The Trip brief, Route review, and Travel plan use the same definitions.

| KPI | Definition and limitation | Decision use |
|---|---|---|
| **Historical trip pressure** | Mean of selected visits' comparable-date median indices, expressed as `× park-year mean`. `1.00×` is each park's corresponding-year mean. It does not compare actual wait minutes across parks, and an index decrease is not the same percentage of queue-time savings. | Compare alternative routes that satisfy the group's constraints. |
| **Higher-pressure visits** | Count of planned visits whose comparable-date median is at least `1.10×`. The threshold is a transparent human-review rule, not a validated prediction boundary. | Locate the visits that need focused manager review. |
| **Must-dos in scheduled parks** | Count of selected must-do attractions whose associated park appears anywhere in the route. This park-presence check does not guarantee completion or validate queues, transport, operating hours, or closures. With no must-dos, the app shows an explicit empty state. | Check whether the route omitted a park required by a selected must-do. |

### Supporting chart

The core dashboard uses one chart: historical pressure for each selected park-day, with reference lines at `1.00×` and the `1.10×` manager-review threshold. It supports the KPIs by showing where pressure occurs without adding unrelated charts.

### Filters and inputs

Primary inputs are first Disney date, number of Disney days, accepted parks, ticket access, trip rhythm, and must-do attractions. Hotel and early-entry details are secondary options because they affect only final operational guidance, not the historical pressure score or route recommendation.

`Relaxed`, `Balanced`, and `Highlights` limit only additional recommendations. Every selected must-do belonging to a scheduled park remains in the visitor list. Must-dos, extra recommendations, and flexible backups are deduplicated, including repeated parks.

### Recommendation method

For each candidate visit, QueueSense uses the median historical index for the same park, calendar month, and weekday. The search uses only accepted parks, requires parks implied by must-dos, respects One Park Per Day or Park Hopper access, prevents duplicate parks on the same hopper day, minimizes total and then peak historical pressure, and preserves variety where trip length permits. A manager may override the proposal.

### Evidence omitted and misleading-data controls

- No visitor counts or attendance claims: no reliable attendance field exists.
- No precise future waits or hour-by-hour schedule: the data do not support that precision.
- No walking-time optimizer: no reliable walking network is provided.
- No weather or event causality: future conditions and event labels are unavailable.
- No raw-data table or extra decorative charts: they do not change the route decision.
- Unmatched pass labels display “Verify access” rather than guessed classifications.
- Attraction minutes are labeled `source avg`; historical indices are not presented as predicted minutes.
- Empty park selections, infeasible must-do combinations, duplicate hopper parks, missing files, and API failures have explicit states.
- The final plan tells the user to recheck official hours, closures, ticket rules, and access.

### Page order and information hierarchy

The four-page workflow is:

1. **Trip brief:** input the group's dates, access, pace, accepted parks, and must-dos.
2. **Route review:** the itinerary product manager reviews and optionally adjusts the system proposal.
3. **Travel plan:** deliver the approved visitor itinerary.
4. **Saved:** confirm the itinerary only in the current browser session, not an account or database.

Within Route review, the three headline KPIs appear first, followed by the baseline/live-data explanation and the optional-adjustment toggle. If the toggle is enabled, the manual park selectors appear there. The threshold status, historical pressure chart, route rationale, manager action, and navigation then complete the review. The visual hierarchy remains summary, evidence, and action without adding another chart.

Before coding, I sketched the dashboard layout on paper, placing the headline KPIs at the top, the supporting pressure chart and route rationale in the middle, and action guidance and optional details below. The sketch helped determine the information hierarchy before implementation.

On narrow screens, content stacks and uses normal browser scrolling. Park labels use consistent non-logo icons: 🏰 Magic Kingdom, 🌐 Epcot, 🎬 Hollywood Studios, and 🌳 Animal Kingdom.

### Reproducible decision case

- **Input:** November 2, 2026 start; four Disney days; all four parks accepted; One Park Per Day; `Relaxed`; five Magic Kingdom must-dos—Seven Dwarfs Mine Train, TRON Lightcycle / Run, Peter Pan's Flight, Jungle Cruise, and Space Mountain.
- **System result:** Day 1 Hollywood Studios `1.2450×`, Day 2 Animal Kingdom `0.9090×`, Day 3 Epcot `0.6745×`, and Day 4 Magic Kingdom `0.7040×`; route mean `0.8831×` (displayed `0.88×`), one of four visits at or above `1.10×`, and `5 / 5` must-dos in scheduled parks.
- **Adjustment reviewed:** replacing Day 2 Animal Kingdom with Magic Kingdom produces `0.8365×` (displayed `0.84×`), keeps one flagged visit and `5 / 5` park-level coverage, but reduces variety from four unique parks to three.
- **Manager action:** retain the system route unless the group explicitly prefers a second Magic Kingdom day; review the flagged Hollywood Studios visit, confirm current hours and closures, and prepare a lower-pressure backup. The Magic Kingdom card still lists all five must-dos plus two pace-limited extras.

These values are historical comparison outputs, not promised queue-time savings or completion rates.

## Step 4 — Refresh Frequency and Action Rules

| Element | Current classroom app | Proposed production design |
|---|---|---|
| Historical data | Frozen committed Kaggle CSVs | Nightly batch collection after operational data are verified; not currently implemented |
| Historical baseline | Fixed 2015–2019 and 2022–2025 reference years | New arrivals would not enter the baseline automatically; changes require validation and a reviewed release |
| Live API | Requested on interaction or reload and cached for five minutes; no idle-page auto-refresh | Same operational separation from historical planning |
| Human review | Manager reviews upcoming groups each Monday | Continue the Monday review cadence |
| Automated alerts/trends | Not implemented | Possible operational layer, separate from the planning dashboard |

Nightly verified collection is sufficient for the proposed production workflow because the manager reviews future group itineraries each Monday. For advance planning, continuous real-time refresh would not change most route decisions. Same-day closures or severe operating abnormalities are better handled through an alert or official notification.

### Action rules

The manager reviews or prepares a backup when:

- a planned visit reaches the `1.10×` historical-pressure review line;
- not every selected must-do has its associated park scheduled; or
- a manual route is more than 3% above the system draft.

The app also reports partial, stale, unavailable, or no-open-attraction live states, but live status does not overwrite the historical recommendation.

### Continuous tracking design

In a production workflow, each weekly review would record the share of future planned visits above the `1.10×` review line and identify the specific visits that meet it. The manager would use that record to decide whether to adjust the route or prepare a backup. Cross-week trend storage, automated alerts, automated nightly collection, and a rolling historical baseline are **design proposals only** and are not implemented in the current classroom app.

Stale planning data could cause the manager to rely on outdated patterns, repeat manual verification, or create a mismatch between the itinerary and current operating reality. No unsupported financial or time-loss estimate is claimed.

## Step 5 — Build, Deployment, and Submission

### Project structure

```text
disney-itinerary-dashboard/
├── .streamlit/
│   └── config.toml
├── app.py
├── dashboard.py
├── data/
│   ├── calendar_enriched.csv
│   ├── ride_stats.csv
│   └── ll_classification.csv
├── notebooks/
│   └── eda.ipynb
├── tests/
│   └── test_dashboard_logic.py
├── static/
│   └── backgrounds/
│       ├── trip-brief.jpg
│       ├── route-review.jpg
│       ├── travel-plan.jpg
│       └── saved.jpg
├── .python-version
├── pyproject.toml
├── uv.lock
└── README.md
```

The virtual environment, downloaded ZIP, unused raw companion files, caches, and credentials are excluded from Git.

### Run locally

```powershell
git clone https://github.com/SelinaHe913/disney-itinerary-dashboard.git
cd disney-itinerary-dashboard
uv sync
uv run streamlit run app.py
```

QueueSense is the default team name. An optional runtime override is available:

```powershell
$env:TEAM_NAME = "Your Team Name"
uv run streamlit run app.py
```

Python 3.14 has been manually confirmed for the course environment; this README revision does not rebuild or change the deployment.

### Execute the EDA notebook

```powershell
uv run python -m ipykernel install --prefix .venv --name queuesense --display-name "QueueSense (Python 3.14)"
$env:JUPYTER_PATH = (Resolve-Path ".venv\share\jupyter").Path
uv run jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=queuesense notebooks/eda.ipynb
```

In VS Code, select `.venv\Scripts\python.exe` as the notebook kernel and choose **Run All**.

### Existing deployment and submission links

The existing Streamlit Community Cloud app uses branch `main` and entry point `app.py`.

1. **Public GitHub repository:** [SelinaHe913/disney-itinerary-dashboard](https://github.com/SelinaHe913/disney-itinerary-dashboard)
2. **Public Streamlit app:** [queuesense-disney-itinerary.streamlit.app](https://queuesense-disney-itinerary.streamlit.app/)

## Visual credit

The app serves optimized 2560 × 1440 local copies of Creative Commons photographs from `static/backgrounds/`:

- Trip brief: [Magic Kingdom — Cinderella Castle panorama](https://commons.wikimedia.org/wiki/File:Magic_Kingdom_-_Cinderella_Castle_panorama_-_by_mrkathika.jpg), Michael Gray, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/).
- Route review: [Tree of Life, Disney's Animal Kingdom](https://commons.wikimedia.org/wiki/File:Tree_of_Life,_Disney%27s_Animal_Kingdom.jpg), Jedi94, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- Travel plan: [The colourful parade at Walt Disney World Resort](https://commons.wikimedia.org/wiki/File:The_colourful_parade_at_Walt_Disney_World_Resort_in_Orlando,_Florida_with_Snow_White_%26_the_Seven_Dwarfs_(15631604701).jpg), traveljunction, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/).
- Saved: [Cinderella's Castle at Night](https://commons.wikimedia.org/wiki/File:Cinderella%27s_Castle_at_Night.jpg), Dancorona21, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The photographs remain visible beneath legibility overlays and use `background-size: cover`. No official logo or character artwork is redistributed.

## Reproducibility checklist

- [x] Dataset name, link, source, period, approximate size, shape, row definition, and observational character documented
- [x] One primary decision-maker, weekly use, supported decision, manual-work risk, and dashboard rationale stated
- [x] EDA findings, KPI definitions and uses, one supporting chart, filters, omissions, risks, layout, and reproducible case documented
- [x] Frozen data, fixed baseline, live-cache behavior, proposed nightly collection, Monday review, action rules, and tracking proposal separated
- [x] Must-do coverage described as park presence rather than guaranteed completion
- [x] Hotel and early-entry inputs described as final-guidance inputs only
- [x] Empty, infeasible, duplicate-hopper, missing-file, and API-error states documented
- [x] Project structure, local run, EDA execution, deployment, and the two public submission links included
- [x] Image sources and licenses retained
