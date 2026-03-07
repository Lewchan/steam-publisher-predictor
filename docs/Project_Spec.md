# Steam Publisher Predictor Project Spec

## 1. Goal

This project is a local web tool for estimating Steam game sales.

The tool must support two workflows:

1. Input a released or upcoming Steam game and fetch public data automatically.
2. Fill in subjective design variables manually, then calculate sales using the project formula.

This project is not yet a fully trained prediction system. The first stage is a rule-driven calculator with a clear input model, clear data sources, and replaceable formulas.

## 2. Core Sales Model

### 2.1 CL Base

`cl_base_raw = art_base * (gameplay_depth * scope * narrative) ^ 2`

Scoring assumptions:

- `art_base`: 1 to 10
- `gameplay_depth`: 1 to 10
- `scope`: 1 to 10
- `narrative`: 1 to 10

Design interpretation anchors:

- emergent narrative can justify `scope = 10`
- emergent narrative can justify `narrative = 10`
- universal coupling design can justify `gameplay_depth = 10`

Raw maximum:

- `10 * (10 * 10 * 10)^2 = 10,000,000`

Normalization:

- `cl_base = cl_base_raw / 10,000,000`

Result range:

- theoretical range `0.000001` to `1`

### 2.2 Showmanship Effect

Upper cap:

- `showmanship_effect <= 0.6`

Raw formula:

`showmanship_raw = (art_base * narrative) / 100 * (1 + amplification_tag_total)`

Recommended cap:

- `showmanship_effect = min(0.6, showmanship_raw)`

Amplification tags and weights:

- `sexual_or_gore = 1.0`
- `extreme_novelty = 0.8`
- `real_time_juice = 0.6`
- `systemic_interlock = 1.0`
- `complex_system = 0.6`
- `linear_experience = 0.2`

Tag accumulation rule:

- stage 1 default: additive sum of selected tag weights
- stage 2 can replace this with weighted attenuation if additive behavior is too aggressive

### 2.3 Brand Coefficient

Upper cap:

- `brand_factor <= 1`

Formula:

`brand_factor = ip_factor * 0.5 + influencer_factor * 0.5`

Scoring assumptions:

- `ip_factor`: 0 to 1
- `influencer_factor`: 0 to 1

### 2.4 CL Final

Parameters:

- `k1 = 2`
- `k2 = 2`

Formula:

`cl_final = cl_base * (1 + showmanship_effect * k1) + k2 * brand_factor`

Notes:

- `cl_final` is intentionally allowed to exceed `1`
- this term is the main non-linear strength multiplier in the sales formula

### 2.5 Sales

Formula:

`sales = user_pool * exposure_base * intent_base * purchase_base * (1 + cl_final)^3`

Conversion note:

- `base_conversion = exposure_base * intent_base * purchase_base`

Examples:

- `0.3 * 0.25 * 0.3 = 0.0225`
- `0.2 * 0.25 * 0.3 = 0.015`
- `0.1 * 0.25 * 0.3 = 0.0075`

### 2.6 Long-tail Annual Sales

Formula:

`annual_long_tail_sales = peak_dau * median_line * 40`

Notes:

- `median_line` needs a stricter later definition
- stage 1 treats this as a separate estimator, not part of the launch sales formula

## 3. Input Model

### 3.1 Manual Design Inputs

These values are subjective and cannot be safely scraped directly from public pages.

They must be entered or confirmed manually in the UI.

| Field | Type | Range | Source |
| --- | --- | --- | --- |
| `art_base` | float | 1-10 | manual |
| `gameplay_depth` | float | 1-10 | manual |
| `scope` | float | 1-10 | manual |
| `narrative` | float | 1-10 | manual |
| `ip_factor` | float | 0-1 | manual |
| `influencer_factor` | float | 0-1 | manual |
| `exposure_base` | float | 0-1 | manual or semi-manual |
| `intent_base` | float | 0-1 | manual or calibrated default |
| `purchase_base` | float | 0-1 | manual or calibrated default |
| `user_pool` | integer | >0 | manual or model-assisted |
| `peak_dau` | integer | >=0 | manual or external estimate |
| `median_line` | float | 0-1 | manual |

### 3.2 Boolean Amplification Tags

These are judgment-based tags. They can be suggested by scraped content, but the final value must be manually confirmed.

