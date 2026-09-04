# LLM Guardrail

> 为 AstrBot 的每次 LLM 请求提供可编排的输入、请求、提示词、路由与输出护栏。

`LLM Guardrail` 不是只做关键词拦截的安全插件。它把一次 LLM 请求拆为五个明确阶段，让你按策略组合本地检测、RAG/LLM 复核、提示词加固、Provider 路由和输出处置，同时保留清晰的依赖、日志和会话状态边界。

> 当前为 **v0.6.2 测试版**。欢迎用于真实群聊或私聊环境，但建议先从观察模式和少量策略开始配置。

## 能做什么

```text
用户输入
  -> Step 1 输入检查
  -> Step 2 Provider 路由
  -> Step 3 最终请求检查
  -> Step 4 提示词加固
  -> 主模型生成
  -> Step 5 输出检查 / 有界重试
```

下面是一套完整策略的依赖图示例：

![LLM Guardrail 策略依赖图示例](https://assets.coocoodaegap.com/astrbot_plugin_llm_guardrail_preset1.png)

| 能力 | 说明 |
| --- | --- |
| 输入与最终请求检查 | 支持关键词、正则、本地检测元件、逻辑门、RAG 与 LLM 复核；可观察、净化或阻断。 |
| 提示词加固 | 可按前序结果替换请求或向 system prompt、临时上下文、输入包装注入固定加固文本。 |
| Provider 路由 | 支持策略内 first-hit 路由，在本轮请求中选择聊天 Provider。 |
| 输出检查 | 支持质量、格式、敏感回显、元数据泄露、拒答泄露、语言漂移等检测，以及观察、净化、阻断。 |
| 有界输出重试 | Step 5 命中 `retry_generation` 时，只使用本轮实际 Provider 重新生成并再次检查输出；通过才交付，失败或耗尽则一次性阻断。 |
| 策略编排 | Pages 中维护规则库、策略、依赖图、局部元件和会话范围；规则可跨策略复用。 |
| 数据流与并发 | 同一策略执行内可显式消费受限 payload、使用输出重定向；同一 Rail 的已就绪检查可并发执行，并按稳定顺序结算。 |
| 策略包迁移 | 支持规则包、自包含策略包与公用常量包的导入导出；引用常量随包迁移，ID 冲突可预览并以副本或替换方式原子提交。 |

## 先看懂策略图：节点、依赖与字段名

| Pages 中的名称 | 内部字段名 | 含义 |
| --- | --- | --- |
| 启用此规则／元件 | `enabled` | 关闭后节点不参加本轮调度。 |
| 优先级 | `priority` | 数值越小越先执行；同一批可并行的节点仍按稳定顺序结算。 |
| 依赖 | `depend_on` | 当前节点开始前必须满足的前置条件。它指向**另一个节点的 ID**，而不是某项配置。 |
| 检查内容重定向 | `inspection_template` | 指定本节点实际检查的文本；留空则检查当前 Step 的原文。 |
| 命中动作 | `action_on_hit` | 节点命中后采用的动作；`default` 表示沿用规则或 Step 默认值。 |
| 错误动作 | `action_on_error` | 节点执行异常时采用的动作；`default` 同样表示沿用默认值。 |

`depend_on` 是**控制流依赖**，不负责传递文本。普通 `source` 表示“来源节点命中后才运行”；`!source` 表示来源未命中；`?source` 表示来源已执行即可；`~source` 表示来源执行失败时才运行。Pages 的“选择依赖项”会用可视化方式设置它，通常不必手写。若要读取来源产生的数据，则在 `inspection_template` 中写 `${source.field}`；这是一项非阻塞数据引用，想确保来源先完成时仍应同时设置 `depend_on`。

## v0.6.2：概率编排、文本组合与全流程动作回退

`random_signal`（Pages 名称：“随机信号”）是策略局部的**概率开关**，不是风险检测器。它只按 `probability`（`0.0` 至 `1.0`）为每次策略执行独立生成真假信号，并在 payload 中记录概率、抽样值和结果。它可放在全部五个 Step，适合灰度启用 `strengthen_prompt`、模型路由或 RAG/LLM 旁审分支；不要把它作为唯一的基础安全检查。

使用方法是：先创建一个“随机信号”元件并给它一个 ID，例如 `sample_review`；再在**下游节点**的“依赖（`depend_on`）”中选择它。普通依赖表示只有抽样命中才继续执行。`probability: 0` 永不命中，`probability: 1` 每次命中；中间值适合灰度加固、抽样旁审和观察性实验。它可使用该 Rail 的 `observe` 或 `block` 动作。

`compose_text`（Pages 名称：“文本组合器”）则是策略局部的文本准备元件。它的“生成文本（`template`）”可以拼接当前 Step 可见的 origin、系统常量和已完成节点的 `${node_id.value}`，再由后续节点通过 `${compose_id.value}` 写入自己的 `inspection_template` 使用。它不是通用模板引擎，不会自动建立 `depend_on`，也不会改写请求或输出。

Step 2 和 Step 4 现在提供“默认命中动作”“默认错误动作”和“阻断提示”。通用信号元件保留 `action_on_hit: default` 时，会回退到本 Step 的默认命中动作；执行错误保留 `action_on_error: default` 时，同样回退到本 Step 的默认错误动作。默认值为 `observe` / `discard`，因此不会改变已有路由或提示词强化策略。

Step 5 的默认命中动作也支持 `observe`、`block` 与 `retry_generation`。这使新输出策略可以先统一观察所有保持 `default` 的节点，再逐步改为阻断或有界重试。`retry_generation` 只在 Step 5 可选；策略图的 Step 1 至 Step 4 已隐藏该无效选项。关键词与正则规则始终在 payload 中提供 `sanitized`：它按规则的“净化替换文本”替换全部命中区间（留空则移除），只有策略显式引用 `${规则名.sanitized}` 作为输出重定向时才会影响后续内容。

## 安装

### 插件市场

审核通过后，可在 AstrBot 插件市场搜索 `LLM Guardrail` 安装。

### 手动安装

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail.git
```

重启 AstrBot 后，在插件管理页打开 **LLM Guardrail**。本插件要求 AstrBot `>=4.26.0,<5`。

## 官方示例策略

仓库中的 [`presets/`](https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail/tree/main/presets/) 提供可导入的策略包、示例知识库和配套说明。它们用于学习、测试和二次配置，**不包含在插件市场或 GitHub Release 的分发 ZIP 中**；请从项目仓库获取，并先阅读各 preset 的 README。

首个完整示例见 [`presets/preset1/`](https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail/tree/main/presets/preset1/)。其中的 RAG 语料需要由使用者自行导入 AstrBot 知识库，策略包不会自动上传文件、创建知识库或填入 Provider 配置。

## 快速试用

1. 保持默认策略并先开启调试日志，确认 `/guardrail` 能显示当前 UMO 和各 Rail 状态。
2. 在 Pages 的“规则库”创建或查看规则，在“策略编排”中绑定到目标 Rail。
3. 新建策略时，先使用 `observe` 观察命中和误报；确认后再为需要的节点启用 `block`。关键词和正则规则的 `${规则名.sanitized}` 可作为后续节点或显式输出重定向的输入。
4. 如需输出重试，只在 `output_rail` 的规则或阶段默认动作中选择 `retry_generation`，并设置较小的 `max_retries`。
5. 使用“策略包”先导出备份；导入外部策略包时，先查看预览，再选择 `copy` 或 `replace`。

> 需要为 RAG/LLM 复核选择可用的辅助 Provider。输出重试不会借用默认或备用 Provider，而是只复用该轮主请求实际选中的 Provider。

## 使用边界

- 流式输出 chunk 当前跳过 Step 5 的输出重定向与重试；只支持非流式、纯文本的输出重试。
- 重试不会重新进入完整 AstrBot hook 链，也不会重跑 Step 1 至 Step 4；它不会切换模型或使用备用 Provider。
- `${node_id.field}` 是同策略、同次执行内的非阻塞数据引用。需要等候来源结果时，请显式配置 `depend_on`（通常使用 `?source`）。
- 终止性 `block` 优先于输出重定向和 `retry_generation`。多轮升级判断、备用 Provider、流式检测、通用 `payload_schema` 与自定义检测器均未默认启用。

## 配置与管理

主要配置入口是插件 Pages：

| 页面 | 用途 |
| --- | --- |
| 总览 | 查看当前配置、策略和诊断摘要。 |
| 规则库 | 管理可复用规则和系统常量。 |
| 策略编排 | 维护 Rail、规则绑定、局部检测元件、逻辑依赖和动作。 |
| 访问控制 | 查看和维护自动/手动封禁与赦免状态。 |
| 知识库经验 | 查看、编辑或删除 RAG 命中经验记录。 |
| 会话策略监控 | 查看每个 UMO 的最近策略执行与路由观察。 |

管理员可在目标会话发送 `/guardrail` 查看版本、当前 UMO、Rail 状态和规则数量。

## 试用反馈

提交 Issue 时，请尽量提供：

- AstrBot 版本、平台适配器和 Provider 类型；
- 使用的策略包（移除密钥、原始对话和敏感内容后）；
- 预期行为与实际行为；
- 开启调试日志后的脱敏摘要；
- 是否为流式输出，以及是否涉及 `retry_generation`、并发检查或策略包导入。

请勿提交密钥、完整私聊记录、原始高风险提示词或模型原始回复。

## 路线图

后续工作按以下优先级推进：

1. **自定义检测器**：定义安全、可验证的扩展契约，让项目可以在不修改核心调度链路的前提下接入领域检测能力。
2. **通用策略数据面**：扩展编码与外部资源语法，并在已交付的受限 `compose_text` 之外引入通用 `payload_schema`，让检查器间能够传递受约束的结构化结果。
3. **执行治理与可追溯性**：增加 Token／预算控制、规则级并行和完整审计，明确每次策略执行的资源消耗、并发行为与决策依据。

这些能力会先经过独立设计、回归测试和观察模式验证，再作为显式配置交付；不会通过隐藏开关或 system fallback 自动启用。

## 贡献与反馈

欢迎通过 [GitHub Issues](https://github.com/coocoodaegap/astrbot_plugin_llm_guardrail/issues) 提交问题、复现和改进建议。若插件对你有帮助，也欢迎点个 Star 支持项目。
