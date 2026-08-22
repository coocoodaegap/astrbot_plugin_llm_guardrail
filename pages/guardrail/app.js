const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);
const status = $("status"),
  summary = $("snapshot-summary"),
  diagnostics = $("diagnostics"),
  systemSettings = $("system-settings"),
  systemSettingsStatus = $("system-settings-status"),
  saveSystemSettings = $("save-system-settings"),
  ruleList = $("rule-list"),
  ruleCount = $("rule-count"),
  ruleStatus = $("rule-library-status"),
  policyListPanel = $("policy-list-panel"),
  policyDetailPanel = $("policy-detail-panel"),
  policyList = $("policy-list"),
  policyCount = $("policy-count"),
  policyLibraryStatus = $("policy-library-status"),
  policyDetailName = $("policy-detail-name"),
  policyDetailDescription = $("policy-detail-description"),
  policyDetailMeta = $("policy-detail-meta"),
  policyNameInput = $("policy-name-input"),
  policyDescriptionInput = $("policy-description-input"),
  policyBasicStatus = $("policy-basic-status"),
  policyGraphStepToggles = $("policy-graph-step-toggles"),
  policyGraphStage = $("policy-graph-stage"),
  policyGraphCanvas = $("policy-graph-canvas"),
  policyGraphStatus = $("policy-graph-status"),
  savePolicy = $("save-policy"),
  policyStepSettings = $("policy-step-settings"),
  policyStepSettingsStatus = $("policy-step-settings-status"),
  policyUmoList = $("policy-umo-list"),
  setDefaultPolicy = $("set-default-policy"),
  policySessionStatus = $("policy-session-status"),
  backToPolicyList = $("back-to-policy-list"),
  newPolicy = $("new-policy"),
  savePolicyAs = $("save-policy-as"),
  deletePolicyButton = $("delete-policy"),
  createPolicyDialog = $("create-policy-dialog"),
  newPolicyId = $("new-policy-id"),
  newPolicyName = $("new-policy-name"),
  newPolicyDescription = $("new-policy-description"),
  createPolicyStatus = $("create-policy-status"),
  cancelCreatePolicy = $("cancel-create-policy"),
  confirmCreatePolicy = $("confirm-create-policy"),
  savePolicyAsDialog = $("save-policy-as-dialog"),
  saveAsPolicyId = $("save-as-policy-id"),
  saveAsPolicyName = $("save-as-policy-name"),
  saveAsPolicyDescription = $("save-as-policy-description"),
  saveAsPolicyStatus = $("save-as-policy-status"),
  cancelSavePolicyAs = $("cancel-save-policy-as"),
  confirmSavePolicyAs = $("confirm-save-policy-as"),
  confirmPolicyDeleteDialog = $("confirm-policy-delete-dialog"),
  confirmPolicyDeleteMessage = $("confirm-policy-delete-message"),
  cancelPolicyDelete = $("cancel-policy-delete"),
  confirmPolicyDelete = $("confirm-policy-delete"),
  ruleLibraryPanel = $("rule-library-panel"),
  ruleWorkspace = $("rule-workspace"),
  ruleCreationDialog = $("rule-creation-dialog"),
  templateOptions = $("template-options"),
  ruleEmptyState = $("rule-empty-state"),
  openRuleEditors = $("open-rule-editors"),
  saveRuleAsDialog = $("save-rule-as-dialog"),
  saveAsRuleId = $("save-as-rule-id"),
  saveAsRuleDescription = $("save-as-rule-description"),
  saveAsRuleStatus = $("save-as-rule-status"),
  cancelSaveRuleAs = $("cancel-save-rule-as"),
  confirmSaveRuleAs = $("confirm-save-rule-as"),
  confirmRuleDeleteDialog = $("confirm-rule-delete-dialog"),
  confirmRuleDeleteMessage = $("confirm-rule-delete-message"),
  cancelRuleDelete = $("cancel-rule-delete"),
  confirmRuleDelete = $("confirm-rule-delete"),
  saveRuleLibrary = $("save-rule-library"),
  newRule = $("new-rule"),
  cancelRuleCreation = $("cancel-rule-creation"),
  confirmRuleCreation = $("confirm-rule-creation"),
  newRuleId = $("new-rule-id"),
  newRuleDescription = $("new-rule-description"),
  ruleCreationStatus = $("rule-creation-status");
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
    "retry_generation",
  ],
  errorActions = ["default", "discard", "record", "retry_generation", "block"];
