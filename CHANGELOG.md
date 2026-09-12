# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 的结构，并使用 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- `rag_judge` 新增 `experience_candidate_threshold`。留空时仅记录规则命中；有效值为 `[0, 1]`，最高分达到阈值即可作为经验候选入库，而不改变 RAG 命中、动作或检索流程；无效值会禁用经验候选并写入配置警告。
- Pages 的 RAG 规则参数新增“经验候选阈值”输入，并在经验详情和列表中区分“规则命中”与“高分候选”。
- 新增默认关闭的实验性“主动 Agent 请求入口”。开启 `debug_settings.enable_agent_request_entry` 后，同一 AstrBot Context、使用标准主 Agent hooks 且未经过 `on_llm_request` 的请求会在 `ToolLoopAgentRunner.reset` 组装前接入 Step 3／4，随后继续原 Agent 与既有 Step 5；不补跑 Step 1／2，也不改变发起方选择的 Provider。
- 主动 Agent 请求在 Step 3 阻断时不会调用 Provider；未阻断时只提交策略允许修改的 prompt 字段，并以 `entry=agent_reset` 记录入口，便于与普通 `on_llm_request` 链路区分。

### Changed

- RAG 经验记录的列表排序和容量淘汰改为最高分优先、同分时最近编辑优先；来源身份缺失的最高分证据仍保留其分数和预览供诊断，但不会开放写入知识库。
- `max_text_chars` 的默认值改为 `0`（不截断），并将系统兜底配置、各执行 Rail 的配置归一化与运行期缺省值同步为该语义。

### Security

- 彻底移除以固定 `INTERNAL_MARKER` 文本识别内部请求的机制。Guardrail 自有的 LLM 旁审、虚拟复检和重试生成改用支持嵌套、并发隔离与异常恢复的 task-local 运行时身份，并在 Step 1、Step 3、Step 5 及 Agent 收尾阶段统一跳过内部调用。
- prompt、system prompt 和 payload 不再能够声明内部身份；旧 marker 字符串按普通输入／输出处理。同步移除旁审提示词中的 marker 以及 `metadata_leakage_detector` 对该字符串的特殊判定。

## [0.7.1] - 2026-09-09

### Fixed

- 修复 `rag_judge` 对下游 payload 的隐式裁剪：移除 `matched_text` 前 3 条、`evidence` 前 5 条及单条文本 500 字符的固定上限。检索数量由 `top_k` 控制，`matched_text` 格式化全部达标记录的全文，`evidence` 保留全部召回记录；日志摘要仍可独立截断。

## [0.7.0] - 2026-09-09

### Added

- 为策略内所有规则与元件节点新增可修改的 `binding_id`；同一规则可以不同 Binding ID 多次加入同一策略，旧元件的 `component_id` 字段继续作为兼容镜像保留。
- 新增策略节点重命名能力：修改 Binding ID 时同步更新节点顺序、依赖、逻辑门输入、节点列表以及 `${node_id.field}` 引用；规则库身份 `rule_id` 仍只能通过“另存为”改变。
- 添加规则或元件时，Binding ID 会自动采用来源原名；若名称已被占用，则依次尝试 `_2`、`_3` 等可用名称。
- `rag_judge` 新增 `matched_evidence_count`，用于统计全部达到 `min_score` 的检索记录。
- `rag_judge` 新增 `value_item_template` 与 `value_separator`，可使用 `${value}` 和 `${source}` 控制 `matched_text` 的逐项格式与拼接方式。

### Changed

- 将 `strengthen_prompt` 从可复用规则迁移为 Step 4 策略局部元件；公用常量继续承担固定文本复用。
- `strengthen_prompt.insertion_text` 现在可读取渲染时已经提交的任意节点 payload 字段，支持 RAG 证据和 `compose_text` 产出的动态提示词。
- 旧快照或旧策略包中的 `strengthen_prompt` 规则绑定会以内联元件方式兼容迁移。
- `rag_judge.matched_text` 现在只包含达到 `min_score` 的前 3 条记录；`evidence_count` 与受限的 `evidence` 仍保留实际召回结果，以便观察低分记录和排查知识库质量。
- 当一次 RAG 查询同时返回有分数与无分数记录时，无分数记录不再参与匹配；只有后端完全不提供分数时，才维持“返回 evidence 即可匹配”的兼容行为。

## [0.6.2] - 2026-09-04

### Added

- 新增策略局部 `compose_text` 元件：在 Step 1、3、5 组合当前阶段可见文本、系统常量和已完成节点的值，供后续节点经 `inspection_template` 消费。

### Changed

- Pages 的策略编辑器统一以系统设置同款 `setting-key` 徽标显示字段键；规则和元件类型选择项也展示其模板键，方便将界面配置与 README、策略包 JSON 对照。
- README 补充策略图字段对照、`depend_on` 的控制流语义，以及 `random_signal`、`compose_text` 的定位和使用方式。

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
