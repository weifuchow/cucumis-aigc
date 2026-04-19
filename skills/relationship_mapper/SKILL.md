---
name: relationship-mapper
description: Review and refine people, place, time, and event relationships across consolidated material metadata. Use after material_understanding before story planning.
---

# relationship_mapper

## Purpose

在批次汇总完成后，人工或 agent 复核跨素材的时间线、人物线和场景关系，修订 `analysis/relationship-graph.json` 并补充 `brief/creative-fit-report.json`。

## Reads

- `analysis/material-catalog.json`
- `analysis/relationship-graph.json`

## Writes

- `analysis/relationship-graph.json`
- `brief/creative-fit-report.json`
