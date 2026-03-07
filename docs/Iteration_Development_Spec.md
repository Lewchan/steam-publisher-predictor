# Iteration Development Spec

## 1. Purpose

This document defines how the `steam-publisher-predictor` project should be iterated.

It is intended for semi-automatic or automatic development cycles where the coding agent:

- reads the current project state
- selects the next highest-value task
- implements a bounded change
- verifies the result
- records what changed and what remains

The goal is not blind automation.

The goal is controlled iteration with clear scope, visible assumptions, and stable project direction.

## 2. Project Objective

Build a local web tool that:

1. accepts a Steam game name, URL, or app id
2. fetches public Steam and related public market data
3. estimates quality and audience strength
4. calculates user pool, `CL`, and predicted sales
5. exposes intermediate values clearly enough for analyst review

## 3. Core Product Principles

Every iteration must preserve these principles:

1. Transparency first
   - the app must show intermediate calculations
   - black-box scoring is not allowed unless explicitly introduced later

2. Objective data and subjective judgment must stay separate
   - scraped public fields must be separated from analyst-entered fields
   - inferred values must be labeled as inferred

3. Quality scoring is high-risk
   - no single metric may dominate quality scoring without justification
   - confidence and missing data must be surfaced

4. User pool is table-driven
   - no hidden one-off genre logic
   - mappings and pool baselines must live in data files or clearly isolated services

5. Iterations must remain locally runnable
   - each iteration should keep the Streamlit app launchable
   - each iteration should keep tests runnable

## 4. Iteration Unit

Each development iteration should be small enough to complete safely in one pass.

Preferred iteration size:

- one feature slice
- one refactor slice
- one scraper adapter
- one scoring improvement
- one calibration improvement

Avoid bundling multiple unrelated ideas into one iteration.

## 5. Iteration Priority Order

When choosing the next automatic iteration, use this order unless the user overrides it.

### Priority A: Calculation correctness

Examples:

- sales formula errors
- `CL` cap behavior
- quality score decomposition errors
- user pool mapping bugs
- incorrect handling of missing data

### Priority B: Data acquisition coverage

Examples:

- Steam HTML tag scraping
- SteamDB adapter
- discussion-source adapters
- fallback logic for unstable endpoints

### Priority C: Calibration and benchmark support

Examples:

- benchmark record schema
- `SAO_Anchor` handling
- benchmark comparison UI
- calibration save/load

### Priority D: Workflow usability

Examples:

- save prediction record
- load prior record
- compare scenarios
- export results

### Priority E: Secondary polish

Examples:

- layout cleanup
- copy changes
- visual improvements

## 6. Mandatory Iteration Workflow

Every automatic iteration should follow this sequence.

1. Read current relevant files
2. Identify the exact target change
3. Avoid changing unrelated logic
4. Implement the smallest complete version
5. Run local verification
6. Report:
   - what changed
   - what was verified
   - what remains risky

## 7. Allowed Automatic Work

The agent may automatically perform:

- create or edit source files
- add or refine services
- add or refine data tables
- add or refine tests
- improve README and project docs
- improve UI structure
- add safe adapters for public data pages
- add confidence and missing-data handling

## 8. Restricted Automatic Work

The agent must not do these without explicit user approval:

- replace the core sales model with a fundamentally different model
- remove existing scoring outputs that explain the model
- introduce hidden proprietary or paid data dependencies
- introduce destructive data migrations
- change benchmark philosophy
- hard-code commercial conclusions as facts
- silently alter calibration baselines without documenting it

## 9. Definition Of Done For An Iteration

An iteration is complete only when all relevant conditions are met:

1. The change is implemented in code or config
2. The app still imports and runs locally
3. Relevant tests pass, or the lack of tests is explicitly stated
4. Documentation is updated if behavior changed
5. The change is understandable from the UI or code outputs

## 10. Required Verification

Each iteration should verify as many of these as apply:

- `pytest`
- direct import check
- one real data fetch check if scraper logic changed
- one calculator check if scoring logic changed
- one UI smoke check if Streamlit layout changed

If a verification step cannot be run, the iteration report must say so directly.

## 11. Required Documentation Updates

Update docs whenever one of these changes:

- formulas
- scoring weights
- caps
- input fields
- output fields
- source adapters
- genre pool baselines
- tag mapping tables

Primary docs:

- [Project_Spec.md](/D:/Codex-Workspace/SteamPublisher/steam-publisher-predictor/docs/Project_Spec.md)
- [README.md](/D:/Codex-Workspace/SteamPublisher/steam-publisher-predictor/README.md)

## 12. Iteration Output Format

After each automatic iteration, the report should contain:

1. Change summary
2. Verification summary
3. Current risks
4. Recommended next iteration

The report should remain short and concrete.

## 13. Automatic Iteration Backlog

Unless the user redirects priorities, future iterations should prefer this order.

1. Persist prediction records to local JSON
2. Add benchmark record schema and benchmark seed data
3. Add benchmark comparison page
4. Add SteamDB public adapter
5. Add discussion-source adapter abstraction
6. Add Reddit public discussion collector
7. Add YouTube public discussion collector
8. Add Bilibili public discussion collector
9. Add quality confidence UI warnings
10. Add scenario comparison mode
11. Add exportable report view
12. Add calibration controls for weights and caps

## 14. Benchmark Iteration Rules

Benchmark-related iterations must follow these rules:

1. `SAO_Anchor` is a virtual ceiling, not a real sample
2. Real benchmark titles must be stored separately from the anchor
3. Benchmark updates must be traceable
4. Any benchmark change that affects formulas or weights must be documented

## 15. Data Adapter Rules

Every new public-data adapter must:

1. isolate source-specific parsing
2. return normalized project fields
3. preserve raw source values where useful
4. fail gracefully
5. avoid crashing the calculator when one source is missing

## 16. Scoring Rules

All scoring modules must:

1. output their subcomponents
2. output confidence where applicable
3. report missing inputs
4. avoid pretending to be final truth

This applies to:

- quality scoring
- user pool estimation
- `CL`
- long-tail estimates

## 17. Automation Safety Rules

For automated development cycles:

1. prefer incremental changes over rewrites
2. do not modify unrelated files without reason
3. do not remove existing tests unless replacing them
4. do not hide uncertainty
5. preserve a working local app at the end of each cycle

## 18. Current Execution Policy

For now, automatic development should focus on:

1. data-source coverage
2. scoring transparency
3. benchmark calibration support
4. persistent local workflow support

It should not yet focus on:

1. visual polish as a primary goal
2. advanced deployment
3. multi-user features
4. premature machine-learning training pipelines

## 19. Trigger Rule For Next Iterations

If the user says "continue development", the agent should select the highest-priority unfinished item that:

- fits the current architecture
- can be completed safely in one bounded iteration
- improves calculation trustworthiness or workflow usefulness

If multiple choices are available, prefer the one that increases data quality or scoring trust.
