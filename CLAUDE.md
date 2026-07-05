# DockMind Agent Context

## Skill routing

When the user's request matches an available gstack skill, use it. Routing:
- Product idea pressure test: `/office-hours`
- Visual QA and polish: `/design-review`
- Debugging: `/investigate`
- Browser QA: `/qa`
- Shipping: `/ship`
- GBrain indexing: `/sync-gbrain`

## GBrain Search Guidance

This repo is pinned by `.gbrain-source` for `mongonsh/DockMind`.
When `gbrain` is installed, prefer:
- `gbrain search "live camera detection"` for semantic code lookup.
- `gbrain code-def <symbol>` for function definitions.
- `gbrain code-refs <symbol>` for cross references.

If `gbrain` is not on PATH, run the gstack setup-gbrain flow first.