| Field | Type | Default |
| --- | --- | --- |
| `sexual_or_gore` | bool | false |
| `extreme_novelty` | bool | false |
| `real_time_juice` | bool | false |
| `systemic_interlock` | bool | false |
| `complex_system` | bool | false |
| `linear_experience` | bool | false |

### 3.3 Scraped Public Inputs

These values should be fetched automatically from public sources when possible.

| Field | Type | Use |
| --- | --- | --- |
| `game_name` | text | display and matching |
| `steam_app_id` | integer | unique id |
| `steam_url` | text | source link |
| `release_date` | date | release timing |
| `price_usd` | float | context and later calibration |
| `discount_percent` | float | context |
| `review_count` | integer | proxy for market proof |
| `review_score` | float | quality proxy |
| `tags` | list[text] | genre and pool inference |
| `genres` | list[text] | genre and pool inference |
| `categories` | list[text] | capability inference |
| `short_description` | text | analyst reference |
| `supported_languages` | list[text] | distribution breadth proxy |
| `developer_names` | list[text] | brand reference |
| `publisher_names` | list[text] | brand reference |
| `dlc_count` | integer | monetization complexity proxy |
| `metacritic_score` | integer | optional quality proxy |
| `is_free` | bool | pricing mode |
| `has_demo` | bool | launch support signal |
| `has_achievements` | bool | feature completeness proxy |
| `required_age` | integer | content warning hint |

## 4. Parameter Acquisition Policy

### 4.1 Parameters That Must Be Manual First

The following variables are too subjective or too hidden to treat as reliable scraped values:

- `art_base`
- `gameplay_depth`
- `scope`
- `narrative`
- `ip_factor`
- `influencer_factor`
- `user_pool`
- `exposure_base`
- `intent_base`
- `purchase_base`
- all amplification tags
- `peak_dau`
- `median_line`

Reason:

- they represent interpretation, market framing, or off-platform awareness
- Steam store pages do not expose them in a structured and trustworthy way

### 4.2 Parameters That Can Be Auto-Suggested

The following values can be estimated from scraped data, but must remain editable:

- `user_pool`
- `ip_factor`
- `influencer_factor`
- amplification tags
- `exposure_base`

Auto-suggestion should be shown as a recommendation, not as a locked value.

### 4.3 Parameters That Can Be Fully Scraped

The following values should be auto-filled and normally not typed by the user:

- `game_name`
- `steam_app_id`
- `steam_url`
- `release_date`
- `price_usd`
- `review_count`
- `review_score`
- `tags`
- `genres`
- `categories`
- `developer_names`
- `publisher_names`
- `supported_languages`
- `metacritic_score`
- `is_free`
- `has_demo`
- `has_achievements`
- `required_age`

## 5. Data Sources and Scraping Strategy

### 5.1 Primary Source: Steam Store Public Endpoints

Primary purpose:

- stable app resolution
- public metadata fetch
- review summary fetch

Recommended endpoints:

- Steam search API for app lookup by game name
- Steam app details API for metadata
- Steam review summary API for review count and score

Expected uses:

- `steam_app_id`
- `game_name`
- `price_usd`
- `release_date`
- `developer_names`
- `publisher_names`
- `genres`
- `categories`
- `supported_languages`
- `is_free`
- `has_demo`
- `has_achievements`
- `required_age`
- `review_count`
- `review_score`

### 5.2 Secondary Source: Steam Store HTML

Primary purpose:

- fields not consistently exposed in JSON
- store tags
- edge-case parsing fallback

Expected uses:

- `tags`
- some visual warning signals
- page-structure-based hints for amplification tags

Rule:

- prefer JSON endpoints first
- use HTML parsing only when JSON lacks the needed field

### 5.3 Optional Source: SteamDB or Similar Public Pages

Primary purpose:

- supplementary public metrics
- release history checks
- concurrent-player references
- owner and follower proxy references where publicly visible

Use status:

- optional
- strongly recommended for stage 2
- do not make first-stage prediction depend on this source until parser stability is verified

Expected fields if available from public pages:

- current players
- 24h peak players
- all-time peak players
- follower-related public indicators
- release history metadata
- ownership proxy references if a public page exposes them

Acquisition rule:

- prefer a dedicated scraper adapter per source
- never hard-code SteamDB-specific assumptions into the core calculator
- store raw fetched values separately from normalized features

### 5.3.1 Source Adapter Policy

Every external source must be wrapped by an adapter layer.

Required adapter interface:

