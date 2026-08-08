# astrbot_plugin_llm_guardrail

LLM Guardrail Orchestrator for AstrBot.

当前版本是配置评审用空壳：

- 插件可以加载。
- 面板可以展示 `_conf_schema.json`。
- `/guardrail` 可以查看占位状态。
- LLM 请求和响应钩子只记录 debug 日志，不执行真实拦截。

后续实现将围绕四段 rail 展开：

- Input Rail：输入分析与反注入。
- Prompt Rail：提示词加固。
- Routing Rail：模型路由。
- Output Rail：输出分析、重试和兜底。

详细设计见：

- `../guardrail_references/llm_guardrail_spec.md`
