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

Without the app, the manager would repeatedly join dates to parks, compare month-and-weekday records, locate the parks of must-do attractions, and check current queues separately. A fixed report cannot answer a different group's dates, access, and priorities without being rebuilt. The app does not claim a specific number of hours saved or dollars earned.

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
| `data/ride_stats.csv` | 2,022 | Uses 83 active, all-time `ride_avg_wait` rows to link attractions to parks and rank preparation priorities. The minutes are source summaries, not future predictions. |
| `data/ll_classification.csv` | 51 | Snapshot labels for Magic Kingdom only: 18 `multi_pass`, 2 `single_pass`, 14 `none`, and 17 `exclude`. Of the 83 active ride rows, 40 match a label; the other 43 are deliberately shown as “Verify access.” |

Other Kaggle companion tables were inspected but are not shipped to the app:

- `park_stats.csv` repeats calendar aggregations already reproducible from `calendar_enriched.csv`.
- `coverage_by_year.csv` is a diagnostic summary reproduced in EDA.
- `chained_index.csv` and `ll_split_index.csv` are intermediate/model summaries, not visitor inputs or direct action measures.

This follows the assignment's “small and decision-focused” requirement: maximize useful evidence, not file count.

### Public live source

The header calls the free [Queue-Times API](https://queue-times.com/en-US/pages/api) for the four Orlando park IDs. The provider states that queue data update every five minutes. The app retrieves parks concurrently, caches for 300 seconds, displays the source timestamp when available, includes the required **Powered by Queue-Times.com** link, and falls back to historical planning if the network is unavailable.

Live data answer “what is happening now?” They are never blended into a precise forecast for the selected future dates.

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

The trip-brief preview and decision-review screen keep exactly three top metrics in the same definitions, so the decision signal is visible immediately and stays consistent during review:

1. **Historical trip-pressure** — mean of the selected visits' comparable-date median indices, in `× park-year mean`.
2. **Higher-pressure visits** — count of visits whose comparable-date median is at least `1.10`.
3. **Must-do coverage** — selected must-do attractions retained by the proposed parks.

`1.10` is a transparent review threshold, not a causal or statistically validated cutoff. It triggers human review; it never declares that a route must change. When a user-edited route is more than 3% above the system draft, the app calls out the difference while preserving the visitor's right to prefer it.

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

The desktop experience is a **guided decision dashboard**, not a long analytical report. Step 1 contains only the inputs that can change the recommendation; Step 2 is the main dashboard surface with three KPIs, one supporting chart, and route-level evidence; Steps 3–4 turn the reviewed decision into a visitor handoff and a saved confirmation. The extra stages do not add unrelated analytics. The page fills the available width and uses one browser-level vertical scroll when browser zoom or viewport height makes the content taller than the screen, so content is not clipped inside a locked viewport.

The product uses a four-step guided flow:

1. **🎠 Trip brief** — visitor facts and preferences on the left; an immediate system route and the three decision KPIs appear on the right.
2. **🎢 Route review** — three KPIs, one explanatory chart, route rationale, and an optional override.
3. **🗺️ Travel plan** — a polished brief with park-days, attraction priorities, backups, hotel/access checks, and explicit uncertainty.
4. **🎆 Saved** — shows the recorded-plan confirmation immediately while a quick, one-time balloon celebration crosses the screen; slower ambient park symbols remain, with options to return to page 1 or review the saved plan.

The sequence answers the manager's questions in order: “What does this group need?”, “What route does the evidence support?”, “What should I hand to the visitor?”, and “Was the plan recorded?” On narrow screens the same content stacks and scrolls for accessibility. Park labels use a consistent non-logo icon system: 🏰 Magic Kingdom, 🌐 Epcot, 🎬 Hollywood Studios, and 🌳 Animal Kingdom.

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
- **Proposed production historical refresh:** nightly after verified operational data become available.
- **Live operational signal:** source and app cache use a five-minute cadence.
- **Human review:** itinerary product manager reviews every Monday for upcoming groups; park-day live conditions are checked again before operational changes.
- **Action trigger:** manually review a route when a visit is at or above `1.10`, must-do coverage is incomplete, or a user override is more than 3% above the system draft.
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
- Route review: [The colourful parade at Walt Disney World Resort](https://commons.wikimedia.org/wiki/File:The_colourful_parade_at_Walt_Disney_World_Resort_in_Orlando,_Florida_with_Snow_White_%26_the_Seven_Dwarfs_(15631604701).jpg), traveljunction, [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/).
- Travel plan: [Tree of Life, Disney's Animal Kingdom](https://commons.wikimedia.org/wiki/File:Tree_of_Life,_Disney%27s_Animal_Kingdom.jpg), Jedi94, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
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
- [x] Units, sample limitations, update cadence, and action rules documented
- [x] One dependency system: `pyproject.toml` + `uv.lock`
- [x] Public Streamlit URL added after deployment
