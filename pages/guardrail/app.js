const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);
const status = $("status"),
  summary = $("snapshot-summary"),
  rails = $("rails"),
  diagnostics = $("diagnostics"),
  systemSettings = $("system-settings"),
  systemSettingsStatus = $("system-settings-status"),
  saveSystemSettings = $("save-system-settings"),
  ruleList = $("rule-list"),
  ruleCount = $("rule-count"),
  ruleStatus = $("rule-library-status"),
  ruleEditor = $("rule-editor"),
  ruleEmptyState = $("rule-empty-state"),
  saveRuleLibrary = $("save-rule-library"),
  newRule = $("new-rule"),
  deleteRule = $("delete-rule"),
  ruleId = $("rule-id"),
  ruleDescription = $("rule-description"),
  ruleTemplate = $("rule-template"),
  rulePriority = $("rule-priority"),
  ruleActionHit = $("rule-action-hit"),
  ruleActionError = $("rule-action-error"),
  ruleTemplateConfig = $("rule-template-config");
const systemSettingHintOverrides = {
  default_action_on_hit: "规则命中风险时采用的默认处理方式。",
  default_action_on_error: "规则执行出错时采用的默认处理方式。",
  group_chat_mode: "决定哪些群聊会进入 Guardrail 流程。",
  private_chat_mode: "决定哪些私聊会进入 Guardrail 流程。",
};
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
const ruleActionDescriptions = {
  default: "使用系统默认动作（default）",
  observe: "仅记录命中，不改变请求或输出（observe）",
  block: "阻断本轮请求或输出（block）",
  sanitize: "净化命中内容后继续（sanitize）",
  block_input: "阻断用户输入（block_input）",
  sanitize_input: "净化用户输入后继续（sanitize_input）",
  block_output: "阻断模型输出（block_output）",
  sanitize_output: "净化模型输出后继续（sanitize_output）",
  retry_generation: "请求模型重新生成输出（retry_generation）",
  discard: "丢弃本次规则结果（discard）",
  record: "记录可被依赖的错误结果（record）",
};
const systemOptionDescriptions = {
  default_action_on_hit: {
    observe: "仅记录命中结果（observe）",
    block: "阻断本轮请求或输出（block）",
  },
  default_action_on_error: {
    discard: "丢弃本次规则结果，仅记录 warning（discard）",
    record: "记录可被依赖的错误结果（record）",
    block: "错误时阻断本轮请求或输出（block）",
  },
  group_chat_mode: {
    all_run: "所有群聊进入 Guardrail（all_run）",
    all_pass: "所有群聊跳过 Guardrail 并放行（all_pass）",
    all_block: "所有群聊跳过 Guardrail 并拦截（all_block）",
    enabled_or_pass: "仅指定群聊进入，其他放行（enabled_or_pass）",
    enabled_or_block: "仅指定群聊进入，其他拦截（enabled_or_block）",
  },
  private_chat_mode: {
    all_run: "所有群聊进入 Guardrail（all_run）",
    all_pass: "所有群聊跳过 Guardrail 并放行（all_pass）",
    all_block: "所有群聊跳过 Guardrail 并拦截（all_block）",
    enabled_or_pass: "仅指定群聊进入，其他放行（enabled_or_pass）",
    enabled_or_block: "仅指定群聊进入，其他拦截（enabled_or_block）",
  },
};
let currentRevision = null,
  ruleLibrary = { rules: [] },
  selectedRuleId = null,
  systemSettingsSchema = {},
  registeredProviders = [];