- `search(query) -> source matches`
- `fetch(app_id or source id) -> raw source payload`
- `normalize(raw payload) -> normalized project fields`

The project must support adding these adapters later:

- `steam_store`
- `steam_html`
- `steamdb_public`
- `reddit_public`
- `youtube_public`
- `bilibili_public`

Rule:

- the calculator must consume normalized fields only
- scraping logic and market logic must remain separate

### 5.4 Optional Source: Manual External Intelligence

Primary purpose:

- estimate non-store brand and hype factors

Examples:

- creator coverage
- livestream virality
- social trend intensity
- pre-existing IP awareness

Use status:

- manual entry in stage 1
- future automation candidate

## 6. Derived Feature Logic

### 6.0 Game Quality Score

`game_quality_score` is a derived score used to estimate the real product strength of a game.

This score is not the same as Steam review score.

It should combine:

- structured rating signals
- review volume
- community discussion quality
- analyst correction against known benchmark games

Stage 1 objective:

- create a transparent quality estimate on a `0-10` scale
- allow manual override
- keep the computation auditable

#### 6.0.1 Why This Is Hard

The hardest part is not collecting public signals.

The hardest part is score calibration.

Reasons:

- different communities score differently
- high review score on a niche title does not equal broad quality
- high discussion volume can mean controversy, not strength
- early-release review counts and late long-tail review counts mean different things
- genre expectations differ a lot

Therefore:

- raw platform scores must never be used directly as final quality
- benchmark calibration is mandatory

#### 6.0.2 Stage 1 Quality Formula

Stage 1 should treat quality as a weighted estimate:

`game_quality_score = quality_rating_component + quality_volume_component + quality_discussion_component + analyst_adjustment`

Recommended starting rule:

`game_quality_score = min(10, max(0, rating_component * 0.5 + volume_component * 0.2 + discussion_component * 0.3 + analyst_adjustment))`

Where:

- `rating_component` is normalized to `0-10`
- `volume_component` is normalized to `0-10`
- `discussion_component` is normalized to `0-10`
- `analyst_adjustment` is typically between `-1.5` and `+1.5`

This is a starting framework, not a final fixed formula.

#### 6.0.3 Rating Component

Primary purpose:

- estimate perceived player satisfaction

Candidate sources:

- Steam review score
- Steam review count
- Metacritic user score, if available
- Metacritic critic score, if available

Recommended stage 1 rule:

1. use Steam review score as the anchor
2. reduce confidence when review count is too low
3. treat external ratings as secondary references, not first truth

Suggested normalization:

- `steam_rating_norm = steam_review_score_10`
- `rating_confidence = min(1, log1p(review_count) / log1p(5000))`
- `rating_component = steam_rating_norm * rating_confidence + benchmark_genre_baseline * (1 - rating_confidence)`

Meaning:

- if a game has few reviews, pull it toward the benchmark baseline
- if a game has many reviews, trust the Steam score more

#### 6.0.4 Volume Component

Primary purpose:

- estimate how much proof the market has already produced

This is not pure quality, but it prevents tiny-sample scores from being overweighted.

Suggested normalization:

- `volume_component = min(10, log10(review_count + 1) * 2.7)`

Interpretation:

- very low review count contributes little certainty
- large review count implies stronger evidence that the market has validated the title

#### 6.0.5 Discussion Component

Primary purpose:

- estimate external community energy and discussion quality

This should combine quantity and tone.

Candidate sources:

- Steam review text summary and recent trend
- Reddit thread count and engagement
- YouTube creator coverage count
- YouTube view count bands
- Bilibili coverage for Chinese-market titles
- Tieba, NGA, or other community visibility where relevant

Stage 1 rule:

- do not fully automate this yet
- collect discussion references and let the analyst score it on `0-10`

Stage 1.5 rule:

- fetch discussion counts automatically where practical
- keep sentiment and quality interpretation under analyst review

Future automation direction:

1. count discussion threads or videos in a recent window
2. score engagement intensity
3. separate positive buzz from controversy
4. normalize by genre baseline

#### 6.0.6 Benchmark Calibration

Benchmark calibration is mandatory for quality scoring.

Each benchmark title should have:

- known market outcome
- widely recognized quality position
- clear genre identity

Initial benchmark pool should include:

- Balatro
- Stardew Valley
- Palworld
- Warm Snow
- Minecraft
- your chosen `VS` reference
- your chosen `完蛋` reference

Each benchmark record should store:

