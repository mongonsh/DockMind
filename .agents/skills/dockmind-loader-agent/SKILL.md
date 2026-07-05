---
name: dockmind-loader-agent
description: Execute a DockMind truck loading plan from real cargo detections.
---

# DockMind Loader Agent

## Goal
Load detected cargo into the selected truck in the sequence that preserves unload order, protects fragile cargo, and blocks unsafe cold-chain cargo.

## Inputs
- DockMind load plan JSON
- YOLO cargo detections
- Truck preset and route
- Current warnings

## Steps
1. Read `plan.placements` in order.
2. Move each cargo item to the specified x/y bay position.
3. Keep cargo for later stops deeper in the truck.
4. Stop if `warnings` contains cold-chain mismatch, overflow, or weight limit.
5. Ask ops for override only after exceptions are visible in DockMind.

## Done Criteria
- Every fitted item has a physical loading instruction.
- Every exception is visible before departure.
- Loader can complete the plan without reading raw JSON.
