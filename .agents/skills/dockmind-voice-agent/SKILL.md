---
name: dockmind-voice-agent
description: Interpret warehouse voice commands and trigger DockMind actions.
---

# DockMind Voice Agent

## Goal
Let a warehouse worker operate DockMind hands-free while looking at cargo or the truck bay.

## Inputs
- Voice transcript
- Current DockMind plan JSON
- Current truck preset
- Current role tab

## Commands
1. "Scan cargo" -> run YOLO detection on the current image or camera frame.
2. "Analyze manifest" -> generate cargo manifest from real detections.
3. "Optimize plan" -> re-run truck layout with current cargo.
4. "Use refrigerated truck" -> switch preset to `reefer`.
5. "Generate loader skill" -> create a gstack-compatible loader skill.

## Done Criteria
- The command maps to one DockMind action.
- The UI confirms the action.
- The browser speaks a short result.
