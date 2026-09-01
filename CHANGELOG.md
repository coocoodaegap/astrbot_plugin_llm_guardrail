# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，并使用 [语义化版本](https://semver.org/lang/zh-CN/)。

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