- genre cluster
- Steam score
- review count
- discussion intensity notes
- final analyst quality score
- calibration notes

Purpose:

- map public signals to a consistent internal `0-10` quality scale
- avoid treating every raw 95 percent Steam rating as equal

#### 6.0.7 Quality Score Output Policy

The UI must show both:

- `game_quality_score`
- the decomposition behind it

Required visible fields:

- `rating_component`
- `rating_confidence`
- `volume_component`
- `discussion_component`
- `analyst_adjustment`
- `game_quality_score`

#### 6.0.8 Relationship to Existing Sales Model

Stage 1 integration rule:

- `game_quality_score` is an explanatory layer first
- do not silently merge it into `cl_base` until benchmark calibration is stable

Allowed stage 1 usage:

- support analyst judgment when entering:
  - `gameplay_depth`
  - `scope`
  - `narrative`
  - `intent_base`
  - `purchase_base`
- optionally display a suggested `intent_base` range from quality score

Not allowed yet:

- fully auto-replacing your manual design score inputs with `game_quality_score`

### 6.1 User Pool

`user_pool` is the hardest variable and must be modeled explicitly.

Stage 1 rule:

- user enters it manually
- tool can later suggest a value based on genre clusters

Future estimation route:

1. infer primary and secondary genres from Steam tags
2. detect cross-genre status
3. sum or blend reachable audience pools from genre buckets
4. apply overlap discount to avoid double counting

Needed support data:

- internal genre bucket table
- per-genre pool baseline
- cross-genre overlap matrix

### 6.2 Exposure Base

Stage 1:

- manual input

Future estimation route:

- review velocity proxy after launch
- wishlist or follower proxies if ever available
- publisher track record
- influencer and trailer heat

### 6.3 Intent Base

Stage 1:

- default value with manual override

Candidate proxies:

- review sentiment
- tag-market fit
- trailer promise clarity
- page conversion quality signals

### 6.4 Purchase Base

Stage 1:

- default value with manual override

Candidate proxies:

- price point
- launch discount
- quality proof
- audience purchasing power by genre

### 6.5 IP Factor

Stage 1:

- manual score

Future structured inputs:

- known franchise yes or no
- previous title sales band
- existing brand search popularity

### 6.6 Influencer Factor

Stage 1:

- manual score

Future structured inputs:

- number of top creator videos
- peak viewer coverage
- short-video trend density

### 6.7 Amplification Tag Suggestion

Stage 1:

- manual checkbox

Future heuristic suggestions from tags and text:

- `sexual_or_gore`: mature content descriptors, explicit tags
- `extreme_novelty`: novelty-heavy tags and unique premise keywords
- `real_time_juice`: action, horde, roguelite, combat feedback indicators
- `systemic_interlock`: sandbox, colony sim, immersive sim, survival craft signals
- `complex_system`: strategy, automation, management, sim complexity indicators
- `linear_experience`: visual novel, walking sim, strongly guided story indicators

These suggestions must remain editable and auditable.

## 7. Product Requirements

### 7.1 Main Workflow

The web app must support this sequence:

1. user enters game name, Steam URL, or app id
2. system fetches Steam public data
3. system computes a first-pass quality reference from public signals
4. system displays scraped metadata and quality decomposition
5. user fills or adjusts manual variables
5. system computes:
   - `cl_base`
   - `showmanship_effect`
   - `brand_factor`
   - `cl_final`
   - `sales`
   - optional `annual_long_tail_sales`
6. system displays intermediate values and final result

### 7.2 Explainability Requirement

The UI must show all intermediate values, not only final sales.

Required visible outputs:

- `rating_component`
- `rating_confidence`
- `volume_component`
- `discussion_component`
- `game_quality_score`
- `cl_base_raw`
- `cl_base`
- `amplification_tag_total`
- `showmanship_raw`
- `showmanship_effect`
- `brand_factor`
- `cl_final`
- `base_conversion`
- `sales`
- `annual_long_tail_sales`, if enough inputs exist

### 7.3 Editing Requirement

All manual values must remain editable after scraping.

Scraped data must be visible and separated from manual judgments.

### 7.4 Scenario Requirement

The UI should support scenario comparison later:

- conservative
- baseline
- optimistic

This is not mandatory for stage 1, but the data model should allow it.

## 8. Data Schema Requirement

Stage 1 should store a prediction record as:

