# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，并使用 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.6.1] - 2026-09-04

### Changed

- 移除 `sanitize` 命中动作。`plain_keywords` 和 `regex_pattern` 现在始终在 payload 提供 `sanitized`，其值按规则的 `sanitizer` 替换文本处理全部命中区间（留空则移除）；只有策略显式消费该字段时才会改变后续内容。
- 清理未使用的字面替换辅助函数；命中动作白名单改由配置层集中定义，Pages 也移除了未使用的模板参数。

### Fixed

- 加载策略时，未知命中动作统一回退为 `observe`，未知错误动作统一回退为 `discard`；运行时动作解析也采用相同兜底。

## [0.6.0] - 2026-09-03

### Added

- 新增全流程策略局部元件 `random_signal`：以唯一配置 `probability` 生成独立真假信号，并在 payload 记录概率、抽样值与结果。
- `random_signal` 可在五个 Rail 执行，适合作为提示词强化、路由、RAG/LLM 旁审等策略分支的前置条件。

### Fixed

- Step 2/4 的通用信号元件在 `action_on_hit: default` 时会回退到 Rail 默认命中动作；`action_on_error: default` 会回退到 Rail 默认错误动作。默认仍为 `observe` / `discard`。
- 对 Step 2/4 中命中 `block` 或错误回退为 `block` 的通用信号元件，现在会实际终止请求并使用 Rail 阻断提示。

- Step 2 和 Step 4 增补策略级“默认命中动作”“默认错误动作”及“阻断提示”配置。
- Step 5 的默认命中动作增补 `observe`，可将使用 `default` 的输出节点统一置于观测模式。
- 策略图按所在 Rail 过滤命中动作：`retry_generation` 仅在 Step 5 显示。

## [0.5.0] - 2026-09-01

### Added

- 新增策略局部元件 `context_extractor`，可从当前会话历史提取经过边界处理的文本上下文，供检查内容重定向中的 `inspection_template` 消费。
- `context_extractor` 支持输入、最终请求和输出 Rail；多个元件共享同一次会话历史读取，但各自独立切片。
- 新增对 AstrBot `ContentPart` 历史内容的兼容：保留文本片段，对 system、tool、空、损坏或纯非文本记录生成中性说明。

## [0.4.1] - 2026-09-01

### Fixed

- 修正共享常量包迁移的遗留引用。

## [0.4.0] - 2026-08-31

### Added

- 发布可视化策略编排、输入/请求/输出检查、提示词加固、Provider 路由、输出重试与策略包管理的首个测试版里程碑。
