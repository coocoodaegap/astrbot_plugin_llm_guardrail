const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);
const status = $("status"),
  summary = $("snapshot-summary"),
  rails = $("rails"),
  diagnostics = $("diagnostics"),
  ruleList = $("rule-list"),
  ruleCount = $("rule-count"),
  ruleStatus = $("rule-library-status"),
  ruleEditor = $("rule-editor"),
  ruleEmptyState = $("rule-empty-state"),
  saveRuleLibrary = $("save-rule-library"),
  newRule = $("new-rule"),
  deleteRule = $("delete-rule"),
  ruleId = $("rule-id"),
  ruleTemplate = $("rule-template"),
  rulePriority = $("rule-priority"),
  ruleActionHit = $("rule-action-hit"),
  ruleActionError = $("rule-action-error"),
  ruleTemplateConfig = $("rule-template-config");
const templates = [
    "plain_keywords",
    "regex_pattern",
    "logic_gate",
    "rag_judge",
    "llm_review",
    "replace_input",
    "strengthen_prompt",
    "route_policy",
  ],
  hitActions = [
    "default",
    "observe",
    "block",
    "sanitize",
    "block_input",
    "sanitize_input",
    "block_output",
    "sanitize_output",
    "retry_generation",
  ],
  errorActions = ["default", "discard", "record", "block"];
let currentRevision = null,
  ruleLibrary = { rules: [] },
  selectedRuleId = null;