```json
{
  "query": "Balatro",
  "scraped": {
    "steam_app_id": 2379780,
    "game_name": "Balatro",
    "release_date": "2024-02-20",
    "price_usd": 14.99,
    "review_count": 100000,
    "review_score": 9.7,
    "genres": ["Strategy", "Indie"],
    "tags": ["Roguelike", "Card Game"]
  },
  "manual": {
    "art_base": 7,
    "gameplay_depth": 8,
    "scope": 6,
    "narrative": 2,
    "ip_factor": 0.1,
    "influencer_factor": 0.6,
    "user_pool": 3000000,
    "exposure_base": 0.3,
    "intent_base": 0.25,
    "purchase_base": 0.3,
    "sexual_or_gore": false,
    "extreme_novelty": true,
    "real_time_juice": true,
    "systemic_interlock": false,
    "complex_system": false,
    "linear_experience": false
  },
  "computed": {
    "cl_base_raw": 451584,
    "cl_base": 0.0451584,
    "amplification_tag_total": 1.4,
    "showmanship_effect": 0.336,
    "brand_factor": 0.35,
    "cl_final": 0.775,
    "base_conversion": 0.0225,
    "sales": 375000,
    "annual_long_tail_sales": null
  }
}
```

## 9. Implementation Boundary

### 9.1 First-Stage Scope

Must implement:

- Steam lookup by game name or URL
- public metadata scraping
- benchmark-ready quality scoring framework
- manual input form for subjective variables
- formula calculation with full intermediate output
- local-only usage

Must not pretend to implement yet:

- reliable automatic user-pool estimation
- reliable automatic influencer estimation
- reliable automatic IP estimation
- real DAU tracking
- full market-wide brand intelligence

### 9.2 First-Stage Philosophy

The system should be honest:

- scrape objective public fields
- ask the user for subjective judgments
- expose every formula step
- avoid fake precision

## 10. Immediate Build Tasks

1. Replace the current generic formula editor with a structured form matching this spec.
2. Add a dedicated calculator service for:
   - `cl_base`
   - `showmanship_effect`
   - `brand_factor`
   - `cl_final`
   - `sales`
   - `annual_long_tail_sales`
3. Add Steam HTML tag scraping as a secondary fetch path.
4. Add persistent save and reload for prediction records.
5. Add calibration pages for the sample games:
   - VS
   - 完蛋
   - 暖雪
   - 星露谷
   - 帕鲁
   - MC

## 11. Table-Driven User Pool System

The `user_pool` module must be table-driven.

It must not be hard-coded as one-off if/else logic in the UI or calculator.

### 11.1 Goal

Estimate Steam-reachable effective audience size using:

- genre base pools
- cross-genre expansion
- overlap reduction
- platform fit
- region fit
- price fit

### 11.2 Formula

Recommended stage 1 formula:

`user_pool = genre_pool_total * platform_fit * region_fit * price_fit`

Where:

`genre_pool_total = weighted_genre_sum * overlap_adjustment`

And:

`weighted_genre_sum = primary_genre_pool * 1.0 + secondary_genre_pool * 0.6 + tertiary_genre_pool * 0.35`

Recommended overlap range:

- `0.55` to `0.95`

### 11.3 Genre Pool Table

The system must load genre pool baselines from a data table.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `genre_id` | text | stable internal key |
| `genre_name` | text | display label |
| `base_pool` | integer | Steam effective audience baseline |
| `steam_fit_default` | float | default platform fit hint |
| `notes` | text | calibration notes |

Initial example table:

| genre_id | genre_name | base_pool |
| --- | --- | --- |
| `survivorlike` | Survivor-like | 8000000 |
| `roguelite_action` | Roguelite Action | 12000000 |
| `farm_life_sim` | Farm/Life Sim | 18000000 |
| `social_coop` | Social Co-op | 22000000 |
| `survival_crafting` | Survival Crafting | 25000000 |
| `fantasy_mmo_like` | Fantasy MMO-like | 30000000 |
| `open_world_survival` | Open World Survival | 35000000 |

These are working calibration baselines only.

They must be revised after benchmark fitting.

### 11.4 Mapping Steam Tags To Pool Buckets

The system must load a separate mapping table that translates scraped Steam tags into internal pool buckets.

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `steam_tag` | text | scraped Steam tag |
| `genre_id` | text | mapped internal bucket |
| `weight` | float | contribution strength |

Examples:

