# Ride Analyzer: Post-Ride Analysis Tool

## What This Is

A Python tool that pulls my latest ride from Intervals.icu via their API, runs training analysis tuned to where I am in my season, and gives me actionable feedback and workout suggestions. The end goal is to trigger this from my phone via Claude Dispatch after every ride and get results back in a few minutes.

## My Context

- Cyclist training 5-6 rides/week, targeting 10+ hours/week minimum
- Current FTP: ~250W (needs validation, hasn't been tested recently)
- Hardware: Quarq 8964 power meter, HR monitor, Garmin head unit with respiration rate
- Platform: Garmin syncs to Intervals.icu (not via Strava)
- Season goal: peak for cyclocross in September 2026
- Current phase: early base (April 2026)
- Indoor training on Zwift, mix of indoor and outdoor rides

## Season Periodization

The tool should know where I am in my season and adjust its analysis accordingly:

| Phase | Dates | Focus | Key Metrics |
|-------|-------|-------|-------------|
| Base | April - May | Aerobic foundation, volume | EF trend, HR drift at Z2, volume accumulation, resp rate |
| Build 1 | June - early July | Sweet spot, tempo introduction | Threshold power quality, recovery between intervals |
| Build 2 | Mid July - August | Race-specific intensity | Short power (30s-2min), above-threshold repeatability |
| Peak/Race | September | CX race prep, maintain | Power repeatability, recovery between efforts, race readiness |

## Data Sources

### Intervals.icu API

Auth: Basic auth with username `API_KEY` and password = my API key from Intervals.icu settings.

Key endpoints:

```
# List recent activities (summary data)
GET /api/v1/athlete/0/activities?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
Authorization: Basic base64(API_KEY:{api_key})

# Get 1-second streams for an activity (returns CSV)
GET /api/v1/activity/{activity_id}/streams
# Columns: time, watts, cadence, heartrate, distance, altitude,
#           velocity_smooth, temp, torque, left_right_balance, respiration

# Get original Garmin FIT file (has Garmin's FTP, training effect, calories, temp)
GET /api/v1/activity/{activity_id}/file

# Get Intervals.icu FIT file (has Intervals.icu FTP, NP, TSS, IF, laps matching intervals)
GET /api/v1/activity/{activity_id}/fit-file

# Wellness data (weight, resting HR, HRV, sleep, etc.)
GET /api/v1/athlete/0/wellness?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
```

### What the streams CSV contains (verified from real ride data)

1-second resolution with these channels:
- **watts**: power from Quarq
- **heartrate**: HR from chest strap
- **cadence**: from Quarq
- **distance**: cumulative meters
- **altitude**: meters (virtual on Zwift)
- **velocity_smooth**: smoothed speed m/s
- **temp**: temperature celsius
- **torque**: Nm from Quarq
- **left_right_balance**: L/R power balance percentage
- **respiration**: breaths per minute (from Garmin)

### What the Garmin FIT file adds beyond streams

- `threshold_power`: Garmin's FTP estimate (may differ from Intervals.icu)
- `training_stress_score`: Garmin's TSS calculation
- `intensity_factor`: Garmin's IF
- `total_training_effect`: Garmin aerobic training effect (1-5 scale)
- `total_anaerobic_training_effect`: Garmin anaerobic training effect
- `total_calories`: calorie estimate
- `avg_temperature`, `max_temperature`
- Device info, event markers

### What the Intervals.icu FIT file adds

- `threshold_power`: Intervals.icu FTP setting (this is the one to use for zone calculations)
- `normalized_power`: NP for the ride
- `training_stress_score`: TSS based on Intervals.icu FTP
- `intensity_factor`: IF based on Intervals.icu FTP
- Laps that match detected intervals

**Important: Intervals.icu FTP and Garmin FTP can diverge significantly.** My Garmin currently says 209W, Intervals.icu says 265W, actual is probably ~250W. The tool should use a configurable FTP value and flag when either platform's value drifts far from the configured one.

## Architecture

### Phase 1: Core Analysis Library (build this first)

A Python package with clean modules:

```
ride-analyzer/
  config.yaml              # FTP, zones, API key, season phases, athlete preferences
  src/
    intervals_client.py    # Intervals.icu API wrapper
    ride_parser.py         # Parse streams CSV and FIT files into clean dataclasses
    metrics.py             # Compute EF, HR drift, NP, TSS, IF, zone time, etc.
    analysis.py            # Season-aware analysis engine (interprets metrics in context)
    workout_suggest.py     # Suggest next workout based on recent load and season phase
    report.py              # Format analysis output (markdown for now)
  tests/
    test_data/             # Store sample ride data for testing
    test_metrics.py
    test_analysis.py
  cli.py                   # Simple CLI: `python cli.py --latest` or `python cli.py --activity-id i138521071`
```

### Phase 2: Delivery Mechanism (after analysis is solid)

Package as a Cowork skill that can be triggered via Dispatch from my phone. The skill calls the CLI, pipes output through Claude for natural language interpretation and workout suggestion, and returns results to my phone.

## Core Metrics to Compute

### Every Ride

- **Normalized Power (NP)**: 30-second rolling average, then RMS
- **Intensity Factor (IF)**: NP / FTP
- **Training Stress Score (TSS)**: (duration_seconds * NP * IF) / (FTP * 3600) * 100
- **Zone distribution**: time in each zone based on configured FTP
  - Z1: <55% FTP
  - Z2: 55-75% FTP
  - Z3: 75-90% FTP
  - Z4: 90-105% FTP
  - Z5: 105-120% FTP
  - Z6: >120% FTP
- **Average power, HR, cadence, respiration rate**
- **Left/right balance**: flag if consistently >53/47 in either direction
- **Efficiency Factor (EF)**: NP / avg HR (for the full ride and for steady segments)

### Aerobic Fitness Indicators (especially during base)

- **HR drift at matched power**: Find the longest steady-state segment (power CV < 5% over 10+ minutes). Compare avg HR in first half vs second half. Drift > 5% suggests aerobic ceiling being approached.
- **EF over 10-minute windows**: The power/HR trend across the ride. Stable or improving = good aerobic fitness. Declining = fatigue or overcooking intensity.
- **Respiration rate trend**: Rising resp rate at constant power = aerobic drift signal. Track this across rides over weeks.
- **Cardiac decoupling**: Ratio of EF in second half to first half of steady-state work. < 5% decoupling = well-developed aerobic base at that intensity.

### Load Tracking (requires pulling multiple rides)

- **7-day TSS**: Sum of TSS over last 7 days
- **28-day CTL (chronic training load)**: Exponentially weighted moving average of daily TSS
- **7-day ATL (acute training load)**: Short-term fatigue
- **TSB (training stress balance)**: CTL - ATL (form indicator)
- **Weekly hours and ride count**: Am I hitting my 10hr/week target?

### CX-Specific (for build and peak phases)

- **Peak powers**: 10s, 30s, 1min, 2min, 5min bests from this ride
- **Repeatability**: If ride has intervals, compare power across repeats. Fade > 5% = flag
- **Recovery quality**: HR recovery rate between intervals (how fast HR drops in rest periods)

## Analysis Logic

### Ride Classification

Before analyzing, classify what type of ride this was:
1. **Endurance/Z2**: IF < 0.75, mostly Z1-Z2 power
2. **Tempo/Sweet Spot**: IF 0.75-0.88, significant Z3-Z4 time
3. **Threshold**: IF 0.88-1.0, structured intervals at Z4
4. **VO2max/Anaerobic**: IF > 0.85 with significant Z5-Z6 time
5. **Recovery**: IF < 0.6, short duration
6. **Race/Group Ride**: High variability index (NP/avg power), mixed zones

### Season-Aware Feedback

The analysis should change based on the current season phase:

**Base phase (now):**
- Praise Z2 volume. Flag if too much Z3+ time (e.g., "You spent 22 minutes above Z2. In base, try to keep rides like this under 10 minutes of Z3+ unless it's a planned tempo day.")
- Track EF trend week over week. "Your EF at Z2 has improved from 1.02 to 1.10 over the last 3 weeks. Aerobic base is developing."
- Monitor volume. "You're at 8.5 hours this week with 2 days remaining. On track for your 10-hour target."
- Flag HR drift. "HR drifted 4.2% over 90 minutes at Z2 power. Under 5% is solid for base building."

**Build phase:**
- Track threshold power quality in intervals
- Monitor recovery: "Your HR took 45 seconds to drop 30bpm between intervals. Last week it was 38 seconds. Watch recovery trends."
- Ensure enough recovery between hard days

**Peak/Race phase:**
- Focus on power repeatability and short-duration peaks
- Flag staleness (TSB too positive = detraining, too negative = overreaching)

## Workout Suggestion Logic

Based on:
1. What phase of the season we're in
2. What I've done in the last 3-7 days (pull from API)
3. Current fatigue level (ATL/TSB)
4. What tomorrow looks like (is it a rest day? long ride day?)

Example suggestions during base:
- After a rest day: "You're fresh (TSB +15). Good day for your longest Z2 ride of the week. Aim for 2-2.5 hours."
- After back-to-back rides: "3 rides in a row, 6 hours accumulated. Consider an easy recovery spin (45 min, Z1) or a full rest day."
- Mid-week: "You're at 6 hours with 3 days left in the week. Two more 2-hour Z2 rides would hit your 10-hour target."

## Config File (config.yaml)

```yaml
athlete:
  ftp: 250
  max_hr: 193
  resting_hr: 50
  weight_kg: 80.3  # 177 lbs

intervals_icu:
  api_key: "YOUR_API_KEY_HERE"
  athlete_id: "0"  # 0 = self

season:
  phases:
    - name: base
      start: "2026-04-01"
      end: "2026-05-31"
    - name: build1
      start: "2026-06-01"
      end: "2026-07-15"
    - name: build2
      start: "2026-07-16"
      end: "2026-08-31"
    - name: peak
      start: "2026-09-01"
      end: "2026-10-15"
  target_event: "CX Season Opener"
  target_date: "2026-09-12"

training:
  weekly_hour_target: 10
  rides_per_week_target: 5
  
zones:  # percentages of FTP
  z1: [0, 55]
  z2: [55, 75]
  z3: [75, 90]
  z4: [90, 105]
  z5: [105, 120]
  z6: [120, 999]
```

## CLI Usage

```bash
# Analyze most recent ride
python cli.py --latest

# Analyze specific activity
python cli.py --activity-id i138521071

# Weekly summary
python cli.py --weekly

# Season progress check
python cli.py --season-status
```

## Implementation Order

1. **intervals_client.py**: Get API auth and data fetching working. Test with my actual API key. Fetch latest activity, streams, and FIT files.
2. **ride_parser.py**: Parse streams CSV into a clean Ride dataclass. Parse FIT files for session-level metrics. Reconcile FTP values.
3. **metrics.py**: Implement NP, IF, TSS, zone distribution, EF, HR drift, cardiac decoupling. Unit test against the sample ride data I've provided (known values: avg power 146W, NP 150W, avg HR 137, max HR 155, duration 5420s).
4. **analysis.py**: Season-phase-aware interpretation of metrics. Ride classification. Contextual feedback generation.
5. **workout_suggest.py**: Pull recent ride history, compute load metrics, suggest next workout.
6. **report.py**: Markdown-formatted output with sections for ride summary, key metrics, analysis, and next workout suggestion.
7. **cli.py**: Wire it all together with argparse.
8. **Test end-to-end** with real data from my Intervals.icu account.

## Sample Ride Data for Testing

From my April 9, 2026 indoor Zwift ride (activity ID: i138521071):

- Duration: 90.3 minutes (5420 seconds)
- Avg Power: 146W, NP: 150W, Max Power: 265W
- Avg HR: 137bpm, Max HR: 155bpm, Min HR: 79bpm
- Avg Cadence: 91rpm
- Avg Respiration: 27.8 breaths/min
- Quarq power meter, 172.5mm cranks
- L/R balance: ~50/50
- Temperature: 13-14C
- Garmin FTP: 209W, Intervals.icu FTP: 265W
- Single lap (no structured intervals detected)

### Known good analysis values for validation:

- At FTP=250W: IF = 0.60, TSS ≈ 32.6
- HR drift (simple first/second half): 4.2% (HR: 134.5 -> 140.2)
- Power drift: 3.7% (144W -> 149W)
- EF range across 10-min windows: 0.98 - 1.13 W/bpm
- Ride classification: Endurance/Z2
- Respiration trend: 22.4 -> 30.4 breaths/min (rising through ride)

## Future Extensions

- Integrate lactate meter data (manual entry or file upload) for LT1/LT2 validation
- Compare EF trends against LT1/LT2 test results over time
- Pull Zwift workout files to compare planned vs actual
- Seasonal power curve tracking (are my 1min, 5min, 20min bests improving?)
- Export weekly/monthly reports
- Package as Cowork skill for Dispatch triggering from phone