const ruleActionDescriptions = {
  default: "使用系统默认动作（default）",
  observe: "仅记录命中，不改变请求或输出（observe）",
  block: "阻断本轮请求或输出（block）",
  sanitize: "净化命中内容后继续（sanitize）",
  retry_generation: "请求模型重新生成输出（retry_generation）",
  discard: "丢弃本次规则结果（discard）",
  record: "记录可被依赖的错误结果（record）",
};
const templateDescriptions = {
  plain_keywords: "关键词匹配",
  regex_pattern: "正则匹配",
  logic_gate: "逻辑门",
  rag_judge: "知识库裁判",
  llm_review: "LLM 审查",
  replace_input: "替换输入",
  strengthen_prompt: "增强提示词",
  route_policy: "模型路由",
};
const templateCreationDetails = {
  plain_keywords: "按关键词或短语匹配输入、请求或输出内容。",
  regex_pattern: "使用正则表达式匹配结构化或复杂文本模式。",
  logic_gate: "组合其他规则的结果，构建 all / any 等逻辑判断。",
  rag_judge: "以知识库检索结果为证据进行风险裁判。",
  llm_review: "调用旁路 LLM 对内容进行结构化审查。",
  replace_input: "将输入中的指定文本替换为安全内容。",
  strengthen_prompt: "向请求注入额外约束或上下文提示。",
  route_policy: "根据规则命中结果选择目标模型 Provider。",
};
const templateParameterFields = {
  plain_keywords: [
    { key: "keywords", label: "关键词列表", hint: "每行一个关键词或短语。", type: "list", default: [], fullWidth: true },
    { key: "keyword_weights", label: "关键词权值", hint: "每行一项，格式为：关键词:权重。未填写的关键词权重为 1。", type: "list", default: [], fullWidth: true },
    { key: "threshold", label: "命中门槛", hint: "命中关键词的权重总和达到此值时规则命中。", type: "number", default: 1 },
    { key: "sanitizer", label: "净化文本", hint: "仅在选择 sanitize 时使用；留空会移除命中片段。", type: "string" },
  ],
  regex_pattern: [
    { key: "pattern", label: "正则模式", hint: "用于匹配文本的正则表达式；保存后由后端编译校验。", type: "text", fullWidth: true },
    { key: "sanitizer", label: "净化文本", hint: "仅在选择 sanitize 时使用；留空会移除命中片段。", type: "string" },
  ],
  logic_gate: [
    { key: "gate", label: "逻辑关系", hint: "all 表示全部满足；any 表示任一满足。", type: "select", default: "all", options: [["all", "全部满足（all）"], ["any", "任一满足（any）"]] },
    { key: "invert", label: "结果取反", hint: "开启后反转逻辑门的计算结果。", type: "boolean", default: false },
    { key: "inputs", label: "输入规则", hint: "每行一个规则 ID；可用 !rule_id 表示未命中，?rule_id 表示只要求已执行。", type: "list", default: [], fullWidth: true },
  ],
  rag_judge: [
    { key: "knowledge_bases", label: "知识库列表", hint: "每行一个 AstrBot 知识库名称；至少填写一个。", type: "list", default: [], fullWidth: true },
    { key: "top_k", label: "检索数量", hint: "每个知识库最多取回的候选数量。", type: "integer", default: 5 },
    { key: "min_score", label: "最低分数", hint: "存在证据且分数达到此值时判为命中。", type: "number", default: 0.72 },
    { key: "timeout_seconds", label: "超时（秒）", hint: "设为 0 不启用插件侧超时。", type: "number", default: 8 },
  ],
  llm_review: [
    { key: "provider_id", label: "审查 Provider", hint: "留空则跟随当前会话 Provider。", type: "provider", fullWidth: true },
    { key: "timeout_seconds", label: "超时（秒）", hint: "设为 0 不启用插件侧超时。", type: "number", default: 8 },
    { key: "audit_prompt", label: "审查提示词", hint: "描述判断目标与希望记录的 payload；插件会自动要求 JSON 结构化输出。", type: "text", fullWidth: true },
  ],
  replace_input: [
    { key: "replacement_text", label: "替换内容", hint: "将整段用户输入替换为此内容；留空会清空输入。", type: "text", fullWidth: true },
  ],
  strengthen_prompt: [
    { key: "insertion_target", label: "注入位置", hint: "选择要写入系统提示、临时上下文或输入包装的位置。", type: "select", default: "temp_user_context", options: [["system_prefix", "系统提示开头（system_prefix）"], ["system_suffix", "系统提示结尾（system_suffix）"], ["temp_user_context", "临时用户上下文（temp_user_context）"], ["input_wrapper", "包装用户输入（input_wrapper）"]] },
    { key: "insertion_text", label: "加固内容", hint: "写入所选位置的提示词内容。", type: "text", fullWidth: true },
  ],
  route_policy: [
    { key: "provider_id", label: "目标 Provider", hint: "留空表示保持 AstrBot 本轮默认请求模型。", type: "provider", fullWidth: true },
  ],
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
  policyLibrary = { policies: [], active_policy_id: "_default" },
  openRuleIds = [],
  selectedPolicyId = null,
  pendingPolicyDeletionId = null,
  saveAsSourceRuleId = null,
  pendingRuleDeletionId = null,
  selectedNewTemplate = null,
  systemSettingsSchema = {},
  registeredProviders = [],
  policyGraphState = {
    model: null,
    layout: null,
    collapsedRails: new Set(),
    selectedNodeId: null,
    renderFrame: 0,
    animationFrame: 0,
  };
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
function switchTab(name) {
  document.querySelectorAll("[data-tab]").forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
  updatePolicyGraphAnimation();
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
    item.classList.toggle("is-selected", openRuleIds.includes(rule.rule_id));
    title.textContent = rule.rule_id || "未命名规则";
    summaryText.textContent = ruleSummary(rule);
    chip.className = "template-chip";
    chip.textContent =
      templateDescriptions[rule.template_key] || rule.template_key || "未选择模板";
    item.append(title, summaryText, chip);
    item.addEventListener("click", () => {
      openRule(rule.rule_id);
      renderRuleList();
    });
    ruleList.append(item);
  }
}
const railLabels = {
  input_rail: "Step 1 · 输入分析",
  routing_rail: "Step 2 · 模型路由",
  request_rail: "Step 3 · 请求检查",
  prompt_rail: "Step 4 · 提示词加工",
  output_rail: "Step 5 · 输出检查",
};
function showPolicyList() {
  policyDetailPanel.hidden = true;
  policyListPanel.hidden = false;
  selectedPolicyId = null;
  renderPolicyList();
  updatePolicyGraphAnimation();
}
function showPolicyDetail(policyId) {
  const policy = policyLibrary.policies.find((item) => item.policy_id === policyId);
  if (!policy) return;
  selectedPolicyId = policyId;
  policyListPanel.hidden = true;
  policyDetailPanel.hidden = false;
  renderPolicyDetail(policy);
}
function customPolicies() {
  return policyLibrary.policies.filter((policy) => policy.policy_id !== "_default");
}
function renderPolicyList() {
  policyList.replaceChildren();
  const policies = customPolicies();
  policyCount.textContent = String(policies.length);
  for (const policy of policies) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "policy-list-item";
    const title = document.createElement("strong");
    const description = document.createElement("small");
    const metadata = document.createElement("span");
    title.textContent = policy.name || policy.policy_id || "未命名策略";
    description.textContent = String(policy.description || "").trim() || "未说明";
    const bindingCount = Array.isArray(policy.bindings) ? policy.bindings.length : 0;
    const umoCount = Array.isArray(policy.umo_list) ? policy.umo_list.length : 0;
    metadata.textContent = `${bindingCount} 条规则绑定 · ${umoCount} 个 UMO${policy.policy_id === policyLibrary.active_policy_id ? " · 默认策略" : ""}`;
    item.append(title, description, metadata);
    item.addEventListener("click", () => showPolicyDetail(policy.policy_id));
    policyList.append(item);
  }
}
const policyStepDefinitions = [
  { rail: "input_rail", title: "Step 1 · 输入分析", fields: [
    ["enabled", "启用 Step 1", "boolean"], ["max_text_chars", "最大检查字符数", "number"],
    ["default_llm_provider", "默认辅助 Provider", "provider"], ["default_action_on_hit", "默认命中动作", "select", ["observe", "block"]],
    ["default_action_on_error", "默认错误动作", "select", ["discard", "record", "block"]], ["block_message", "默认阻断提示", "text"],
  ] },
  { rail: "routing_rail", title: "Step 2 · 模型路由", fields: [["enabled", "启用 Step 2", "boolean"]] },
  { rail: "request_rail", title: "Step 3 · 请求审查", fields: [
    ["enabled", "启用 Step 3", "boolean"], ["max_text_chars", "最大检查字符数", "number"],
    ["default_llm_provider", "默认辅助 Provider", "provider"], ["default_action_on_hit", "默认命中动作", "select", ["observe", "block"]],
    ["default_action_on_error", "默认错误动作", "select", ["discard", "record", "block"]], ["block_message", "默认阻断提示", "text"],
  ] },
  { rail: "prompt_rail", title: "Step 4 · 提示词强化", fields: [["enabled", "启用 Step 4", "boolean"]] },
  { rail: "output_rail", title: "Step 5 · 输出检查", fields: [
    ["enabled", "启用 Step 5", "boolean"], ["max_text_chars", "最大检查字符数", "number"],
    ["default_llm_provider", "默认辅助 Provider", "provider"], ["max_retries", "最大重试次数", "number"],
    ["default_action_on_hit", "默认命中动作", "select", ["block"]], ["default_action_on_error", "默认错误动作", "select", ["discard", "record", "block"]],
    ["block_message", "默认阻断提示", "text"],
  ] },
];
const policyGraphSteps = [
  { rail: "input_rail", step: 1, label: "Step 1 · 输入分析", color: "#ff5a78", fill: "#401d31" },
  { rail: "routing_rail", step: 2, label: "Step 2 · 模型路由", color: "#ff963f", fill: "#41291c" },
  { rail: "request_rail", step: 3, label: "Step 3 · 请求审查", color: "#eadb41", fill: "#3c3819" },
  { rail: "prompt_rail", step: 4, label: "Step 4 · 提示词增强", color: "#4ee19a", fill: "#17372b" },
  { rail: "output_rail", step: 5, label: "Step 5 · 输出检查", color: "#56b9ff", fill: "#17334a" },
];
const policyGraphStepByRail = new Map(
  policyGraphSteps.map((item) => [item.rail, item]),
);
function parsePolicyGraphReference(value) {
  const raw = String(value || "").trim();
  if (!raw) return { raw, targetId: "", mode: "none" };
  if (raw.startsWith("!")) return { raw, targetId: raw.slice(1).trim(), mode: "not_matched" };
  if (raw.startsWith("?")) return { raw, targetId: raw.slice(1).trim(), mode: "executed" };
  return { raw, targetId: raw, mode: "matched" };
}
function graphRuleInputs(rule) {
  const inputs = rule?.template_config?.inputs;
  return Array.isArray(inputs)
    ? inputs.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}