function populateOptions(select, values) {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}
function ensureOption(select, value) {
  if (
    value &&
    !Array.from(select.options).some((option) => option.value === value)
  ) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${value}（保留值）`;
    select.append(option);
  }
}
populateOptions(ruleTemplate, templates);
populateOptions(ruleActionHit, hitActions);
populateOptions(ruleActionError, errorActions);
function switchTab(name) {
  document.querySelectorAll("[data-tab]").forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
}
document
  .querySelectorAll("[data-tab]")
  .forEach((tab) =>
    tab.addEventListener("click", () => switchTab(tab.dataset.tab)),
  );
function addSummary(label, value) {
  const term = document.createElement("dt"),
    detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = String(value);
  summary.append(term, detail);
}
function renderOverview(overview) {
  summary.replaceChildren();
  addSummary("Revision", overview.revision);
  addSummary("Schema", overview.schema_version);
  addSummary("Warnings", overview.warning_count);
  addSummary("Active policy", overview.active_policy_id);
  addSummary(
    "Graph",
    `${overview.graph.node_count} rules / ${overview.graph.edge_count} edges`,
  );
  rails.replaceChildren();
  for (const [name, rail] of Object.entries(overview.rails)) {
    const item = document.createElement("article"),
      title = document.createElement("strong"),
      state = document.createElement("span"),
      count = document.createElement("small");
    item.className = "rail";
    title.textContent = name;
    state.textContent = rail.enabled ? "enabled" : "disabled";
    count.textContent = `${rail.enabled_rules}/${rail.total_rules} valid rules`;
    item.append(title, state, count);
    rails.append(item);
  }
}
function renderDiagnostics(items) {
  diagnostics.replaceChildren();
  for (const message of items.length ? items : ["未发现配置诊断。"]) {
    const item = document.createElement("li");
    item.textContent = message;
    diagnostics.append(item);
  }
}
function ruleSummary(rule) {
  const config = rule.template_config || {};
  if (Array.isArray(config.keywords))
    return `${config.keywords.length} 个关键词`;
  if (typeof config.pattern === "string")
    return config.pattern.slice(0, 48) || "未配置正则";
  if (typeof config.prompt === "string") return "已配置审查提示";
  return "模板参数待配置";
}
function selectedRule() {
  return (
    ruleLibrary.rules.find((rule) => rule.rule_id === selectedRuleId) || null
  );
}
function renderRuleEditor() {
  const rule = selectedRule(),
    hasRule = Boolean(rule);
  ruleEditor.hidden = !hasRule;
  ruleEmptyState.hidden = hasRule;
  if (!rule) return;
  $("rule-editor-title").textContent = `编辑：${rule.rule_id}`;
  ruleId.value = rule.rule_id;
  ensureOption(ruleTemplate, rule.template_key);
  ensureOption(ruleActionHit, rule.default_action_on_hit);
  ensureOption(ruleActionError, rule.default_action_on_error);
  ruleTemplate.value = rule.template_key || templates[0];
  rulePriority.value = String(
    Number.isInteger(rule.default_priority) ? rule.default_priority : 100,
  );
  ruleActionHit.value = rule.default_action_on_hit || "default";
  ruleActionError.value = rule.default_action_on_error || "default";
  ruleTemplateConfig.value = JSON.stringify(
    rule.template_config || {},
    null,
    2,
  );
}
function renderRuleList() {
  ruleList.replaceChildren();
  ruleCount.textContent = String(ruleLibrary.rules.length);
  for (const rule of ruleLibrary.rules) {
    const item = document.createElement("button"),
      title = document.createElement("strong"),
      summaryText = document.createElement("small"),
      chip = document.createElement("span");
    item.type = "button";
    item.className = "rule-card";
    item.classList.toggle("is-selected", rule.rule_id === selectedRuleId);
    title.textContent = rule.rule_id || "未命名规则";
    summaryText.textContent = ruleSummary(rule);
    chip.className = "template-chip";
    chip.textContent = rule.template_key || "未选择模板";
    item.append(title, summaryText, chip);
    item.addEventListener("click", () => {
      selectedRuleId = rule.rule_id;
      renderRuleList();
      renderRuleEditor();
    });
    ruleList.append(item);
  }
  renderRuleEditor();
}
function syncSelectedRule() {
  const rule = selectedRule();
  if (!rule) return true;
  let templateConfig;
  try {
    templateConfig = JSON.parse(ruleTemplateConfig.value);
  } catch (error) {
    ruleStatus.textContent = `模板参数 JSON 格式错误：${error instanceof Error ? error.message : String(error)}`;
    return false;
  }
  if (
    !templateConfig ||
    Array.isArray(templateConfig) ||
    typeof templateConfig !== "object"
  ) {
    ruleStatus.textContent = "模板参数必须是 JSON 对象。";
    return false;
  }
  const nextId = ruleId.value.trim();
  if (!/^[a-z][a-z0-9_]{0,63}$/.test(nextId)) {
    ruleStatus.textContent =
      "规则 ID 必须以小写字母开头，并只包含小写字母、数字和下划线。";
    return false;
  }
  if (
    nextId !== rule.rule_id &&
    ruleLibrary.rules.some((item) => item.rule_id === nextId)
  ) {
    ruleStatus.textContent = "规则 ID 已存在。";
    return false;
  }
  const priority = Number.parseInt(rulePriority.value, 10);
  rule.rule_id = nextId;
  rule.template_key = ruleTemplate.value;
  rule.default_priority = Number.isNaN(priority) ? 100 : priority;
  rule.default_action_on_hit = ruleActionHit.value;
  rule.default_action_on_error = ruleActionError.value;
  rule.template_config = templateConfig;
  selectedRuleId = nextId;
  return true;
}
function createRule() {
  if (!syncSelectedRule()) return;
  let index = ruleLibrary.rules.length + 1,
    id = `rule_${index}`;
  while (ruleLibrary.rules.some((rule) => rule.rule_id === id)) {
    index += 1;
    id = `rule_${index}`;
  }
  ruleLibrary.rules.push({
    rule_id: id,
    template_key: "plain_keywords",
    template_config: { keywords: [] },
    default_priority: 100,
    default_action_on_hit: "default",
    default_action_on_error: "default",
  });
  selectedRuleId = id;
  ruleStatus.textContent = "已新建规则，保存后才会发布。";
  renderRuleList();
}
function deleteSelectedRule() {
  const rule = selectedRule();
  if (!rule) return;
  ruleLibrary.rules = ruleLibrary.rules.filter((item) => item !== rule);
  selectedRuleId = ruleLibrary.rules[0]?.rule_id || null;
  ruleStatus.textContent =
    "已从待保存的规则库移除规则。若策略仍绑定此规则，后端会拒绝保存。";
  renderRuleList();
}
async function refresh() {
  const [overviewResult, diagnosticsResult, ruleResult] = await Promise.all([
    bridge.apiGet("get_overview"),
    bridge.apiGet("get_diagnostics"),
    bridge.apiGet("get_rule_library"),
  ]);
  currentRevision = overviewResult.overview.revision;
  renderOverview(overviewResult.overview);
  renderDiagnostics(diagnosticsResult.diagnostics || []);
  ruleLibrary = {
    rules: Array.isArray(ruleResult.rule_library?.rules)
      ? ruleResult.rule_library.rules
      : [],
  };
  if (!ruleLibrary.rules.some((rule) => rule.rule_id === selectedRuleId))
    selectedRuleId = ruleLibrary.rules[0]?.rule_id || null;
  renderRuleList();
  const validation = ruleResult.validation || {
      warnings: [],
      fatal_errors: [],
    },
    messages = [
      ...(validation.fatal_errors || []),
      ...(validation.warnings || []),
    ];
  ruleStatus.textContent = messages.length
    ? `revision ${ruleResult.revision}: ${messages.join("; ")}`
    : `已加载规则库 revision ${ruleResult.revision}。`;
  status.textContent = `已加载配置快照 revision ${currentRevision}`;
}
newRule.addEventListener("click", createRule);
deleteRule.addEventListener("click", deleteSelectedRule);
saveRuleLibrary.addEventListener("click", async () => {
  if (!Number.isInteger(currentRevision) || !syncSelectedRule()) return;
  saveRuleLibrary.disabled = true;
  try {
    const result = await bridge.apiPost("save_rule_library", {
      expected_revision: currentRevision,
      rule_library: ruleLibrary,
    });
    if (!result.success) {
      ruleStatus.textContent = result.detail || result.error || "保存失败。";
      return;
    }
    ruleStatus.textContent = `规则库已发布为 revision ${result.revision}。`;
    await refresh();
  } catch (error) {
    ruleStatus.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    saveRuleLibrary.disabled = false;
  }
});
if (!bridge) {
  status.textContent = "当前不在 AstrBot Pages 环境中，无法读取或保存配置。";
} else {
  try {
    await bridge.ready();
    await refresh();
  } catch (error) {
    status.textContent = `无法读取 Guardrail 状态：${error instanceof Error ? error.message : String(error)}`;
  }
}
