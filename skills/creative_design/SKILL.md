---
name: creative-design
description: 创意需求定稿阶段。将一句话需求先整理为 Creative Brief，再输出结构化 input.json，作为主链第一步。
---

# creative_design

## 中文名

`创意需求定稿`

## Purpose

把“创意引导 + 输入结构化”合并为一个前置阶段，确保主链从第一步开始就有稳定的执行输入。

## Reads

- `projects/<project>/request.md`（用户原始输入或草稿）

## Writes

- `projects/<project>/brief/creative-brief.md`
- `projects/<project>/brief/intake.json`
- `projects/<project>/request.md`（标准化覆盖）
- `projects/<project>/input/input.json`

## Execution

统一执行脚本：

`python3 scripts/run_creative_design.py --project <project-path>`

该脚本会串行执行：

1. `run_creative_brief_intake.py`
2. `run_input_parser.py`

## Compatibility

- `creative_brief_intake` 和 `input_parser` 仍可单独运行，用于调试或局部重跑。