function graphPriority(binding, rule) {
  const value = binding?.priority;
  if (Number.isFinite(Number(value))) return Number(value);
  return Number.isFinite(Number(rule?.default_priority)) ? Number(rule.default_priority) : 100;
}
function buildPolicyGraphModel(policy) {
  const ruleById = new Map(
    (Array.isArray(ruleLibrary.rules) ? ruleLibrary.rules : []).map((rule) => [rule.rule_id, rule]),
  );
  const nodes = [];
  const nodeById = new Map();
  for (const binding of Array.isArray(policy?.bindings) ? policy.bindings : []) {
    const rule = ruleById.get(binding.rule_id) || null;
    const theme = policyGraphStepByRail.get(binding.rail);
    const node = {
      id: String(binding.rule_id || ""),
      binding,
      rule,
      rail: binding.rail,
      step: theme?.step || 0,
      theme,
      priority: graphPriority(binding, rule),
      enabled: binding.enabled !== false,
      isLogicGate: rule?.template_key === "logic_gate",
      issues: [],
      state: "available",
      depth: 0,
      x: 0,
      y: 0,
    };
    if (!rule) node.issues.push({ level: "error", message: "规则库中找不到该规则。" });
    if (!theme) node.issues.push({ level: "error", message: "规则绑定到未知 Step。" });
    nodes.push(node);
    if (node.id && !nodeById.has(node.id)) nodeById.set(node.id, node);
  }
  const edges = [];
  const addEdge = (dependent, rawReference, kind) => {
    const reference = parsePolicyGraphReference(rawReference);
    if (!reference.targetId) {
      dependent.issues.push({ level: "error", message: `${kind === "logic_input" ? "逻辑门输入" : "依赖项"}为空。` });
      return;
    }
    const source = nodeById.get(reference.targetId) || null;
    const edge = {
      id: `${kind}:${reference.raw}:${dependent.id}`,
      sourceId: reference.targetId,
      targetId: dependent.id,
      source,
      target: dependent,
      kind,
      mode: reference.mode,
      invalid: !source,
    };
    if (!source) {
      dependent.issues.push({ level: "error", message: `依赖目标“${reference.targetId}”不在当前策略中。` });
    } else {
      if (!source.enabled) {
        edge.invalid = true;
        dependent.issues.push({ level: "warning", message: `依赖目标“${source.id}”已禁用。` });
      }
      if (source.step > dependent.step) {
        edge.invalid = true;
        dependent.issues.push({ level: "error", message: `不能依赖较晚的 ${source.theme?.label || source.rail}。` });
      }
    }
    edges.push(edge);
  };
  for (const node of nodes) {
    if (node.binding.depend_on) addEdge(node, node.binding.depend_on, "depend_on");
    if (node.isLogicGate) {
      for (const input of graphRuleInputs(node.rule)) addEdge(node, input, "logic_input");
    }
  }
  const incoming = new Map(nodes.map((node) => [node.id, []]));
  for (const edge of edges) {
    if (edge.source && edge.target) incoming.get(edge.target.id)?.push(edge.source.id);
  }
  const visiting = new Set();
  const visited = new Set();
  const cycleNodes = new Set();
  const depthFor = (nodeId) => {
    if (visiting.has(nodeId)) {
      cycleNodes.add(nodeId);
      return 0;
    }
    if (visited.has(nodeId)) return nodeById.get(nodeId)?.depth || 0;
    visiting.add(nodeId);
    let depth = 0;
    for (const sourceId of incoming.get(nodeId) || []) {
      if (visiting.has(sourceId)) cycleNodes.add(sourceId);
      depth = Math.max(depth, depthFor(sourceId) + 1);
    }
    visiting.delete(nodeId);
    visited.add(nodeId);
    const node = nodeById.get(nodeId);
    if (node) node.depth = depth;
    return depth;
  };
  for (const node of nodes) depthFor(node.id);
  for (const node of nodes) {
    if (cycleNodes.has(node.id)) node.issues.push({ level: "error", message: "存在循环依赖。" });
    if (!node.enabled) node.state = "disabled";
    else if (node.issues.some((issue) => issue.level === "error")) node.state = "unavailable";
    else if (node.issues.length) node.state = "warning";
  }
  return { policy, nodes, nodeById, edges };
}
function policyGraphCanvasHeight() {
  return policyGraphSteps.reduce(
    (height, step) => height + (policyGraphState.collapsedRails.has(step.rail) ? 42 : 104),
    0,
  );
}
function renderPolicyGraphStepToggles(model) {
  policyGraphStepToggles.replaceChildren();
  for (const step of policyGraphSteps) {
    const count = model.nodes.filter((node) => node.rail === step.rail).length;
    const collapsed = policyGraphState.collapsedRails.has(step.rail);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "policy-graph-step-toggle";
    button.classList.toggle("is-expanded", !collapsed);
    button.classList.toggle("is-collapsed", collapsed);
    button.setAttribute("aria-pressed", String(!collapsed));
    button.textContent = `${step.label} · ${count}`;
    button.addEventListener("click", () => {
      if (collapsed) policyGraphState.collapsedRails.delete(step.rail);
      else policyGraphState.collapsedRails.add(step.rail);
      renderPolicyGraphStepToggles(model);
      schedulePolicyGraphRender();
    });
    policyGraphStepToggles.append(button);
  }
}
function policyGraphIsVisible() {
  return Boolean(
    policyGraphState.model
      && selectedPolicyId
      && !policyDetailPanel.hidden
      && !$("panel-policies").hidden
      && document.visibilityState !== "hidden",
  );
}
function policyGraphReducedMotion() {
  return Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
}
function schedulePolicyGraphRender() {
  if (policyGraphState.renderFrame) return;
  policyGraphState.renderFrame = requestAnimationFrame((timestamp) => {
    policyGraphState.renderFrame = 0;
    drawPolicyGraph(timestamp);
  });
}
function updatePolicyGraphAnimation() {
  if (policyGraphState.animationFrame) {
    cancelAnimationFrame(policyGraphState.animationFrame);
    policyGraphState.animationFrame = 0;
  }
  if (!policyGraphIsVisible() || policyGraphReducedMotion()) {
    schedulePolicyGraphRender();
    return;
  }
  const animate = (timestamp) => {
    drawPolicyGraph(timestamp);
    if (policyGraphIsVisible() && !policyGraphReducedMotion()) {
      policyGraphState.animationFrame = requestAnimationFrame(animate);
    } else {
      policyGraphState.animationFrame = 0;
    }
  };
  policyGraphState.animationFrame = requestAnimationFrame(animate);
}
function layoutPolicyGraph(model, width, height) {
  const laneLayouts = new Map();
  let top = 0;
  for (const step of policyGraphSteps) {
    const collapsed = policyGraphState.collapsedRails.has(step.rail);
    const laneHeight = collapsed ? 42 : 104;
    laneLayouts.set(step.rail, { step, top, height: laneHeight, collapsed });
    top += laneHeight;
  }
  const left = 92;
  const right = Math.max(left + 90, width - 34);
  for (const step of policyGraphSteps) {
    const lane = laneLayouts.get(step.rail);
    const nodes = model.nodes
      .filter((node) => node.rail === step.rail)
      .sort((leftNode, rightNode) => (
        leftNode.priority - rightNode.priority || leftNode.id.localeCompare(rightNode.id)
      ));
    if (lane.collapsed) continue;
    const depthCounts = new Map();
    for (const node of nodes) depthCounts.set(node.depth, (depthCounts.get(node.depth) || 0) + 1);
    const depthOffsets = new Map();
    nodes.forEach((node, index) => {
      const availableWidth = Math.max(1, right - left);
      node.x = nodes.length === 1 ? left + availableWidth / 2 : left + (availableWidth * index) / (nodes.length - 1);
      const offset = depthOffsets.get(node.depth) || 0;
      depthOffsets.set(node.depth, offset + 1);
      const depthY = lane.top + 38 + node.depth * 25 + offset * 16;
      node.y = Math.min(lane.top + lane.height - 18, depthY);
    });
  }
  return { laneLayouts, width, height };
}
function graphColorForEdge(edge) {
  if (edge.invalid || edge.source?.state === "unavailable" || edge.target?.state === "unavailable") return "#ff6b74";
  if (edge.source?.state === "disabled" || edge.target?.state === "disabled") return "#718096";
  if (edge.kind === "logic_input") return "#e2e8f0";
  return edge.target?.theme?.color || "#cbd5e1";
}
function drawPolicyGraphGrid(context, lane, timestamp, reducedMotion) {
  context.fillStyle = lane.step.fill;
  context.fillRect(0, lane.top, lane.width, lane.height);
  const offset = reducedMotion ? 0 : (timestamp / 7000) % 24;
  context.strokeStyle = `${lane.step.color}35`;
  context.lineWidth = 1;
  for (let x = -24 + offset; x < lane.width; x += 24) {
    context.beginPath();
    context.moveTo(x, lane.top);
    context.lineTo(x, lane.top + lane.height);
    context.stroke();
  }
  for (let y = lane.top + 10; y < lane.top + lane.height; y += 24) {
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(lane.width, y);
    context.stroke();
  }
  context.strokeStyle = `${lane.step.color}aa`;
  context.strokeRect(.5, lane.top + .5, lane.width - 1, lane.height - 1);
  context.fillStyle = lane.step.color;
  context.font = "600 14px Inter, system-ui, sans-serif";
  context.fillText(lane.step.label, 14, lane.top + 22);
}
function drawPolicyGraphArrow(context, source, target, edge) {
  const color = graphColorForEdge(edge);
  context.save();
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = edge.kind === "logic_input" ? 2.2 : 2;
  if (edge.kind === "logic_input") context.setLineDash([3, 4]);
  else if (edge.mode === "not_matched") context.setLineDash([7, 5]);
  else if (edge.mode === "executed") context.setLineDash([2, 5]);
  else context.setLineDash([]);
  const controlX = Math.max(24, Math.abs(target.x - source.x) * .38);
  context.beginPath();
  context.moveTo(source.x, source.y);
  context.bezierCurveTo(source.x + controlX, source.y, target.x - controlX, target.y, target.x, target.y);
  context.stroke();
  const angle = Math.atan2(target.y - source.y, target.x - source.x);
  const size = 6;
  context.setLineDash([]);
  context.beginPath();
  context.moveTo(target.x, target.y);
  context.lineTo(target.x - size * Math.cos(angle - Math.PI / 6), target.y - size * Math.sin(angle - Math.PI / 6));
  context.lineTo(target.x - size * Math.cos(angle + Math.PI / 6), target.y - size * Math.sin(angle + Math.PI / 6));
  context.closePath();
  context.fill();
  context.restore();
}
function graphGlowForNode(node) {
  if (node.state === "disabled") return null;
  if (node.state === "unavailable") return "#ff4d5e";
  if (node.state === "warning") return "#ffbe4d";
  return "#ffffff";
}
function drawPolicyGraphNode(context, node, timestamp, reducedMotion) {
  if (policyGraphState.collapsedRails.has(node.rail)) return;
  const color = node.state === "disabled" ? "#94a3b8" : node.theme?.color || "#e2e8f0";
  const glow = graphGlowForNode(node);
  context.save();
  context.strokeStyle = color;
  context.lineWidth = node.isLogicGate ? 2.6 : 2.2;
  if (glow) {
    context.shadowColor = glow;
    context.shadowBlur = node.state === "available" ? 10 : 13;
  }
  if (node.isLogicGate) {
    const radius = 8;
    context.beginPath();
    context.moveTo(node.x, node.y - radius);
    context.lineTo(node.x + radius, node.y);
    context.lineTo(node.x, node.y + radius);
    context.lineTo(node.x - radius, node.y);
    context.closePath();
    context.stroke();
    context.shadowBlur = 0;
    context.fillStyle = color;
    context.font = "600 9px Inter, system-ui, sans-serif";
    const symbol = node.rule?.template_config?.gate === "any" ? "∨" : "∧";
    context.fillText(symbol, node.x - 3, node.y + 3);
  } else {
    context.beginPath();
    context.arc(node.x, node.y, 7, 0, Math.PI * 2);
    context.stroke();
  }
  if (policyGraphState.selectedNodeId === node.id) {
    const phase = reducedMotion ? 0 : (timestamp / 900) % 1;
    context.shadowBlur = 0;
    context.strokeStyle = "#ffffff";
    context.lineWidth = 1.4;
    context.setLineDash([3, 3]);
    context.lineDashOffset = -phase * 12;
    context.beginPath();
    context.arc(node.x, node.y, 13, 0, Math.PI * 2);
    context.stroke();
  }
  context.shadowBlur = 0;
  context.setLineDash([]);
  context.fillStyle = "#eef6ff";
  context.font = "500 11px Inter, system-ui, sans-serif";
  context.fillText(node.id || "未命名", node.x + 11, node.y + 4);
  context.restore();
}
function drawPolicyGraph(timestamp = performance.now()) {
  const model = policyGraphState.model;
  if (!model || !policyGraphCanvas || !policyGraphIsVisible()) return;
  const canvasHeight = policyGraphCanvasHeight();
  policyGraphCanvas.style.height = `${canvasHeight}px`;
  const rect = policyGraphCanvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const pixelWidth = Math.round(rect.width * dpr);
  const pixelHeight = Math.round(rect.height * dpr);
  if (policyGraphCanvas.width !== pixelWidth || policyGraphCanvas.height !== pixelHeight) {
    policyGraphCanvas.width = pixelWidth;
    policyGraphCanvas.height = pixelHeight;
  }
  const context = policyGraphCanvas.getContext("2d");
  if (!context) return;
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, rect.width, rect.height);
  const layout = layoutPolicyGraph(model, rect.width, rect.height);
  policyGraphState.layout = layout;
  const reducedMotion = policyGraphReducedMotion();
  for (const lane of layout.laneLayouts.values()) {
    lane.width = rect.width;
    drawPolicyGraphGrid(context, lane, timestamp, reducedMotion);
    if (lane.collapsed) {
      const count = model.nodes.filter((node) => node.rail === lane.step.rail).length;
      context.fillStyle = "#d8e7f7";
      context.font = "500 11px Inter, system-ui, sans-serif";
      context.fillText(`${count} 个节点已折叠`, rect.width - 88, lane.top + 22);
    }
  }
  for (const edge of model.edges) {
    if (!edge.source || policyGraphState.collapsedRails.has(edge.source.rail) || policyGraphState.collapsedRails.has(edge.target.rail)) continue;
    drawPolicyGraphArrow(context, edge.source, edge.target, edge);
  }
  for (const node of model.nodes) drawPolicyGraphNode(context, node, timestamp, reducedMotion);
}
function policyGraphNodeAt(clientX, clientY) {
  const rect = policyGraphCanvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  return policyGraphState.model?.nodes.find((node) => (
    !policyGraphState.collapsedRails.has(node.rail)
      && Math.hypot(node.x - x, node.y - y) <= 15
  )) || null;
}
function renderPolicyGraph(policy) {
  policyGraphState.selectedNodeId = null;
  policyGraphState.model = buildPolicyGraphModel(policy);
  renderPolicyGraphStepToggles(policyGraphState.model);
  const issues = policyGraphState.model.nodes.flatMap((node) => node.issues);
  policyGraphStatus.textContent = issues.length
    ? `图中有 ${issues.length} 项需要处理的问题；保存时以后端校验为准。`
    : `共 ${policyGraphState.model.nodes.length} 个节点、${policyGraphState.model.edges.length} 条依赖。`;
  policyGraphCanvas.classList.toggle("is-interactive", policyGraphState.model.nodes.length > 0);
  updatePolicyGraphAnimation();
}
function createPolicyStepControl(type, value, options) {
  if (type === "boolean") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "setting-checkbox";
    input.checked = value !== false;
    return input;
  }
  if (type === "provider") return createProviderSelector(value);
  if (type === "select") {
    const select = document.createElement("select");
    const inherit = document.createElement("option");
    inherit.value = "";
    inherit.textContent = "沿用系统设置";
    select.append(inherit);
    populateRuleActionOptions(select, options || []);
    ensureOption(select, String(value ?? ""));
    select.value = String(value ?? "");
    return select;
  }
  const input = document.createElement("input");
  input.type = type === "number" ? "number" : "text";
  input.value = String(value ?? "");
  input.placeholder = "沿用系统设置";
  return input;
}
function renderPolicyStepSettings(policy) {
  policyStepSettings.replaceChildren();
  const settings = policy.rail_settings || {};
  for (const definition of policyStepDefinitions) {
    const card = document.createElement("section");
    card.className = "policy-step-card";
    const title = document.createElement("h4");
    title.textContent = definition.title;
    const grid = document.createElement("div");
    grid.className = "form-grid";
    const railSettings = settings[definition.rail] || {};
    for (const [key, labelText, type, options] of definition.fields) {
      const label = document.createElement("label");
      label.textContent = labelText;
      const control = createPolicyStepControl(type, railSettings[key], options);
      control.dataset.policyRail = definition.rail;
      control.dataset.policyRailSetting = key;
      control.dataset.policyRailSettingType = type;
      label.append(control);
      grid.append(label);
    }
    const bindingsLabel = document.createElement("label");
    bindingsLabel.className = "full-width";
    bindingsLabel.textContent = "规则绑定（JSON）";
    const bindingsJson = document.createElement("textarea");
    bindingsJson.className = "json-editor policy-step-bindings-json";
    bindingsJson.spellcheck = false;
    bindingsJson.dataset.policyBindingsRail = definition.rail;
    bindingsJson.setAttribute("aria-label", `${definition.title} 的规则绑定 JSON`);
    bindingsJson.value = JSON.stringify(
      (policy.bindings || []).filter((binding) => binding.rail === definition.rail),
      null,
      2,
    );
    bindingsLabel.append(bindingsJson);
    card.append(title, grid, bindingsLabel);
    policyStepSettings.append(card);
  }
  policyStepSettingsStatus.textContent = "";
}
function collectPolicyStepSettings(policy) {
  const settings = structuredClone(policy.rail_settings || {});
  for (const definition of policyStepDefinitions) {
    const railSettings = { ...(settings[definition.rail] || {}) };
    for (const [key, _label, type] of definition.fields) {
      const control = policyStepSettings.querySelector(
        `[data-policy-rail="${definition.rail}"][data-policy-rail-setting="${key}"]`
      );
      if (!control) continue;
      let value;
      if (type === "boolean") value = control.checked;
      else if (type === "provider") value = control.providerValue();
      else if (type === "number") value = control.value === "" ? "" : Number(control.value);
      else value = control.value;
      if (value === "" || (typeof value === "number" && !Number.isFinite(value))) delete railSettings[key];
      else railSettings[key] = value;
    }
    settings[definition.rail] = railSettings;
  }
  return settings;
}
function renderPolicyDetail(policy) {
  policyDetailName.textContent = policy.name || policy.policy_id || "未命名策略";
  policyDetailDescription.textContent = String(policy.description || "").trim() || "未说明";
  policyNameInput.value = policy.name || "";
  policyDescriptionInput.value = policy.description || "";
  policyBasicStatus.textContent = "";
  const bindings = Array.isArray(policy.bindings) ? policy.bindings : [];
  policyDetailMeta.replaceChildren(
    document.createTextNode("策略 ID："),
    Object.assign(document.createElement("code"), { textContent: policy.policy_id || "未设置" }),
    document.createTextNode(` · 规则绑定：${bindings.length} 条`),
  );
  renderPolicyGraph(policy);
  renderPolicyStepSettings(policy);
  policyUmoList.replaceChildren();
  policyUmoList.umoEditor = createUmoTagEditor(policy.umo_list || []);
  policyUmoList.append(policyUmoList.umoEditor);
  setDefaultPolicy.disabled = policy.policy_id === policyLibrary.active_policy_id;
  setDefaultPolicy.textContent = policy.policy_id === policyLibrary.active_policy_id
    ? "当前默认策略"
    : "设为默认策略";
  policySessionStatus.textContent = "";
  savePolicyAs.hidden = policy.builtin;
  deletePolicyButton.hidden = policy.builtin;
}
function collectPolicyBindings() {
  try {
    const bindings = [];
    for (const editor of policyStepSettings.querySelectorAll("[data-policy-bindings-rail]")) {
      const rail = editor.dataset.policyBindingsRail;
      let parsed;
      try {
        parsed = JSON.parse(editor.value);
      } catch (error) {
        editor.classList.add("is-invalid");
        throw new SyntaxError(`${rail} 的 JSON 无效：${error.message}`);
      }
      if (!Array.isArray(parsed)) throw new TypeError(`${rail} 的规则绑定必须是 JSON 数组`);
      for (const binding of parsed) {
        if (!binding || typeof binding !== "object" || Array.isArray(binding)) {
          throw new TypeError(`${rail} 的规则绑定必须是对象`);
        }
        bindings.push({ ...binding, rail });
      }
      editor.classList.remove("is-invalid");
    }
    return bindings;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const match = message.match(/^(\w+_rail) /);
    if (match) {
      policyStepSettings.querySelector(`[data-policy-bindings-rail="${match[1]}"]`)?.classList.add("is-invalid");
    }
    policyStepSettingsStatus.textContent = `规则 JSON 无效：${message}`;
    return null;
  }
}
function collectPolicyDetailDraft(policy) {
  const name = policyNameInput.value.trim();
  if (!name) {
    policyBasicStatus.textContent = "请填写策略名称。";
    policyNameInput.focus();
    return null;
  }
  const bindings = collectPolicyBindings();
  if (bindings === null) return null;
  const umoEditor = policyUmoList.umoEditor;
  return {
    ...structuredClone(policy),
    name,
    description: policyDescriptionInput.value.trim(),
    bindings,
    rail_settings: collectPolicyStepSettings(policy),
    umo_list: Array.isArray(umoEditor?.umoValues) ? [...umoEditor.umoValues] : [],
  };
}
function syncPolicyBindingsJson() {
  const policy = policyLibrary.policies.find((item) => item.policy_id === selectedPolicyId);
  const bindings = policy ? collectPolicyBindings() : null;
  if (!policy || bindings === null) return false;
  policy.bindings = bindings;
  return true;
}
function validCustomPolicyId(id) {
  return /^[a-z][a-z0-9_]{0,63}$/.test(id) && id !== "_default";
}
async function persistPolicyLibrary(successMessage) {
  if (!Number.isInteger(currentRevision)) return false;
  try {
    const result = await bridge.apiPost("save_policy_library", {
      expected_revision: currentRevision,
      policy_library: policyLibrary,
    });
    if (!result.success) {
      policyLibraryStatus.textContent = result.detail || result.error || "保存策略失败。";
      return false;
    }
    currentRevision = result.revision;
    policyLibraryStatus.textContent = successMessage(result.revision);
    return true;
  } catch (error) {
    policyLibraryStatus.textContent = `保存策略失败：${error instanceof Error ? error.message : String(error)}`;
    return false;
  }
}
async function saveCurrentPolicy(makeDefault = false) {
  const policy = policyLibrary.policies.find((item) => item.policy_id === selectedPolicyId);
  if (!policy) return false;
  const draft = collectPolicyDetailDraft(policy);
  if (!draft) return false;
  const previousPolicy = structuredClone(policy);
  const previousDefaultPolicyId = policyLibrary.active_policy_id;
  Object.assign(policy, draft);
  if (makeDefault) policyLibrary.active_policy_id = policy.policy_id;
  savePolicy.disabled = true;
  setDefaultPolicy.disabled = true;
  const saved = await persistPolicyLibrary((revision) => makeDefault
    ? `策略“${policy.name || policy.policy_id}”已设为默认策略，revision ${revision}。`
    : `策略“${policy.name || policy.policy_id}”已保存为 revision ${revision}。`);
  savePolicy.disabled = false;
  setDefaultPolicy.disabled = false;
  if (!saved) {
    Object.assign(policy, previousPolicy);
    policyLibrary.active_policy_id = previousDefaultPolicyId;
    return false;
  }
  renderPolicyList();
  renderPolicyDetail(policy);
  policySessionStatus.textContent = makeDefault
    ? "默认策略已更新。"
    : "策略的所有修改已保存。";
  return true;
}
function openCreatePolicyDialog() {
  newPolicyId.value = "";
  newPolicyName.value = "";
  newPolicyDescription.value = "";
  createPolicyStatus.textContent = "";
  createPolicyDialog.showModal();
  newPolicyId.focus();
}
async function createPolicy() {
  const id = newPolicyId.value.trim();
  const name = newPolicyName.value.trim();
  if (!validCustomPolicyId(id)) {
    createPolicyStatus.textContent = "策略 ID 必须以小写字母开头，并只包含小写字母、数字和下划线。";
    return;
  }
  if (!name) { createPolicyStatus.textContent = "请填写策略名称。"; return; }
  if (policyLibrary.policies.some((policy) => policy.policy_id === id)) {
    createPolicyStatus.textContent = "策略 ID 已存在。";
    return;
  }
  const policy = { policy_id: id, name, description: newPolicyDescription.value.trim(), bindings: [], session_scope: {}, builtin: false };
  policyLibrary.policies.push(policy);
  confirmCreatePolicy.disabled = true;
  const saved = await persistPolicyLibrary((revision) => `策略“${name}”已创建为 revision ${revision}。`);
  confirmCreatePolicy.disabled = false;
  if (!saved) { policyLibrary.policies = policyLibrary.policies.filter((item) => item !== policy); return; }
  createPolicyDialog.close();
  renderPolicyList();
  showPolicyDetail(id);
}
function openSavePolicyAsDialog() {
  const source = policyLibrary.policies.find((policy) => policy.policy_id === selectedPolicyId);
  if (!source || source.builtin) return;
  saveAsPolicyId.value = "";
  saveAsPolicyName.value = `${policyNameInput.value.trim() || source.name || source.policy_id} 副本`;
  saveAsPolicyDescription.value = policyDescriptionInput.value.trim();
  saveAsPolicyStatus.textContent = "";
  savePolicyAsDialog.showModal();
  saveAsPolicyId.focus();
}
async function savePolicyAsCopy() {
  const id = saveAsPolicyId.value.trim();
  const name = saveAsPolicyName.value.trim();
  const source = policyLibrary.policies.find((policy) => policy.policy_id === selectedPolicyId);
  if (!source || source.builtin) return;
  if (!validCustomPolicyId(id)) { saveAsPolicyStatus.textContent = "新策略 ID 格式无效。"; return; }
  if (!name) { saveAsPolicyStatus.textContent = "请填写策略名称。"; return; }
  if (policyLibrary.policies.some((policy) => policy.policy_id === id)) { saveAsPolicyStatus.textContent = "策略 ID 已存在。"; return; }
  const draft = collectPolicyDetailDraft(source);
  if (!draft) return;
  const copy = { ...draft, policy_id: id, name, description: saveAsPolicyDescription.value.trim(), builtin: false };
  policyLibrary.policies.push(copy);
  confirmSavePolicyAs.disabled = true;
  const saved = await persistPolicyLibrary((revision) => `策略“${name}”已另存为 revision ${revision}。`);
  confirmSavePolicyAs.disabled = false;
  if (!saved) { policyLibrary.policies = policyLibrary.policies.filter((item) => item !== copy); return; }
  savePolicyAsDialog.close();
  renderPolicyList();
  showPolicyDetail(id);
}
function requestPolicyDeletion() {
  const policy = policyLibrary.policies.find((item) => item.policy_id === selectedPolicyId);
  if (!policy || policy.builtin) return;
  pendingPolicyDeletionId = policy.policy_id;
  confirmPolicyDeleteMessage.textContent = `策略“${policy.name || policy.policy_id}”将被永久删除。`;
  confirmPolicyDeleteDialog.showModal();
}
async function deleteSelectedPolicy() {
  const policyId = pendingPolicyDeletionId;
  const policy = policyLibrary.policies.find((item) => item.policy_id === policyId);
  if (!policy || policy.builtin) return;
  const previousActivePolicyId = policyLibrary.active_policy_id;
  policyLibrary.policies = policyLibrary.policies.filter((item) => item.policy_id !== policyId);
  if (policyLibrary.active_policy_id === policyId) policyLibrary.active_policy_id = "_default";
  confirmPolicyDelete.disabled = true;
  const saved = await persistPolicyLibrary((revision) => `策略“${policy.name || policyId}”已删除，revision ${revision}。`);
  confirmPolicyDelete.disabled = false;
  if (!saved) {
    policyLibrary.policies.push(policy);
    policyLibrary.active_policy_id = previousActivePolicyId;
    return false;
  }
  confirmPolicyDeleteDialog.close();
  showPolicyList();
  return true;
}
function createActionSelect(values, value) {
  const select = document.createElement("select");
  populateRuleActionOptions(select, values);
  ensureOption(select, value);
  select.value = value || "default";
  return select;
}
function hitActionsForTemplate(templateKey) {
  if (templateKey === "plain_keywords" || templateKey === "regex_pattern") {
    return hitActions;
  }
  return hitActions.filter((action) => action !== "sanitize");
}
function createRuleHitActionSelect(templateKey, value) {
  const values = hitActionsForTemplate(templateKey);
  const select = document.createElement("select");
  populateRuleActionOptions(select, values);
  select.value = values.includes(value) ? value : "default";
  return select;
}
function createRuleFieldHint(text) {
  const hint = document.createElement("span");
  hint.className = "rule-field-hint";
  hint.textContent = text;
  return hint;
}
function templateConfigValue(config, field) {
  return Object.hasOwn(config, field.key) ? config[field.key] : field.default;
}
function createTemplateParameterControl(field, value) {
  if (field.type === "provider") {
    return createProviderSelector(String(value ?? ""));
  }
  if (field.type === "boolean") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = "setting-checkbox";
    input.checked = Boolean(value);
    return input;
  }
  if (field.type === "select") {
    const select = document.createElement("select");
    for (const [optionValue, label] of field.options || []) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = label;
      select.append(option);
    }
    ensureOption(select, String(value ?? field.default ?? ""));
    select.value = String(value ?? field.default ?? "");
    return select;
  }
  if (field.type === "list" || field.type === "text") {
    const textarea = document.createElement("textarea");
    textarea.className = field.type === "list" ? "template-list-value" : "template-text-value";
    textarea.spellcheck = field.type !== "list";
    textarea.value = field.type === "list"
      ? (Array.isArray(value) ? value.join("\n") : "")
      : String(value ?? "");
    return textarea;
  }
  const input = document.createElement("input");
  input.type = "number";
  input.step = field.type === "integer" ? "1" : "any";
  input.value = String(value ?? field.default ?? "");
  return input;
}
function createTemplateParameterForm(rule) {
  const section = document.createElement("section");
  section.className = "template-parameters";
  const heading = document.createElement("div");
  const title = document.createElement("h4");
  const description = document.createElement("p");
  title.textContent = "模板参数";
  description.textContent = templateCreationDetails[rule.template_key] || "按此模板的业务字段配置规则。";
  heading.append(title, description);
  const grid = document.createElement("div");
  grid.className = "form-grid template-parameter-grid";
  const config = rule.template_config || {};
  for (const field of templateParameterFields[rule.template_key] || []) {
    const label = document.createElement("label");
    if (field.fullWidth) label.classList.add("full-width");
    label.textContent = field.label;
    const control = createTemplateParameterControl(field, templateConfigValue(config, field));
    control.dataset.templateField = field.key;
    label.append(createRuleFieldHint(field.hint), control);
    grid.append(label);
  }
  section.append(heading, grid);
  return section;
}
function collectTemplateConfig(editor, rule) {
  const config = structuredClone(rule.template_config || {});
  for (const field of templateParameterFields[rule.template_key] || []) {
    const control = editor.querySelector(`[data-template-field="${field.key}"]`);
    if (!control) continue;
    if (field.type === "provider") {
      config[field.key] = typeof control.providerValue === "function"
        ? control.providerValue()
        : "";
    } else if (field.type === "boolean") {
      config[field.key] = control.checked;
    } else if (field.type === "list") {
      config[field.key] = control.value
        .split("\n")
        .map((value) => value.trim())
        .filter(Boolean);
    } else if (field.type === "integer") {
      const value = Number.parseInt(control.value, 10);
      config[field.key] = Number.isNaN(value) ? field.default : value;
    } else if (field.type === "number") {
      const value = Number.parseFloat(control.value);
      config[field.key] = Number.isNaN(value) ? field.default : value;
    } else {
      config[field.key] = control.value;
    }
  }
  return config;
}
function syncRuleEditor(editor) {
  const rule = ruleLibrary.rules.find((item) => item.rule_id === editor.dataset.ruleId);
  if (!rule) return true;
  const templateConfig = collectTemplateConfig(editor, rule);
  const priority = Number.parseInt(editor.querySelector('input[type="number"]').value, 10);
  rule.description = editor.querySelector(".rule-description").value.trim();
  rule.default_priority = Number.isNaN(priority) ? 100 : priority;
  rule.default_action_on_hit = editor.querySelector(".rule-hit-action").value;
  rule.default_action_on_error = editor.querySelector(".rule-error-action").value;
  rule.template_config = templateConfig;
  return true;
}
function createRuleEditor(rule) {
  const editor = document.createElement("article");
  editor.className = "open-rule-editor";
  editor.dataset.ruleId = rule.rule_id;
  const heading = document.createElement("div");
  heading.className = "form-heading";
  const headingText = document.createElement("div");
  const title = document.createElement("h3");
  const template = document.createElement("p");
  title.textContent = rule.rule_id;
  template.textContent = templateDescriptions[rule.template_key] || rule.template_key;
  headingText.append(title, template);
  const actions = document.createElement("div");
  actions.className = "button-group";
  const save = document.createElement("button");
  save.type = "button"; save.className = "rule-card-save"; save.textContent = "保存";
  save.addEventListener("click", () => saveRuleEditor(rule.rule_id));
  const saveAs = document.createElement("button");
  saveAs.type = "button"; saveAs.className = "button-secondary"; saveAs.textContent = "另存为";
  saveAs.addEventListener("click", () => openSaveAsDialog(rule.rule_id));
  const remove = document.createElement("button");
  remove.type = "button"; remove.className = "danger-button"; remove.textContent = "删除";
  remove.addEventListener("click", () => requestRuleDeletion(rule.rule_id));
  const close = document.createElement("button");
  close.type = "button"; close.className = "button-secondary"; close.textContent = "关闭";
  close.addEventListener("click", () => closeRuleEditor(rule.rule_id));
  actions.append(save, saveAs, close, remove); heading.append(headingText, actions);
  const grid = document.createElement("div"); grid.className = "form-grid";
  const descriptionLabel = document.createElement("label"); descriptionLabel.textContent = "规则描述";
  const description = document.createElement("input"); description.className = "rule-description"; description.value = rule.description || ""; description.placeholder = "简述这条规则的用途"; descriptionLabel.append(createRuleFieldHint("用于规则列表的说明，不影响实际执行。"), description);
  const priorityLabel = document.createElement("label"); priorityLabel.textContent = "默认优先级";
  const priority = document.createElement("input"); priority.type = "number"; priority.value = String(Number.isInteger(rule.default_priority) ? rule.default_priority : 100); priorityLabel.append(createRuleFieldHint("数值越小越先执行；策略编排可覆盖此值。"), priority);
  const hitAction = createRuleHitActionSelect(rule.template_key, rule.default_action_on_hit); hitAction.className = "rule-hit-action";
  const hitLabel = document.createElement("label"); hitLabel.textContent = "默认命中动作"; hitLabel.append(createRuleFieldHint("命中时的默认处理；策略编排可覆盖。retry_generation 当前会回退为 Step 默认动作。"), hitAction);
  const errorAction = createActionSelect(errorActions, rule.default_action_on_error); errorAction.className = "rule-error-action";
  const errorLabel = document.createElement("label"); errorLabel.textContent = "默认错误动作"; errorLabel.append(createRuleFieldHint("规则执行出错时的默认处理；retry_generation 当前会回退为 Step 默认动作。"), errorAction);
  grid.append(descriptionLabel, priorityLabel, hitLabel, errorLabel);
  editor.append(heading, grid, createTemplateParameterForm(rule));
  editor.addEventListener("input", () => editor.classList.add("is-dirty"));
  editor.addEventListener("change", () => editor.classList.add("is-dirty"));
  return editor;
}
function openRule(ruleId, afterRuleId = null) {
  if (openRuleIds.includes(ruleId)) {
    openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`)?.scrollIntoView({ block: "nearest" });
    return;
  }
  const rule = ruleLibrary.rules.find((item) => item.rule_id === ruleId);
  if (!rule) return;
  const editor = createRuleEditor(rule);
  const sourceEditor = afterRuleId && openRuleEditors.querySelector(`[data-rule-id="${afterRuleId}"]`);
  if (sourceEditor) sourceEditor.after(editor); else openRuleEditors.append(editor);
  const index = afterRuleId ? openRuleIds.indexOf(afterRuleId) + 1 : openRuleIds.length;
  openRuleIds.splice(index, 0, ruleId);
  ruleEmptyState.hidden = true;
}
function closeRuleEditor(ruleId) {
  const editor = openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`);
  if (!editor) return;
  openRuleIds = openRuleIds.filter((id) => id !== ruleId);
  editor.remove();
  ruleEmptyState.hidden = openRuleIds.length > 0;
  renderRuleList();
}
async function persistRuleLibrary(successMessage) {
  if (!Number.isInteger(currentRevision)) return false;
  try {
    const result = await bridge.apiPost("save_rule_library", {
      expected_revision: currentRevision,
      rule_library: ruleLibrary,
    });
    if (!result.success) {
      ruleStatus.textContent = result.detail || result.error || "保存失败。";
      return false;
    }
    currentRevision = result.revision;
    ruleStatus.textContent = successMessage(result.revision);
    return true;
  } catch (error) {
    ruleStatus.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
    return false;
  }
}
async function saveRuleEditor(ruleId) {
  const editor = openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`);
  if (!editor || !syncRuleEditor(editor)) return;
  const button = editor.querySelector(".rule-card-save");
  button.disabled = true;
  const saved = await persistRuleLibrary((revision) => `规则“${ruleId}”已保存为 revision ${revision}。`);
  button.disabled = false;
  if (!saved) return;
  editor.classList.remove("is-dirty");
  renderRuleList();
}
function requestRuleDeletion(ruleId) {
  pendingRuleDeletionId = ruleId;
  confirmRuleDeleteMessage.textContent = `规则“${ruleId}”会从待保存规则库中移除；若策略仍绑定它，保存会被拒绝。`;
  confirmRuleDeleteDialog.showModal();
}
function deleteRule(ruleId) {
  ruleLibrary.rules = ruleLibrary.rules.filter((rule) => rule.rule_id !== ruleId);
  openRuleIds = openRuleIds.filter((id) => id !== ruleId);
  openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`)?.remove();
  ruleEmptyState.hidden = openRuleIds.length > 0;
  ruleStatus.textContent = "已从待保存的规则库移除规则。若策略仍绑定此规则，后端会拒绝保存。";
  renderRuleList();
}
function openSaveAsDialog(ruleId) {
  const editor = openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`);
  if (!editor || !syncRuleEditor(editor)) return;
  const source = ruleLibrary.rules.find((rule) => rule.rule_id === ruleId);
  if (!source) return;
  saveAsSourceRuleId = ruleId;
  saveAsRuleId.value = "";
  saveAsRuleDescription.value = source.description || "";
  saveAsRuleStatus.textContent = "";
  saveRuleAsDialog.showModal();
  saveAsRuleId.focus();
}
async function saveRuleAs() {
  const id = saveAsRuleId.value.trim();
  if (!/^[a-z][a-z0-9_]{0,63}$/.test(id)) { saveAsRuleStatus.textContent = "规则 ID 格式无效。"; return; }
  if (ruleLibrary.rules.some((rule) => rule.rule_id === id)) { saveAsRuleStatus.textContent = "规则 ID 已存在。"; return; }
  const source = ruleLibrary.rules.find((rule) => rule.rule_id === saveAsSourceRuleId);
  if (!source) { saveAsRuleStatus.textContent = "原规则已不存在。"; return; }
  const copy = { ...source, rule_id: id, description: saveAsRuleDescription.value.trim(), template_config: structuredClone(source.template_config || {}) };
  ruleLibrary.rules.push(copy);
  confirmSaveRuleAs.disabled = true;
  const saved = await persistRuleLibrary((revision) => `新规则“${id}”已保存为 revision ${revision}。`);
  confirmSaveRuleAs.disabled = false;
  if (!saved) {
    ruleLibrary.rules = ruleLibrary.rules.filter((rule) => rule !== copy);
    return;
  }
  openRuleEditors.querySelector(`[data-rule-id="${source.rule_id}"]`)?.classList.remove("is-dirty");
  saveRuleAsDialog.close();
  openRule(id, source.rule_id);
  renderRuleList();
}
function renderTemplateOptions() {
  templateOptions.replaceChildren();
  for (const templateKey of templates) {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "template-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", String(templateKey === selectedNewTemplate));
    option.classList.toggle("is-selected", templateKey === selectedNewTemplate);
    const title = document.createElement("strong");
    const description = document.createElement("span");
    title.textContent = templateDescriptions[templateKey] || templateKey;
    description.textContent = templateCreationDetails[templateKey] || "暂无说明。";
    option.append(title, description);
    option.addEventListener("click", () => {
      selectedNewTemplate = templateKey;
      renderTemplateOptions();
    });
    templateOptions.append(option);
  }
}
function startRuleCreation() {
  selectedNewTemplate = null;
  newRuleId.value = "";
  newRuleDescription.value = "";
  ruleCreationStatus.textContent = "";
  renderTemplateOptions();
  ruleCreationDialog.showModal();
  newRuleId.focus();
}
function cancelNewRuleCreation() {
  ruleCreationDialog.close();
  selectedNewTemplate = null;
  ruleCreationStatus.textContent = "";
}
function createRule() {
  const id = newRuleId.value.trim();
  if (!/^[a-z][a-z0-9_]{0,63}$/.test(id)) {
    ruleCreationStatus.textContent = "规则 ID 必须以小写字母开头，并只包含小写字母、数字和下划线。";
    newRuleId.focus();
    return;
  }
  if (ruleLibrary.rules.some((rule) => rule.rule_id === id)) {
    ruleCreationStatus.textContent = "规则 ID 已存在。";
    newRuleId.focus();
    return;
  }
  if (!selectedNewTemplate) {
    ruleCreationStatus.textContent = "请先选择规则类型。";
    return;
  }
  ruleLibrary.rules.push({
    rule_id: id,
    template_key: selectedNewTemplate,
    description: newRuleDescription.value.trim(),
    template_config: {},
    default_priority: 100,
    default_action_on_hit: "default",
    default_action_on_error: "default",
  });
  ruleStatus.textContent = "已新建规则，保存后才会发布。";
  cancelNewRuleCreation();
  openRule(id);
  renderRuleList();
}
async function refresh() {
  const [overviewResult, diagnosticsResult, ruleResult, policyResult, systemSettingsResult] =
    await Promise.all([
    bridge.apiGet("get_overview"),
    bridge.apiGet("get_diagnostics"),
    bridge.apiGet("get_rule_library"),
    bridge.apiGet("get_policy_library"),
    bridge.apiGet("get_system_settings"),
  ]);
  currentRevision = overviewResult.overview.revision;
  renderOverview(overviewResult.overview);
  renderDiagnostics(diagnosticsResult.diagnostics || []);
  renderSystemSettings(systemSettingsResult);
  systemSettingsStatus.textContent = `已加载系统设置 revision ${systemSettingsResult.revision}。`;
  const previousOpenRuleIds = [...openRuleIds];
  ruleLibrary = {
    rules: Array.isArray(ruleResult.rule_library?.rules)
      ? ruleResult.rule_library.rules
      : [],
  };
  policyLibrary = {
    policies: Array.isArray(policyResult.policy_library?.policies)
      ? policyResult.policy_library.policies
      : [],
    active_policy_id: String(policyResult.policy_library?.active_policy_id || "_default"),
  };
  openRuleEditors.replaceChildren();
  openRuleIds = [];
  for (const ruleId of previousOpenRuleIds) openRule(ruleId);
  ruleEmptyState.hidden = openRuleIds.length > 0;
  renderRuleList();
  if (selectedPolicyId && policyLibrary.policies.some((policy) => policy.policy_id === selectedPolicyId)) {
    renderPolicyDetail(policyLibrary.policies.find((policy) => policy.policy_id === selectedPolicyId));
  } else {
    selectedPolicyId = null;
    policyDetailPanel.hidden = true;
    policyListPanel.hidden = false;
    renderPolicyList();
  }
  const policyValidation = policyResult.validation || { warnings: [], fatal_errors: [] };
  const policyMessages = [
    ...(policyValidation.fatal_errors || []),
    ...(policyValidation.warnings || []),
  ];
  policyLibraryStatus.textContent = policyMessages.length
    ? policyMessages.join(" · ")
    : `已加载 ${customPolicies().length} 条自定义策略，revision ${policyResult.revision}。`;
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
policyGraphCanvas.addEventListener("click", (event) => {
  const node = policyGraphNodeAt(event.clientX, event.clientY);
  policyGraphState.selectedNodeId = node?.id || null;
  if (node) {
    const stateLabel = {
      available: "可用",
      disabled: "禁用",
      warning: "警告",
      unavailable: "不可用",
    }[node.state] || node.state;
    const issueText = node.issues.length ? ` · ${node.issues[0].message}` : "";
    policyGraphStatus.textContent = `已选中 ${node.id} · ${templateDescriptions[node.rule?.template_key] || node.rule?.template_key || "未知规则"} · ${stateLabel}${issueText}`;
  } else if (policyGraphState.model) {
    policyGraphStatus.textContent = `共 ${policyGraphState.model.nodes.length} 个节点、${policyGraphState.model.edges.length} 条依赖。`;
  }
  schedulePolicyGraphRender();
});
policyGraphCanvas.addEventListener("mousemove", (event) => {
  const node = policyGraphNodeAt(event.clientX, event.clientY);
  policyGraphCanvas.title = node
    ? `${node.id} · ${templateDescriptions[node.rule?.template_key] || node.rule?.template_key || "未知规则"}`
    : "";
});
if (window.ResizeObserver) {
  new window.ResizeObserver(() => {
    if (policyGraphIsVisible()) schedulePolicyGraphRender();
  }).observe(policyGraphStage);
}
window.addEventListener("resize", schedulePolicyGraphRender);
document.addEventListener("visibilitychange", updatePolicyGraphAnimation);
newRule.addEventListener("click", startRuleCreation);
cancelRuleCreation.addEventListener("click", cancelNewRuleCreation);
confirmRuleCreation.addEventListener("click", createRule);
backToPolicyList.addEventListener("click", showPolicyList);
savePolicy.addEventListener("click", () => saveCurrentPolicy());
setDefaultPolicy.addEventListener("click", () => saveCurrentPolicy(true));
newPolicy.addEventListener("click", openCreatePolicyDialog);
cancelCreatePolicy.addEventListener("click", () => createPolicyDialog.close());
confirmCreatePolicy.addEventListener("click", createPolicy);
savePolicyAs.addEventListener("click", openSavePolicyAsDialog);
cancelSavePolicyAs.addEventListener("click", () => savePolicyAsDialog.close());
confirmSavePolicyAs.addEventListener("click", savePolicyAsCopy);
deletePolicyButton.addEventListener("click", requestPolicyDeletion);
cancelPolicyDelete.addEventListener("click", () => confirmPolicyDeleteDialog.close());
confirmPolicyDelete.addEventListener("click", async () => {
  if (await deleteSelectedPolicy()) pendingPolicyDeletionId = null;
});
cancelSaveRuleAs.addEventListener("click", () => saveRuleAsDialog.close());
confirmSaveRuleAs.addEventListener("click", saveRuleAs);
cancelRuleDelete.addEventListener("click", () => confirmRuleDeleteDialog.close());
confirmRuleDelete.addEventListener("click", () => {
  if (pendingRuleDeletionId) deleteRule(pendingRuleDeletionId);
  pendingRuleDeletionId = null;
  confirmRuleDeleteDialog.close();
});
saveRuleLibrary.addEventListener("click", async () => {
  if (!Number.isInteger(currentRevision) || ![...openRuleEditors.children].every(syncRuleEditor)) return;
  saveRuleLibrary.disabled = true;
  const saved = await persistRuleLibrary((revision) => `已保存当前所有打开规则为 revision ${revision}。`);
  saveRuleLibrary.disabled = false;
  if (!saved) return;
  [...openRuleEditors.children].forEach((editor) => editor.classList.remove("is-dirty"));
  renderRuleList();
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