function populateOptions(select, values) {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  }
}
function populateRuleActionOptions(select, values) {
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = ruleActionDescriptions[value] || value;
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
populateRuleActionOptions(ruleActionHit, hitActions);
populateRuleActionOptions(ruleActionError, errorActions);
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
function createUmoTagEditor(value) {
  const editor = document.createElement("div");
  editor.className = "umo-tag-editor";
  editor.umoValues = Array.isArray(value) ? [...new Set(value)] : [];
  const tags = document.createElement("div");
  tags.className = "umo-tag-list";
  const controls = document.createElement("div");
  controls.className = "umo-tag-controls";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "输入 UMO 后按回车，可粘贴多行";
  input.setAttribute("aria-label", "添加 UMO");
  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "button-secondary umo-add-button";
  addButton.textContent = "添加";
  const renderTags = () => {
    tags.replaceChildren();
    for (const umo of editor.umoValues) {
      const tag = document.createElement("span");
      tag.className = "umo-tag";
      const label = document.createElement("span");
      label.textContent = umo;
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "umo-remove-button";
      removeButton.setAttribute("aria-label", `移除 ${umo}`);
      removeButton.textContent = "×";
      removeButton.addEventListener("click", () => {
        editor.umoValues = editor.umoValues.filter((item) => item !== umo);
        renderTags();
      });
      tag.append(label, removeButton);
      tags.append(tag);
    }
  };
  const addUmos = () => {
    const values = input.value
      .split(/[\n,]/)
      .map((item) => item.trim())
      .filter(Boolean);
    editor.umoValues = [...new Set([...editor.umoValues, ...values])];
    input.value = "";
    renderTags();
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addUmos();
    }
  });
  addButton.addEventListener("click", addUmos);
  controls.append(input, addButton);
  editor.append(tags, controls);
  renderTags();
  return editor;
}
function createProviderSelector(value) {
  const editor = document.createElement("div");
  editor.className = "provider-selector";
  const select = document.createElement("select");
  const automaticOption = document.createElement("option");
  automaticOption.value = "";
  automaticOption.textContent = "跟随当前会话 Provider（默认）";
  select.append(automaticOption);
  for (const provider of registeredProviders) {
    const option = document.createElement("option");
    option.value = provider.id;
    option.textContent =
      provider.name === provider.id
        ? provider.id
        : `${provider.name}（${provider.id}）`;
    select.append(option);
  }
  const manualOption = document.createElement("option");
  manualOption.value = "__llm_guardrail_manual_provider__";
  manualOption.textContent = "手动填写…";
  select.append(manualOption);
  const manualInput = document.createElement("input");
  manualInput.type = "text";
  manualInput.placeholder = "输入 Provider ID";
  manualInput.setAttribute("aria-label", "手动填写 Provider ID");
  const selectedProvider = String(value ?? "").trim();
  const isRegistered = registeredProviders.some(
    (provider) => provider.id === selectedProvider,
  );
  select.value = selectedProvider && !isRegistered
    ? manualOption.value
    : selectedProvider;
  manualInput.value = selectedProvider && !isRegistered ? selectedProvider : "";
  const syncManualInput = () => {
    manualInput.hidden = select.value !== manualOption.value;
  };
  select.addEventListener("change", syncManualInput);
  editor.providerValue = () =>
    select.value === manualOption.value ? manualInput.value.trim() : select.value;
  editor.append(select, manualInput);
  syncManualInput();
  return editor;
}
function describeSystemSettingOption(fieldKey, value) {
  const description = systemOptionDescriptions[fieldKey]?.[value];
  return description || value;
}
function describeSystemSettingHint(fieldKey, fallback) {
  return systemSettingHintOverrides[fieldKey] || fallback;
}
function createSystemSettingControl(groupKey, fieldKey, field, value) {
  if (field.type === "bool") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "setting-checkbox";
    input.checked = Boolean(value);
    return input;
  }
  if (field.type === "list" && groupKey === "session_control") {
    return createUmoTagEditor(value);
  }
  if (field._special === "select_provider") {
    return createProviderSelector(value);
  }
  if (field.type === "list") {
    const textarea = document.createElement("textarea");
    textarea.className = "list-value";
    textarea.value = Array.isArray(value) ? value.join("\n") : "";
    textarea.placeholder = "（空列表）";
    return textarea;
  }
  if (Array.isArray(field.options)) {
    const select = document.createElement("select");
    for (const optionValue of field.options) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = describeSystemSettingOption(fieldKey, optionValue);
      select.append(option);
    }
    ensureOption(select, String(value ?? ""));
    select.value = String(value ?? "");
    return select;
  }
  const input = document.createElement("input");
  input.type = field.type === "int" ? "number" : "text";
  input.value = String(value ?? "");
  return input;
}
function renderSystemSettings(payload) {
  systemSettings.replaceChildren();
  systemSettingsSchema = payload.schema || {};
  registeredProviders = Array.isArray(payload.providers)
    ? payload.providers.filter(
        (provider) =>
          provider &&
          typeof provider.id === "string" &&
          typeof provider.name === "string",
      )
    : [];
  for (const [groupKey, groupSchema] of Object.entries(payload.schema || {})) {
    const group = document.createElement("section");
    group.className = "card setting-group";
    const header = document.createElement("header");
    const title = document.createElement("h3");
    const description = document.createElement("p");
    title.textContent = groupSchema.description || groupKey;
    description.textContent = groupSchema.hint || "";
    header.append(title, description);
    const grid = document.createElement("div");
    grid.className = "setting-grid";
    for (const [fieldKey, field] of Object.entries(groupSchema.items || {})) {
      const row = document.createElement("div");
      row.className = "setting-row";
      if (field.invisible) row.classList.add("is-hidden-in-schema");
      const meta = document.createElement("div");
      meta.className = "setting-meta";
      const fieldTitle = document.createElement("strong");
      fieldTitle.textContent = field.description || fieldKey;
      const key = document.createElement("code");
      key.className = "setting-key";
      key.textContent = fieldKey;
      meta.append(fieldTitle, key);
      if (field.invisible) {
        const badge = document.createElement("span");
        badge.className = "schema-badge";
        badge.textContent = "配置表隐藏项";
        meta.append(badge);
      }
      const hint = document.createElement("p");
      hint.className = "setting-hint";
      hint.textContent = describeSystemSettingHint(fieldKey, field.hint || "");
      const control = createSystemSettingControl(
        groupKey,
        fieldKey,
        field,
        payload.settings?.[groupKey]?.[fieldKey],
      );
      control.dataset.systemSettingGroup = groupKey;
      control.dataset.systemSettingKey = fieldKey;
      row.append(
        meta,
        hint,
        control,
      );
      grid.append(row);
    }
    group.append(header, grid);
    systemSettings.append(group);
  }
}
function collectSystemSettings() {
  const settings = {};
  for (const [groupKey, groupSchema] of Object.entries(systemSettingsSchema)) {
    const groupSettings = {};
    for (const [fieldKey, field] of Object.entries(groupSchema.items || {})) {
      const selector = `[data-system-setting-group="${groupKey}"][data-system-setting-key="${fieldKey}"]`;
      const control = systemSettings.querySelector(selector);
      if (!control) throw new Error(`缺少系统设置字段：${groupKey}.${fieldKey}`);
      if (field.type === "bool") {
        groupSettings[fieldKey] = control.checked;
      } else if (typeof control.providerValue === "function") {
        groupSettings[fieldKey] = control.providerValue();
      } else if (field.type === "list") {
        groupSettings[fieldKey] = Array.isArray(control.umoValues)
          ? [...control.umoValues]
          : control.value
              .split("\n")
              .map((item) => item.trim())
              .filter(Boolean);
      } else if (field.type === "int") {
        const value = Number(control.value);
        if (!Number.isInteger(value)) {
          throw new Error(`${field.description || fieldKey} 必须是整数。`);
        }
        groupSettings[fieldKey] = value;
      } else {
        groupSettings[fieldKey] = control.value;
      }
    }
    settings[groupKey] = groupSettings;
  }
  return settings;
}
function ruleSummary(rule) {
  return String(rule.description || "").trim() || "未说明";
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
  ruleDescription.value = rule.description || "";
  ensureOption(ruleTemplate, rule.template_key);
  ensureOption(ruleActionHit, rule.default_action_on_hit);
  ensureOption(ruleActionError, rule.default_action_on_error);
  ruleTemplate.value = rule.template_key || templates[0];
  ruleTemplate.disabled = true;
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
  rule.description = ruleDescription.value.trim();
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
    description: "",
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
  const [overviewResult, diagnosticsResult, ruleResult, systemSettingsResult] =
    await Promise.all([
    bridge.apiGet("get_overview"),
    bridge.apiGet("get_diagnostics"),
    bridge.apiGet("get_rule_library"),
    bridge.apiGet("get_system_settings"),
  ]);
  currentRevision = overviewResult.overview.revision;
  renderOverview(overviewResult.overview);
  renderDiagnostics(diagnosticsResult.diagnostics || []);
  renderSystemSettings(systemSettingsResult);
  systemSettingsStatus.textContent = `已加载系统设置 revision ${systemSettingsResult.revision}。`;
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
saveSystemSettings.addEventListener("click", async () => {
  if (!Number.isInteger(currentRevision)) {
    systemSettingsStatus.textContent = "尚未加载当前配置，无法保存。";
    return;
  }
  let settings;
  try {
    settings = collectSystemSettings();
  } catch (error) {
    systemSettingsStatus.textContent = `无法保存：${error instanceof Error ? error.message : String(error)}`;
    return;
  }
  saveSystemSettings.disabled = true;
  try {
    const result = await bridge.apiPost("save_system_settings", {
      expected_revision: currentRevision,
      settings,
    });
    if (!result.success) {
      systemSettingsStatus.textContent = result.detail || result.error || "保存失败。";
      return;
    }
    systemSettingsStatus.textContent = `系统设置已发布为 revision ${result.revision}。`;
    await refresh();
  } catch (error) {
    systemSettingsStatus.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    saveSystemSettings.disabled = false;
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
