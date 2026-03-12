# script_writer

## Purpose

基于结构化输入配置生成脚本，形成下游分镜阶段的核心叙事基础。

## Reads

- `projects/<project>/input/input.json`

## Writes

- `projects/<project>/script/script.json`

## Required Output

`script.json` 至少应包含：

- `title`
- `summary`
- `audio_track`
- `visual_track`
- `beats`

其中 `beats` 应表达段落级节奏或叙事单元，为分镜规划提供稳定输入。

## Runtime Expectations

- 只依赖 `input.json` 中的标准字段
- 输出必须是结构化 JSON，而不是纯散文文本
- 事件写入规则与主 workflow 一致

## Failure Behavior

- 如果输入字段不足以支撑脚本生成，应中止并报告缺失原因
- 不得输出半结构化或格式损坏的脚本文件
