# QueueSense — Walt Disney World Orlando Trip Studio

- **Team:** QueueSense (change with the `TEAM_NAME` environment variable)
- **Public repository:** [SelinaHe913/disney-itinerary-dashboard](https://github.com/SelinaHe913/disney-itinerary-dashboard)
- **Streamlit app:** [queuesense-disney-itinerary.streamlit.app](https://queuesense-disney-itinerary.streamlit.app/)

## Executive Summary

QueueSense is a historical-data planning prototype for a Disney travel company's **itinerary product manager**. On Monday, the manager enters an upcoming group's dates, trip length, ticket access, hotel type, pace, and must-do attractions. The app proposes the park assignment, explains the historical pressure behind it, and produces a visitor-ready brief. The visitor supplies preferences; the system does not make them choose every park-day first.

> If the itinerary manager sees that a park has consistently longer waits than comparable days, they will review which park to recommend and how to arrange the guided itinerary for upcoming groups.

Historical fit is planning evidence, not a precise prediction of a future day's queues. Weather, temporary events, closures, operating hours, reservations, and future rule changes are not available in the frozen Kaggle snapshot.

## Step 1 — Define the decision and verify the sources

### Decision, user, and recurring need

The single decision-maker is the itinerary product manager. Every Monday, they review upcoming groups and may change the recommended park mix, order of park-days, or which high-burden attractions require advance preparation. On a park day, the live header is a separate operational check.

Without the app, the manager would repeatedly join dates to parks, compare month-and-weekday records, locate the parks of must-do attractions, and check current queues separately. A fixed report cannot answer a different team's dates, trip length, accepted parks, ticket access, pace, and must-do mix without being rebuilt; the interactive controls recalculate the proposal and review signals for each group. Emergencies such as a sudden closure, severe weather, major ride downtime, or a ticket-rule change are better handled by an operational alert or official notification than by expecting a planning dashboard to be watched continuously. The app does not claim a specific number of hours saved or dollars earned.

### Kaggle historical snapshot

- **Dataset:** [Walt Disney World Wait Times and Crowd Calendar](https://www.kaggle.com/datasets/chadwambles/walt-disney-world-wait-times)
- **Uploader:** Chad Wambles
- **Place:** Walt Disney World Resort area, Orlando, Florida, United States
- **License shown on Kaggle:** CC BY 4.0
- **Main file:** `data/calendar_enriched.csv`, 1,223,707 bytes (about 1.17 MiB)
- **Coverage:** January 1, 2015 through September 30, 2026
- **Shape:** 16,682 rows × 17 columns
- **Unit of observation:** one park × calendar date
- **Parks:** Magic Kingdom, Epcot, Hollywood Studios, and Animal Kingdom
- **Data character:** the uploader presents these as compiled historical/observational statistics, not synthetic data; QueueSense has not independently verified the full scrape lineage or every transformation

The Kaggle description attributes the compiled snapshot to scraped Queue-Times historical statistics and calendar pages. It is **not presented here as an official Disney release or as TouringPlans data**. The repository does not independently reproduce the uploader's scraping or every transformation. Where the source definition is incomplete, this README states the limitation instead of guessing.

`crowd_rel_to_year` is a processed park-day crowd index relative to that park-year's mean. It is not turnstile attendance and it is not an attraction's posted or actual wait. `1.00` means the source park-year mean. The source label `ride_avg_wait` does not establish whether its underlying observations were posted waits, actual waits, or another processed series, so the app calls it only a **source average** and never a future prediction. `operating_minutes` is contextual and missing for some dates; it is not used by the optimizer.

Two compact companion files add only decision-useful attraction context:

| File | Source rows | App use |
|---|---:|---|
| `data/ride_stats.csv` | 2,022 | 151,458 bytes. Uses 83 active, all-time `ride_avg_wait` rows to link attractions to parks and rank preparation priorities. The minutes are source summaries, not future predictions. |
| `data/ll_classification.csv` | 51 | 2,672 bytes. Snapshot labels for Magic Kingdom only: 18 `multi_pass`, 2 `single_pass`, 14 `none`, and 17 `exclude`. Of the 83 active ride rows, 40 match a label; the other 43 are deliberately shown as “Verify access.” |

Other Kaggle companion tables were inspected but are not shipped to the app:

- `park_stats.csv` repeats calendar aggregations already reproducible from `calendar_enriched.csv`.
- `coverage_by_year.csv` is a diagnostic summary reproduced in EDA.
- `chained_index.csv` and `ll_split_index.csv` are intermediate/model summaries, not visitor inputs or direct action measures.

This follows the assignment's “small and decision-focused” requirement: maximize useful evidence, not file count.

### Public live source

The header calls the free [Queue-Times API](https://queue-times.com/en-US/pages/api) for the four Orlando park IDs. The provider states that queue data update every five minutes. QueueSense requests the API only when Streamlit executes after an interaction or page reload, and caches each result for 300 seconds; an idle page does **not** refresh itself every five minutes. The header displays the source date and time in Eastern Time, the number of returned parks, and the denominator used for the open-attraction median. A snapshot older than 15 minutes—three stated source-update intervals—is marked stale. Partial park responses are marked partial, and a total failure leaves historical planning available.

Missing wait values remain missing; a real reported zero is retained. If the returned scope contains no open attractions, the interface says so instead of showing a normal-looking `0 min` median. Live data answer “what is happening now?” They are never blended into a precise forecast for the selected future dates.


## Step 2 — EDA and defensible measures

The executable analysis is in [`notebooks/eda.ipynb`](notebooks/eda.ipynb). It uses Pandas and Matplotlib to inspect shape, dtypes, missingness, duplicates, date coverage, park balance, distributions, weekday differences, comparable-cell sample sizes, attraction coverage, and pass-label coverage.

### Verified findings

- No duplicate `park_name × date` rows were found.
- `operating_minutes` is the only column with missing values: 630 rows. It is excluded from recommendations.
- Park coverage is balanced: Magic Kingdom 4,173 rows, Animal Kingdom 4,173, Hollywood Studios 4,169, and Epcot 4,167.
- The full range contains 118–124 missing calendar dates per park, largely reflecting disrupted operating periods. In the included full-year baseline, only one date is absent for three parks and three dates are absent for Epcot. No dates are imputed; comparison cells use the available rows.
- 2020–2021 are excluded because the operating disruption is not a useful normal-planning baseline. Partial 2026 is also excluded so an unfinished year cannot distort comparison.
- The final reference contains 13,142 park-days from 2015–2019 and 2022–2025. The raw CSV remains unchanged for audit.
- In that reference, `crowd_rel_to_year` has median 1.02, interquartile range 0.642–1.331, and range 0.000–3.148.
- Same park × calendar month × weekday creates 336 comparison cells with 36–41 observations each. This supports a median and middle-50% interval without imputation.
- The active attraction summary covers 83 attractions: 40 Magic Kingdom, 18 Epcot, 15 Hollywood Studios, and 10 Animal Kingdom.
- Pass classification is not park-wide: it covers only the 40 active Magic Kingdom matches. The interface never infers a label for the remaining 43 attractions.

### Comparison and route method

For each candidate park-day, QueueSense selects historical rows for the same **park, calendar month, and weekday** and calculates the median `crowd_rel_to_year`. The route search:

1. creates one park slot per trip day;
2. adds a second slot only when Park Hopper is selected and must-do park coverage requires it;
3. limits candidates to parks the group accepts;
4. requires every park implied by a must-do attraction;
5. avoids assigning the same park twice on one hopper day;
6. minimizes the sum of comparable-date medians and then the highest single visit;
7. preserves variety up to the number of available trip days.

For a four-day trip with all parks accepted, the first proposal therefore covers all four parks automatically. A user may override the proposal, but is not forced to construct it.

### Final KPIs and threshold

The trip-brief preview, manager review, and travel-plan delivery use the same three metric definitions, so the decision signal stays consistent across the workflow:

1. **Historical trip pressure** — mean of the selected visits' comparable-date median indices, in `× park-year mean`. `1.00×` is the corresponding park's mean within each source year. Because every park is normalized to itself, indices do not compare actual waiting minutes between parks. A route-index decrease is not the same percentage reduction in queue time.
2. **Higher-pressure visits** — count of visits whose comparable-date median is at least `1.10×`. The threshold is a transparent human-review rule, not a validated prediction boundary.
3. **Must-dos in scheduled parks** — count of selected must-do attractions whose associated park appears anywhere in the route. This is deliberately a **park-presence check**: it does not promise that the visitor can complete an attraction and does not validate queues, travel time, operating hours, or closures. With no selection, the dashboard shows an explicit empty state.

The visitor-ready list always includes every selected must-do belonging to a scheduled park. `Relaxed`, `Balanced`, and `Highlights` control only the number of **additional** recommendations; they never truncate must-dos. Must-dos, extra recommendations, and the flexible backup are deduplicated, including when a park occurs more than once. When a user-edited route is more than 3% above the system draft, the app calls out the difference while preserving the visitor's right to prefer it.

### Evidence retained and omitted

The app retains one chart: the selected route's historical pressure by park-day with lines at 1.00 and 1.10. The final cards then connect each park to must-do attractions, historically higher-wait preparation priorities, the available snapshot pass label, and a lower-burden backup.

Deliberately omitted:

- **Visitor counts or “attendance”:** no reliable attendance field exists.
- **Exact future wait minutes or hour-by-hour order:** the files do not support that precision.
- **A map or walking-time optimizer:** no reliable walking network or geocoded attraction path is provided.
- **Weather/event causality:** future weather, closures, and temporary events are unavailable.
- **A raw-data table and extra decorative charts:** neither changes the manager's route decision.
- **Unmatched pass assumptions:** labels missing outside Magic Kingdom are shown as “Verify access,” never filled in from memory.

## Step 3 — Guided one-panel product design

The desktop experience is a **guided decision dashboard**, not a long analytical report. Step 1 keeps dates, days, accepted parks, ticket access, pace, and must-dos in the primary form. Hotel and early-entry details sit in a secondary disclosure because they affect only the final operational checklist, not the historical score or route recommendation. Step 2 is the manager's core dashboard: three KPIs, one supporting chart on an opaque plotting surface, the route rationale, and the recommended action. Step 3 is the decision-approved visitor handoff rather than a second analysis page. Step 4 confirms session-only storage. The page fills the available width and uses one browser-level vertical scroll when browser zoom or viewport height makes the content taller than the screen, so content is not clipped inside a locked viewport.

The product uses a four-step guided flow:

1. **🎠 Trip brief** — visitor facts and preferences on the left; an immediate system route and the three decision KPIs appear on the right.
2. **🎢 Route review** — the manager's core review-and-adjust dashboard with three KPIs, one explanatory chart, route rationale, a specific action, and an optional override.
3. **🗺️ Travel plan** — the approved decision delivered as a polished visitor brief with park-days, every in-scope must-do, pace-limited extras, unique backups, hotel/access checks, and explicit uncertainty.
4. **🎆 Saved** — confirms that the plan exists only in the current browser session, not an account or database, while a quick, one-time balloon celebration crosses the screen; options return to page 1 or reopen the plan.

The sequence answers the manager's questions in order: “What does this group need?”, “What route does the evidence support?”, “What should I hand to the visitor?”, and “Was the plan recorded?” On narrow screens the same content stacks and scrolls for accessibility. Park labels use a consistent non-logo icon system: 🏰 Magic Kingdom, 🌐 Epcot, 🎬 Hollywood Studios, and 🌳 Animal Kingdom.

### Reproducible decision case

This case was calculated against the committed CSVs and current route code (and can be rerun with the automated tests plus the app):

- **Input:** November 2, 2026 start; four Disney days; all four parks accepted; One Park Per Day; `Relaxed`; five Magic Kingdom must-dos—Seven Dwarfs Mine Train, TRON Lightcycle / Run, Peter Pan's Flight, Jungle Cruise, and Space Mountain.
- **System result:** Day 1 Hollywood Studios `1.2450×`, Day 2 Animal Kingdom `0.9090×`, Day 3 Epcot `0.6745×`, and Day 4 Magic Kingdom `0.7040×`; route mean `0.8831×` (displayed `0.88×`), one of four visits at or above `1.10×`, and `5 / 5` must-dos in scheduled parks.
- **Adjustment reviewed:** replacing Day 2 Animal Kingdom with Magic Kingdom lowers the displayed route mean to `0.84×` (`0.8365×` before rounding) while keeping one flagged visit and `5 / 5` park-level must-do coverage, but reduces the route from four unique parks to three.
- **Manager action:** reject that adjustment unless the group explicitly values a second Magic Kingdom day more than four-park variety; retain the system draft, review the flagged Hollywood Studios day, confirm current hours and closures, and prepare a lower-burden backup. On the Magic Kingdom card, Relaxed still lists all five must-dos, then two extra recommendations; none is displaced by the pace setting.

These numbers are historical comparison outputs, not promised wait-time savings or completion rates.

### Misleading-data controls

- COVID-disrupted years and partial 2026 are excluded from the reference, not deleted from the raw file.
- The app says “historical index,” never attendance or predicted minutes.
- Attraction minutes are labeled `source avg`.
- Pass classes are explicitly called snapshot labels and unmatched rows say “Verify access.”
- Special events, closures, and operating-hour differences can still affect comparisons because reliable event labels are unavailable. The dashboard therefore uses comparable-date medians and presents the result as a review signal, not a causal claim.
- Hotel and early-entry inputs alter the final operational checklist, but not the historical route score. The source has no reliable hotel-transfer times, future day-specific early-entry eligibility, or current entitlement rules, so the app does not invent them.
- Empty park selections, insufficient park slots, duplicate hopper assignments, missing files, and API failure have clear states.
- The final brief requires rechecking official hours, closures, ticket rules, and access before acting.

## Step 4 — Refresh, use, and deploy

### Cadence and action rule

- **Classroom historical data:** frozen Kaggle CSV; no automatic refresh.
- **Proposed production data collection:** nightly after verified operational data become available; this collection schedule is not implemented by the classroom app.
- **Historical recommendation baseline:** fixed to 2015–2019 and 2022–2025 in code. Nightly arrivals would not enter this reference automatically; changing the reference years requires explicit validation and a reviewed code/model release.
- **Live operational signal:** fetched only on a Streamlit rerun caused by interaction or reload, then cached for 300 seconds. The source's stated five-minute update frequency is not a browser auto-refresh schedule. A returned timestamp more than 15 minutes old is marked stale, while fewer than four responding parks is marked partial.
- **Human review:** itinerary product manager reviews every Monday for upcoming groups; park-day live conditions are checked again before operational changes.
- **Action trigger:** manually review a route when a visit is at or above `1.10`, fewer selected must-dos have their park scheduled than were selected, or a user override is more than 3% above the system draft.
- **Cost of stale data:** if the planning base is a week out of date, the manager may rely on outdated queue patterns and create a mismatch between itinerary and experience. No unsupported financial loss is claimed.

This remains a historical-data prototype. It cannot provide real-time park control, guarantee a “best day next week,” or predict exact future waits.

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
├── .gitignore
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

Optional team-name override:

```powershell
$env:TEAM_NAME = "Your Team Name"
uv run streamlit run app.py
```

Execute the EDA notebook:

```powershell
uv run python -m ipykernel install --prefix .venv --name queuesense --display-name "QueueSense (Python 3.14)"
$env:JUPYTER_PATH = (Resolve-Path ".venv\share\jupyter").Path
uv run jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.kernel_name=queuesense notebooks/eda.ipynb
```

In VS Code, the equivalent is to select `.venv\Scripts\python.exe` as the notebook kernel and choose **Run All**.

### Streamlit Community Cloud

1. Push this public repository to GitHub.
2. Create a new Streamlit Community Cloud app from `SelinaHe913/disney-itinerary-dashboard`.
3. Select branch `main` and main file `app.py`.
4. In **Advanced settings**, select Python **3.14** as required by the course.
5. The deployed app is available at [queuesense-disney-itinerary.streamlit.app](https://queuesense-disney-itinerary.streamlit.app/); test all four steps and at least one changed preference after each deployment.

Canvas submission should contain exactly two real links: the public GitHub repository URL and the public Streamlit app URL.

### Visual credit

Stage photographs are Creative Commons files from Wikimedia Commons. The app serves optimized 2560 × 1440 local copies from `static/backgrounds/` so each stage loads without waiting for an external image redirect:

- Trip brief: [Magic Kingdom — Cinderella Castle panorama](https://commons.wikimedia.org/wiki/File:Magic_Kingdom_-_Cinderella_Castle_panorama_-_by_mrkathika.jpg), Michael Gray, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/).
- Route review: [Tree of Life, Disney's Animal Kingdom](https://commons.wikimedia.org/wiki/File:Tree_of_Life,_Disney%27s_Animal_Kingdom.jpg), Jedi94, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- Travel plan: [The colourful parade at Walt Disney World Resort](https://commons.wikimedia.org/wiki/File:The_colourful_parade_at_Walt_Disney_World_Resort_in_Orlando,_Florida_with_Snow_White_%26_the_Seven_Dwarfs_(15631604701).jpg), traveljunction, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/).
- Saved celebration: [Cinderella's Castle at Night](https://commons.wikimedia.org/wiki/File:Cinderella%27s_Castle_at_Night.jpg), Dancorona21, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The photographs are pre-cropped for a 16:9 dashboard and still use `background-size: cover` for full-viewport coverage. A lighter purple, rose, and fireworks-gold interface overlay preserves legibility without hiding the photography. Park icons, stars, carousel/fireworks emoji, the full-screen saved-page celebration, and the four photographs provide the themed visual language; no official logo or character artwork is redistributed.

## Reproducibility checklist

- [x] Three real Kaggle CSVs used only where they support a decision
- [x] Historical and live evidence kept conceptually separate
- [x] EDA, app, and README use the same comparable-date definition
- [x] 1–7 day trips, one-park tickets, Park Hopper, must-dos, hotel type, access, and pace supported
- [x] System proposes parks before asking the visitor to edit them
- [x] Responsive four-stage flow with one-page scrolling, licensed stage photography, and park icon labels
- [x] Empty, infeasible, duplicate-hopper, missing-file, and API-error states handled
- [x] Regression tests protect default routing, ticket/day changes, park-level must-do coverage, must-do retention beyond pace limits, deduplication, and live empty/partial states
- [x] Units, sample limitations, update cadence, and action rules documented
- [x] One dependency system: `pyproject.toml` + `uv.lock`
- [x] Public Streamlit URL added after deployment
