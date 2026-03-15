---
name: creative-design
description: 创意需求定稿阶段。引导需求→生成多方案→用户确认→结构化输入，作为主链第一步。
---

# creative_design

## 中文名

`创意需求定稿`

## Purpose

把"需求引导 → 创意方案选择 → 输入结构化"合并为一个前置阶段，确保主链从用户真正认可的创意方向开始执行。

**未经用户确认创意方向，不得推进到生产流水线。**

## 完整流程（Claude 驱动）

```
Step 1: creative_brief_intake
  用户一句话 → 多轮引导澄清 → brief/creative-brief.md + brief/intake.json

Step 2: creative_proposal              ← 新增，人在环节点
  读取 intake.json → 生成 3 个差异化方案 → 展示给用户
  用户确认选择 → brief/proposals.json + brief/selected-concept.json

Step 3: input_parser
  intake.json + selected-concept.json → input/input.json（含模型配置）
```

## Reads

- `projects/<project>/request.md`（用户原始输入或草稿）

## Writes

- `projects/<project>/brief/creative-brief.md`
- `projects/<project>/brief/intake.json`
- `projects/<project>/brief/proposals.json`
- `projects/<project>/brief/selected-concept.json`
- `projects/<project>/request.md`（标准化覆盖）
- `projects/<project>/input/input.json`

## 脚本执行（自动化 fallback）

```bash
python3 scripts/run_creative_design.py --project <project-path>
```

脚本串行执行：
1. `run_creative_brief_intake.py`
2. `run_creative_proposal.py`（如果 `brief/selected-concept.json` 不存在）
3. `run_input_parser.py`

**注意**：Claude 驱动模式下，Step 2 是交互式的，用户确认后 `selected-concept.json` 已写入，脚本会跳过 `run_creative_proposal.py` 直接继续。

## Compatibility

- `creative_brief_intake`、`creative_proposal`、`input_parser` 仍可单独运行，用于调试或局部重跑。