| steam_tag | genre_id | weight |
| --- | --- | --- |
| `Open World` | `open_world_survival` | 1.0 |
| `Survival` | `survival_crafting` | 0.9 |
| `Crafting` | `survival_crafting` | 0.8 |
| `Roguelite` | `roguelite_action` | 1.0 |
| `Farming Sim` | `farm_life_sim` | 1.0 |

### 11.5 User Pool Output Requirement

The UI must show:

- detected mapped genres
- raw weighted genre sum
- overlap adjustment
- platform fit
- region fit
- price fit
- final `user_pool`

## 12. Quality Scoring Data Policy

Quality scoring is the most failure-sensitive part of the project.

If quality scoring is wrong, the final sales estimate will drift badly.

Therefore quality scoring must use multi-source evidence, not one metric.

### 12.1 Required Quality Inputs

Stage 1 quality should consider:

- Steam review count
- Steam positive ratio or review score
- Steam recent review trend if available
- public discussion intensity
- public discussion quality
- benchmark comparison

Stage 2 quality should additionally consider:

- concurrent-player proof
- creator/video discussion scale
- community persistence

### 12.2 Quality Source Layers

Layer A: objective platform proof

- Steam review count
- Steam review score
- Steam recent review state
- SteamDB concurrency-like metrics if public and available

Layer B: external attention proof

- Reddit thread count and engagement
- YouTube creator coverage count
- Bilibili video count and engagement for Chinese-market titles
- other forum discussion count where relevant

Layer C: analyst interpretation

- controversy vs genuine praise
- niche bias correction
- launch window distortion correction
- benchmark anchor correction

### 12.3 Quality Score Decomposition

The project should define:

`quality_score = rating_strength * 0.45 + proof_strength * 0.20 + discussion_strength * 0.20 + persistence_strength * 0.15 + analyst_adjustment`

Working interpretation:

- `rating_strength`: how strong and trustworthy the public rating signal is
- `proof_strength`: how much market evidence exists
- `discussion_strength`: how large and healthy the public conversation is
- `persistence_strength`: whether the game maintains attention over time

Stage 1 note:

- `persistence_strength` can be partially manual until enough source adapters exist

### 12.4 Rating Strength Rule

Rating strength must not be equal to raw good-review ratio.

It must combine:

- satisfaction level
- sample size confidence
- benchmark genre correction

Recommended stage 1 structure:

`rating_strength = normalized_rating * confidence_weight + genre_baseline * (1 - confidence_weight)`

Where:

- `normalized_rating` is a `0-10` conversion from Steam review score
- `confidence_weight` is derived from review count

### 12.5 Discussion Strength Rule

Discussion strength must consider both amount and quality of discussion.

Do not equate pure controversy with healthy quality discussion.

Required output components:

- `discussion_count_signal`
- `discussion_engagement_signal`
- `discussion_sentiment_signal`
- `discussion_strength`

Stage 1 implementation:

- count what can be counted automatically
- let analyst supply the final correction

### 12.6 Benchmark Requirement

Quality scoring must be benchmarked against an internal virtual anchor.

Anchor name:

- `SAO_Anchor`

Definition:

- a virtual top-tier ideal game used as the maximum reference for market strength dimensions

Important:

- `SAO_Anchor` is not a real market sample
- it is a calibration ceiling, not a training row

Each real benchmark title must be compared against:

- `SAO_Anchor`
- other benchmark titles in the same genre cluster

### 12.7 Quality Failure Rule

If discussion data cannot be fetched or quality evidence is incomplete:

- the system must lower quality confidence
- the UI must show that the score is partial
- the app must not silently present a precise-looking quality score

Required fields:

- `quality_confidence`
- `missing_quality_sources`

## 13. Data Collection Modules

The implementation should be split into independent collectors.

### 13.1 Required Collectors

- `steam_store_collector`
- `steam_html_collector`
- `quality_signal_collector`
- `discussion_signal_collector`
- `user_pool_mapper`

### 13.2 Collector Responsibilities

`steam_store_collector`

- lookup by game name
- fetch app details
- fetch review summary

`steam_html_collector`

- fetch tags and fallback metadata
- parse page-only public signals

`quality_signal_collector`

- normalize rating-related fields
- normalize proof-related fields
- combine public quality evidence

`discussion_signal_collector`

- collect cross-community counts and engagement proxies
- keep source-level raw values

`user_pool_mapper`

- map tags to pool buckets
- load genre baseline table
- compute effective audience estimates
