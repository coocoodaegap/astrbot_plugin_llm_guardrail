const bridge = window.AstrBotPluginPage;
const $ = (id) => document.getElementById(id);
const status = $("status"),
  summary = $("snapshot-summary"),
  diagnostics = $("diagnostics"),
  overviewHealthState = $("overview-health-state"),
  overviewDefaultPolicyPath = $("overview-default-policy-path"),
  overviewPrioritySummary = $("overview-priority-summary"),
  overviewRailSummary = $("overview-rail-summary"),
  overviewRailCoverage = $("overview-rail-coverage"),
  overviewAssets = $("overview-assets"),
  overviewBoundary = $("overview-boundary"),
  overviewOpenSystemSettings = $("overview-open-system-settings"),
  systemSettings = $("system-settings"),
  systemSettingsStatus = $("system-settings-status"),
  saveSystemSettings = $("save-system-settings"),
  sharedConstants = $("shared-constants"),
  importSharedConstants = $("import-shared-constants"),
  exportSharedConstants = $("export-shared-constants"),
  saveSharedConstants = $("save-shared-constants"),
  ruleList = $("rule-list"),
  ruleCount = $("rule-count"),
  ruleStatus = $("rule-library-status"),
  policyListPanel = $("policy-list-panel"),
  policyDetailPanel = $("policy-detail-panel"),
  policyList = $("policy-list"),
  policyCount = $("policy-count"),
  policyLibraryStatus = $("policy-library-status"),
  defaultPolicySummary = $("default-policy-summary"),
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
  policyGraphEditor = $("policy-graph-editor"),
  savePolicy = $("save-policy"),
  policyUmoList = $("policy-umo-list"),
  setDefaultPolicy = $("set-default-policy"),
  defaultPolicyIndicator = $("default-policy-indicator"),
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
  policyDependencyModeDialog = $("policy-dependency-mode-dialog"),
  policyDependencyModeDescription = $("policy-dependency-mode-description"),
  policyDependencyMode = $("policy-dependency-mode"),
  cancelPolicyDependencyMode = $("cancel-policy-dependency-mode"),
  confirmPolicyDependencyMode = $("confirm-policy-dependency-mode"),
  confirmPolicyBindingRemoveDialog = $("confirm-policy-binding-remove-dialog"),
  confirmPolicyBindingRemoveMessage = $("confirm-policy-binding-remove-message"),
  cancelPolicyBindingRemove = $("cancel-policy-binding-remove"),
  confirmPolicyBindingRemove = $("confirm-policy-binding-remove"),
  policyRulePickerDialog = $("policy-rule-picker-dialog"),
  policyRulePickerTitle = $("policy-rule-picker-title"),
  policyRulePickerDescription = $("policy-rule-picker-description"),
  policyRulePickerStatus = $("policy-rule-picker-status"),
  policyRulePickerList = $("policy-rule-picker-list"),
  cancelPolicyRulePicker = $("cancel-policy-rule-picker"),
  confirmPolicyRulePicker = $("confirm-policy-rule-picker"),
  policyComponentCreationDialog = $("policy-component-creation-dialog"),
  policyComponentCreationTitle = $("policy-component-creation-title"),
  policyComponentCreationDescription = $("policy-component-creation-description"),
  newPolicyComponentId = $("new-policy-component-id"),
  policyComponentCreationStatus = $("policy-component-creation-status"),
  policyComponentOptions = $("policy-component-options"),
  cancelPolicyComponentCreation = $("cancel-policy-component-creation"),
  confirmPolicyComponentCreation = $("confirm-policy-component-creation"),
  policySaveIssuesDialog = $("policy-save-issues-dialog"),
  policySaveIssuesTitle = $("policy-save-issues-title"),
  policySaveIssuesIntro = $("policy-save-issues-intro"),
  policySaveIssuesList = $("policy-save-issues-list"),
  closePolicySaveIssues = $("close-policy-save-issues"),
  ruleLibraryPanel = $("rule-library-panel"),
  ruleLibraryRulesSection = $("rule-library-rules-section"),
  sharedConstantsPanel = $("shared-constants-panel"),
  showRuleLibraryRules = $("show-rule-library-rules"),
  showSharedConstants = $("show-shared-constants"),
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
  ruleCreationStatus = $("rule-creation-status"),
  accessPlatformId = $("access-platform-id"),
  accessUserId = $("access-user-id"),
  accessDecision = $("access-decision"),
  accessDurationMode = $("access-duration-mode"),
  accessDurationRow = $("access-duration-row"),
  accessDurationMinutes = $("access-duration-minutes"),
  accessReasonCode = $("access-reason-code"),
  accessFormStatus = $("access-form-status"),
  saveAccessDecision = $("save-access-decision"),
  resetAccessForm = $("reset-access-form"),
  accessRecordCount = $("access-record-count"),
  accessDecisionFilter = $("access-decision-filter"),
  refreshAccessRecords = $("refresh-access-records"),
  accessRecordsStatus = $("access-records-status"),
  accessRecordList = $("access-record-list"),
  sessionPolicyListPanel = $("session-policy-list-panel"),
  sessionPolicyDetailPanel = $("session-policy-detail-panel"),
  sessionPolicyStateQuery = $("session-policy-state-query"),
  refreshSessionPolicyStatesButton = $("refresh-session-policy-states"),
  sessionPolicyStateCount = $("session-policy-state-count"),
  sessionPolicyStateStatus = $("session-policy-state-status"),
  sessionPolicyStateList = $("session-policy-state-list"),
  sessionPolicyStatePrevPage = $("session-policy-state-prev-page"),
  sessionPolicyStatePage = $("session-policy-state-page"),
  sessionPolicyStateNextPage = $("session-policy-state-next-page"),
  sessionPolicyDetailUmo = $("session-policy-detail-umo"),
  sessionPolicyDetailMeta = $("session-policy-detail-meta"),
  clearSessionPolicyState = $("clear-session-policy-state"),
  confirmSessionPolicyStateDeleteDialog = $("confirm-session-policy-state-delete-dialog"),
  confirmSessionPolicyStateDeleteMessage = $("confirm-session-policy-state-delete-message"),
  cancelSessionPolicyStateDelete = $("cancel-session-policy-state-delete"),
  confirmSessionPolicyStateDelete = $("confirm-session-policy-state-delete"),
  sessionPolicySelection = $("session-policy-selection"),
  saveSessionPolicySelection = $("save-session-policy-selection"),
  sessionPolicySelectionStatus = $("session-policy-selection-status"),
  sessionPolicyResultSummary = $("session-policy-result-summary"),
  sessionPolicySignalList = $("session-policy-signal-list"),
  sessionPolicyRouteCandidate = $("session-policy-route-candidate"),
  sessionPolicyRequestObservation = $("session-policy-request-observation"),
  sessionPolicyTargetComparison = $("session-policy-target-comparison"),
  sessionPolicyActivityList = $("session-policy-activity-list"),
  backToSessionPolicyList = $("back-to-session-policy-list"),
  ragExperienceListPanel = $("rag-experience-list-panel"),
  ragExperienceDetailPanel = $("rag-experience-detail-panel"),
  ragExperienceQuery = $("rag-experience-query"),
  refreshRagExperiencesButton = $("refresh-rag-experiences"),
  ragExperienceCount = $("rag-experience-count"),
  ragExperienceStatus = $("rag-experience-status"),
  ragExperienceList = $("rag-experience-list"),
  ragExperiencePrevPage = $("rag-experience-prev-page"),
  ragExperiencePage = $("rag-experience-page"),
  ragExperienceNextPage = $("rag-experience-next-page"),
  ragExperienceDetailHeading = $("rag-experience-detail-heading"),
  ragExperienceDetailMeta = $("rag-experience-detail-meta"),
  ragExperienceSourceMeta = $("rag-experience-source-meta"),
  ragExperienceTitle = $("rag-experience-title"),
  ragExperienceContent = $("rag-experience-content"),
  ragExperienceDetailStatus = $("rag-experience-detail-status"),
  saveRagExperience = $("save-rag-experience"),
  deleteRagExperience = $("delete-rag-experience"),
  uploadRagExperience = $("upload-rag-experience"),
  backToRagExperienceList = $("back-to-rag-experience-list"),
  confirmRagExperienceDeleteDialog = $("confirm-rag-experience-delete-dialog"),
  confirmRagExperienceDeleteMessage = $("confirm-rag-experience-delete-message"),
  cancelRagExperienceDelete = $("cancel-rag-experience-delete"),
  confirmRagExperienceDelete = $("confirm-rag-experience-delete");
const reportStack = $("report-stack");
const importRules = $("import-rules"),
  exportRules = $("export-rules"),
  importPolicies = $("import-policies"),
  exportPolicies = $("export-policies"),
  configurationExportDialog = $("configuration-export-dialog"),
  configurationExportTitle = $("configuration-export-title"),
  configurationExportDescription = $("configuration-export-description"),
  configurationExportStatus = $("configuration-export-status"),
  configurationExportList = $("configuration-export-list"),
  cancelConfigurationExport = $("cancel-configuration-export"),
  confirmConfigurationExport = $("confirm-configuration-export"),
  configurationImportDialog = $("configuration-import-dialog"),
  configurationImportFile = $("configuration-import-file"),
  configurationImportMode = $("configuration-import-mode"),
  configurationImportStatus = $("configuration-import-status"),
  configurationImportPreview = $("configuration-import-preview"),
  cancelConfigurationImport = $("cancel-configuration-import"),
  confirmConfigurationImport = $("confirm-configuration-import");

let configurationExportKind = null,
  configurationImportKind = null,
  pendingConfigurationPackage = null;

function publishReport(message, { tone = "success", duration } = {}) {
  const text = String(message || "").trim();
  if (!text || !reportStack) return;
  const item = document.createElement("article");
  item.className = "report-message is-" + tone;
  item.setAttribute("role", tone === "error" ? "alert" : "status");
  const content = document.createElement("span");
  content.className = "report-message-content";
  content.textContent = text;
  const dismissButton = document.createElement("button");
  dismissButton.type = "button";
  dismissButton.className = "report-message-dismiss";
  dismissButton.setAttribute("aria-label", "关闭此消息");
  dismissButton.textContent = "×";
  let dismissed = false;
  const dismiss = () => {
    if (dismissed) return;
    dismissed = true;
    item.classList.remove("is-visible");
    item.classList.add("is-leaving");
    window.setTimeout(() => item.remove(), 180);
  };
  dismissButton.addEventListener("click", dismiss);
  item.append(content, dismissButton);
  reportStack.append(item);
  while (reportStack.childElementCount > 4) reportStack.firstElementChild?.remove();
  window.requestAnimationFrame(() => item.classList.add("is-visible"));
  const lifetime = duration ?? (tone === "error" ? 0 : tone === "warning" ? 6200 : 4200);
  if (lifetime > 0) window.setTimeout(dismiss, lifetime);
}

function openConfigurationExport(kind) {
  const isRules = kind === "rules";
  const items = isRules ? ruleLibrary.rules : policyLibrary.policies;
  configurationExportKind = kind;
  configurationExportTitle.textContent = isRules ? "导出规则" : "导出策略";
  configurationExportDescription.textContent = isRules
    ? "选择规则；导出文件只包含这些规则。"
    : "选择策略；关联规则会自动一并写入自包含文件。";
  configurationExportStatus.textContent = items.length ? "" : "当前没有可导出的项目。";
  configurationExportList.replaceChildren();
  for (const item of items) {
    const id = isRules ? item.rule_id : item.policy_id;
    const label = document.createElement("label");
    label.className = "policy-rule-picker-item";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = String(id || "");
    const content = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = isRules
      ? `${id} · ${item.template_key || "未知模板"}`
      : `${item.name || id} · ${id}`;
    const description = document.createElement("small");
    description.textContent = isRules
      ? String(item.description || "未填写描述")
      : `${Array.isArray(item.bindings) ? item.bindings.length : 0} 条规则绑定`;
    content.append(title, description);
    label.append(input, content);
    configurationExportList.append(label);
  }
  confirmConfigurationExport.disabled = items.length === 0;
  configurationExportDialog.showModal();
}

function selectedConfigurationExportIds() {
  return [...configurationExportList.querySelectorAll("input:checked")]
    .map((input) => input.value)
    .filter(Boolean);
}

const SHARED_CONSTANT_REFERENCE_PATTERN = /\$\{\s*([A-Z0-9_]{1,64})\s*\}/g;

function collectSharedConstantReferences(value, references = new Set()) {
  if (typeof value === "string") {
    for (const match of value.matchAll(SHARED_CONSTANT_REFERENCE_PATTERN)) {
      references.add(match[1]);
    }
  } else if (Array.isArray(value)) {
    value.forEach((item) => collectSharedConstantReferences(item, references));
  } else if (value && typeof value === "object") {
    Object.values(value).forEach((item) => collectSharedConstantReferences(item, references));
  }
  return references;
}

function collectReferencedSharedConstants(rules, policies, constants) {
  const references = collectSharedConstantReferences([...rules, ...policies]);
  return Object.fromEntries(
    [...references]
      .sort()
      .filter((name) => Object.prototype.hasOwnProperty.call(constants, name))
      .map((name) => [name, constants[name]]),
  );
}

function buildSharedConstantsExportPackage(constants) {
  return {
    format_version: 1,
    kind: "shared_constants",
    exported_at: new Date().toISOString(),
    rules: [],
    policies: [],
    system_constants: constants,
  };
}

function buildConfigurationExportPackage(kind, selectedIds, constants) {
  if (kind === "rules") {
    const selected = new Set(selectedIds);
    const rules = ruleLibrary.rules.filter((rule) => selected.has(rule.rule_id));
    return {
      format_version: 1,
      kind: "rules",
      exported_at: new Date().toISOString(),
      rules,
      policies: [],
      system_constants: collectReferencedSharedConstants(rules, [], constants),
    };
  }
  const selected = new Set(selectedIds);
  const policies = policyLibrary.policies.filter((policy) => selected.has(policy.policy_id));
  const requiredRuleIds = new Set(policies.flatMap((policy) =>
    Array.isArray(policy.bindings) ? policy.bindings.map((binding) => binding.rule_id) : []));
  return {
    format_version: 1,
    kind: "policies",
    exported_at: new Date().toISOString(),
    rules: ruleLibrary.rules.filter((rule) => requiredRuleIds.has(rule.rule_id)),
    policies,
    system_constants: collectReferencedSharedConstants(
      ruleLibrary.rules.filter((rule) => requiredRuleIds.has(rule.rule_id)),
      policies,
      constants,
    ),
  };
}

async function getSharedConstantsForExport() {
  if (sharedConstantsDirty) return collectSharedConstants();
  const result = await bridge.apiGet("get_shared_constants");
  if (!result?.success || !result.constants || typeof result.constants !== "object") {
    throw new Error(result?.detail || result?.error || "无法读取公用常量。");
  }
  return result.constants;
}

function downloadConfigurationPackage(packageValue) {
  const json = `${JSON.stringify(packageValue, null, 2)}\n`;
  const blob = new Blob([json], { type: "application/json;charset=utf-8" });
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const date = new Date().toISOString().slice(0, 10);
  link.href = href;
  const filenameKind = packageValue.kind === "shared_constants" ? "constants" : packageValue.kind;
  link.download = `guardrail-${filenameKind}-${date}.json`;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(href), 0);
}

function openConfigurationImport(kind) {
  if (hasUnsavedRuleDrafts() || hasUnsavedPolicyDraft() || sharedConstantsDirty) {
    publishReport("请先保存或放弃当前规则/策略草稿，再导入配置包。", { tone: "warning" });
    return;
  }
  const labels = {
    rules: "规则",
    policies: "策略",
    shared_constants: "公用常量",
  };
  configurationImportKind = kind;
  pendingConfigurationPackage = null;
  configurationImportFile.value = "";
  configurationImportStatus.textContent = `请选择${labels[kind] || "配置"} JSON 文件。`;
  configurationImportPreview.hidden = true;
  configurationImportPreview.textContent = "";
  confirmConfigurationImport.disabled = true;
  configurationImportDialog.showModal();
}

async function previewConfigurationImport() {
  const [file] = configurationImportFile.files || [];
  pendingConfigurationPackage = null;
  confirmConfigurationImport.disabled = true;
  configurationImportPreview.hidden = true;
  if (!file) {
    configurationImportStatus.textContent = "请选择 JSON 文件。";
    return;
  }
  try {
    const packageValue = JSON.parse(await file.text());
    const result = await bridge.apiPost("preview_config_import", {
      package: packageValue,
      conflict_mode: configurationImportMode.value,
    });
    if (!result?.success) throw new Error(result?.detail || result?.error || "配置包校验失败。");
    const preview = result.preview;
    if (preview.kind !== configurationImportKind) {
      const expectedLabel = {
        rules: "规则",
        policies: "策略",
        shared_constants: "公用常量",
      }[configurationImportKind] || "配置";
      throw new Error(`请选择${expectedLabel}配置包。`);
    }
    pendingConfigurationPackage = packageValue;
    const ruleConflicts = Array.isArray(preview.rule_conflicts) ? preview.rule_conflicts.length : 0;
    const policyConflicts = Array.isArray(preview.policy_conflicts) ? preview.policy_conflicts.length : 0;
    const constantConflicts = Array.isArray(preview.constant_conflicts) ? preview.constant_conflicts.length : 0;
    const constantCount = preview.constants && typeof preview.constants === "object"
      ? Object.keys(preview.constants).length : 0;
    const constantConflictNames = Array.isArray(preview.constant_conflicts)
      ? preview.constant_conflicts.join(", ") : "";
    const copiedIdentifierMappings = (mapping) => mapping && typeof mapping === "object"
      ? Object.entries(mapping)
        .filter(([source, target]) => source !== target)
        .map(([source, target]) => `${source} → ${target}`)
        .join(", ") : "";
    const copiedRuleIds = copiedIdentifierMappings(preview.rule_id_map);
    const copiedPolicyIds = copiedIdentifierMappings(preview.policy_id_map);
    const copiedConstantIds = copiedIdentifierMappings(preview.constant_name_map);
    const copyMappings = [
      copiedRuleIds && `规则：${copiedRuleIds}`,
      copiedPolicyIds && `策略：${copiedPolicyIds}`,
      copiedConstantIds && `常量：${copiedConstantIds}`,
    ].filter(Boolean).join("；");
    configurationImportStatus.textContent = "文件校验通过。确认后才会写入配置快照。";
    const warnings = Array.isArray(preview.warnings) && preview.warnings.length
      ? ` 警告：${preview.warnings.join("；")}` : "";
    configurationImportPreview.textContent = `规则 ${preview.rules.length} 条，策略 ${preview.policies.length} 条，公用常量 ${constantCount} 项；规则 ID 冲突 ${ruleConflicts} 个，策略 ID 冲突 ${policyConflicts} 个，常量名冲突 ${constantConflicts} 个${constantConflictNames ? `（${constantConflictNames}）` : ""}。${copyMappings ? ` 拷贝副本映射：${copyMappings}。` : ""}${warnings}`;
    configurationImportPreview.hidden = false;
    confirmConfigurationImport.disabled = false;
  } catch (error) {
    configurationImportStatus.textContent = `无法导入：${error instanceof Error ? error.message : String(error)}`;
  }
}

async function importConfigurationPackage() {
  if (!pendingConfigurationPackage || !Number.isInteger(currentRevision)) return;
  confirmConfigurationImport.disabled = true;
  try {
    const result = await bridge.apiPost("import_config_package", {
      package: pendingConfigurationPackage,
      conflict_mode: configurationImportMode.value,
      expected_revision: currentRevision,
    });
    if (!result?.success) throw new Error(result?.detail || result?.error || "导入失败。");
    currentRevision = result.revision;
    const [rules, policies, constants] = await Promise.all([
      bridge.apiGet("get_rule_library"), bridge.apiGet("get_policy_library"), bridge.apiGet("get_shared_constants"),
    ]);
    applyRuleLibraryPayload(rules);
    applyPolicyLibraryPayload(policies);
    sharedConstantsDirty = false;
    applySharedConstantsPayload(constants);
    configurationImportDialog.close();
    publishReport(`配置包已导入为 revision ${result.revision}。`);
    rerenderOverviewIfReady();
  } catch (error) {
    configurationImportStatus.textContent = `导入失败：${error instanceof Error ? error.message : String(error)}`;
    confirmConfigurationImport.disabled = false;
  }
}

const systemSettingHintOverrides = {
  default_action_on_hit: "规则命中风险时采用的默认处理方式。",
  default_action_on_error: "规则执行出错时采用的默认处理方式。",
  group_chat_mode: "决定哪些群聊会进入 Guardrail 流程。",
  private_chat_mode: "决定哪些私聊会进入 Guardrail 流程。",
  blacklist_duration_minutes: "-1 表示永久；这里选择“永久”时会保存为 -1。正整数表示封禁分钟数。",
  blacklist_max_violations: "只有成功提交的 Step 1 终止性拦截才会计入此阈值。",
  blacklist_message: "命中封禁时的提示文本；支持 ${user_id}。留空仍会使用内置默认提示。",
  blacklist_message_interval_minutes: "同一已封禁用户的提示间隔。0 表示每次提示；-1 表示静默；其他负数无效。",
};
const multilineSystemSettingKeys = new Set(["block_message", "blacklist_message"]);
const systemConstantNamePattern = /^[A-Z0-9_]{1,64}$/;
const templates = [
    "plain_keywords",
    "regex_pattern",
    "contains_request_user_id",
    "rag_judge",
    "llm_review",
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
  errorActions = ["default", "discard", "record", "block"];
const ruleActionDescriptions = {
  default: "沿用策略默认动作（default）",
  observe: "仅记录命中，不改变请求或输出（observe）",
  block: "阻断本轮请求或输出（block）",
  sanitize: "生成净化文本（sanitize）",
  retry_generation: "请求模型重新生成输出（retry_generation）",
  discard: "丢弃本次规则结果（discard）",
  record: "记录可被依赖的错误结果（record）",
};
const templateDescriptions = {
  plain_keywords: "关键词匹配",
  regex_pattern: "正则匹配",
  logic_gate: "逻辑门",
  encoded_payload_detector: "编码载荷检测器",
  length_anomaly_detector: "长度异常检测器",
  role_marker_spoofing_detector: "角色标记伪造检测器",
  external_fetch_detector: "外部资源操作检测器",
  instruction_override_detector: "指令覆盖检测器",
  context_extractor: "对话上下文提取器",
  format_violation_detector: "输出格式违约检测器",
  poor_quality_detector: "异常低质回复检测器",
  metadata_leakage_detector: "运行时工件泄漏检测器",
  refusal_leakage_detector: "拒答内部边界泄漏检测器",
  language_drift_detector: "对话语言漂移检测器",
  sensitive_echo_detector: "风险信号复判",
  contains_request_user_id: "请求者 ID 匹配规则",
  contains_forward: "转发消息检测器",
  contains_file: "文件消息检测器",
  contains_image: "图片消息检测器",
  contains_record: "语音消息检测器",
  contains_video: "视频消息检测器",
  rag_judge: "知识库裁判",
  llm_review: "LLM 审查",
  strengthen_prompt: "增强提示词",
  route_policy: "模型路由",
};
const templateCreationDetails = {
  plain_keywords: "按关键词或短语匹配输入、请求或输出内容。",
  regex_pattern: "使用正则表达式匹配结构化或复杂文本模式。",
  contains_request_user_id: "判断当前请求发送者 ID 是否命中可复用的用户 ID 列表；不替代访问控制。",
  rag_judge: "以知识库检索结果为证据进行风险裁判。",
  llm_review: "调用旁路 LLM 对内容进行结构化审查。",
  strengthen_prompt: "向请求注入额外约束或上下文提示。",
  route_policy: "根据规则命中结果选择目标模型 Provider。",
};
const templateParameterFields = {
  plain_keywords: [
    { key: "keywords", label: "关键词列表", hint: "每行一个关键词或短语。", type: "list", default: [], fullWidth: true },
    { key: "keyword_weights", label: "关键词权值", hint: "每行一项，格式为：关键词:权重。未填写的关键词权重为 1。", type: "list", default: [], fullWidth: true },
    { key: "threshold", label: "命中门槛", hint: "命中关键词的权重总和达到此值时规则命中。", type: "number", default: 1 },
    { key: "sanitizer", label: "净化文本", hint: "仅在选择 sanitize 时使用，将命中片段替换为净化文本，留空则移除命中片段；命中时不自动改写文本，而是在信号的 payload 中生成 sanitized 字段来存放净化后的文本，可在后续节点中使用 ${规则名.sanitized}。", type: "string" },
  ],
  regex_pattern: [
    { key: "pattern", label: "正则模式", hint: "用于匹配文本的正则表达式；保存后由后端编译校验。", type: "text", fullWidth: true },
    { key: "sanitizer", label: "净化文本", hint: "仅在选择 sanitize 时使用，将命中片段替换为净化文本，留空则移除命中片段；命中时不自动改写文本，而是在信号的 payload 中生成 sanitized 字段来存放净化后的文本，可在后续节点中使用 ${规则名.sanitized}。", type: "string" },
  ],
  contains_request_user_id: [
    { key: "user_ids", label: "用户 ID 列表", hint: "每行一个请求者 ID；空列表不能保存为可用规则。", type: "list", default: [], fullWidth: true },
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
  latestOverview = null,
  latestDiagnostics = [],
  activeTabName = "overview",
  tabLoadEpoch = 0,
  pendingOverviewPolicyId = null,
  systemSettingsDirty = false,
  sharedConstantsDirty = false,
  ruleLibrary = { rules: [] },
  policyLibrary = { policies: [], active_policy_id: "", umo_policy_selections: {} },
  openRuleIds = [],
  selectedPolicyId = null,
  pendingPolicyDeletionId = null,
  pendingPolicyBindingRemovalId = null,
  pendingPolicyBindingRail = null,
  pendingPolicyComponentRail = null,
  selectedNewComponentType = null,
  saveAsSourceRuleId = null,
  pendingRuleDeletionId = null,
  pendingRuleDeletionIds = new Set(),
  selectedNewTemplate = null,
  systemSettingsSchema = {},
  systemSettingsDraft = {},
  registeredProviders = [],
  policyGraphState = {
    model: null,
    layout: null,
    collapsedRails: new Set(),
    hiddenNodeStates: new Set(),
    selectedNodeId: null,
    selectedRail: null,
    dependencySelection: null,
    pendingDependencySourceId: null,
    dirtyNodeIds: new Set(),
    draft: null,
    renderFrame: 0,
    animationFrame: 0,
  };
let accessRecords = [],
  accessReasonCodes = { ban: [], pardon: [] },
  accessFormExpectedRecordRevision = null,
  accessRefreshEpoch = 0,
  accessMutationInFlight = false;
let sessionPolicyStateItems = [],
  selectedSessionPolicyUmo = null,
  sessionPolicyStateCurrentPage = 1,
  sessionPolicyStateTotal = 0,
  sessionPolicyStatePageSize = 30,
  sessionPolicyMonitoringEnabled = false,
  sessionPolicyStateRefreshEpoch = 0,
  sessionPolicyStateDetailEpoch = 0,
  sessionPolicySelectionInFlight = false,
  sessionPolicyStateDeleteInFlight = false,
  selectedSessionPolicyRecordRevision = null;
let ragExperienceItems = [],
  selectedRagExperience = null,
  ragExperienceCurrentPage = 1,
  ragExperienceTotal = 0,
  ragExperiencePageSize = 30,
  ragExperienceRefreshEpoch = 0,
  ragExperienceDetailEpoch = 0,
  ragExperienceMutationInFlight = false;
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
  activeTabName = name;
  document.querySelectorAll("[data-tab]").forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
  updatePolicyGraphAnimation();
  if (name === "session") {
    showSessionPolicyStateList();
  }
  if (name === "knowledge") {
    showRagExperienceList();
  }
  if (bridge) void loadTabData(name);
}
function switchRuleLibrarySection(section) {
  const showRules = section !== "constants";
  ruleLibraryRulesSection.hidden = !showRules;
  sharedConstantsPanel.hidden = showRules;
  showRuleLibraryRules.classList.toggle("is-active", showRules);
  showRuleLibraryRules.setAttribute("aria-selected", String(showRules));
  showSharedConstants.classList.toggle("is-active", !showRules);
  showSharedConstants.setAttribute("aria-selected", String(!showRules));
}
document
  .querySelectorAll("[data-tab]")
  .forEach((tab) =>
    tab.addEventListener("click", () => switchTab(tab.dataset.tab)),
  );
overviewOpenSystemSettings.addEventListener("click", () => switchTab("system"));
function addSummary(label, value) {
  const term = document.createElement("dt"),
    detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = String(value);
  summary.append(term, detail);
}
const overviewRailDefinitions = Object.freeze([
  { rail: "input_rail", step: "Step 1", label: "输入分析" },
  { rail: "routing_rail", step: "Step 2", label: "模型路由" },
  { rail: "request_rail", step: "Step 3", label: "请求审查" },
  { rail: "prompt_rail", step: "Step 4", label: "提示词增强" },
  { rail: "output_rail", step: "Step 5", label: "输出检查" },
]);
function formatOverviewTime(value) {
  const raw = String(value || "").trim();
  if (!raw) return "未记录";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  try {
    return date.toLocaleString("zh-CN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return raw;
  }
}
function overviewCount(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}
function appendOverviewLine(container, label, value) {
  const row = document.createElement("div");
  const term = document.createElement("span");
  const detail = document.createElement("strong");
  term.textContent = label;
  detail.textContent = value;
  row.append(term, detail);
  container.append(row);
}
function createOverviewMetric(label, value, note = "") {
  const metric = document.createElement("article");
  const count = document.createElement("strong");
  const title = document.createElement("span");
  const description = document.createElement("small");
  metric.className = "overview-metric";
  count.textContent = String(value);
  title.textContent = label;
  description.textContent = note;
  metric.append(count, title, description);
  return metric;
}
function overviewPolicyById(policyId) {
  return policyLibrary.policies.find((policy) => policy.policy_id === policyId) || null;
}
function showOverviewPolicyPath(policyId) {
  pendingOverviewPolicyId = String(policyId || "").trim() || null;
  switchTab("policies");
}
function renderOverviewDefaultPolicyPath(overview) {
  overviewDefaultPolicyPath.replaceChildren();
  const policyId = String(overview.effective_policy_id || "").trim();
  const policy = overviewPolicyById(policyId);
  const mappingCount = overviewCount(overview.umo_policy_selection_count);
  const inputLlmReviewEnabled = Boolean(overview.fallback_input_llm_review_enabled);
  const outputLlmReviewEnabled = Boolean(overview.fallback_output_llm_review_enabled);
  const identity = document.createElement("div");
  const title = document.createElement("strong");
  const description = document.createElement("p");
  const details = document.createElement("div");
  const action = document.createElement("button");
  title.textContent = policyId
    ? (policy?.name || overview.effective_policy_name || policyId)
    : "系统 fallback 图";
  if (policyId) {
    description.textContent = "默认策略 · " + policyId;
    appendOverviewLine(
      details,
      "会话指定",
      mappingCount ? String(mappingCount) + " 项 UMO 显式选择" : "未设置显式选择",
    );
    appendOverviewLine(details, "失效回退", "系统 fallback 图");
    action.textContent = "策略详情";
    action.addEventListener("click", () => showOverviewPolicyPath(policyId));
  } else {
    description.textContent = "尚未指定默认策略";
    appendOverviewLine(details, "请求路径", "找不到合法策略时使用 fallback");
    appendOverviewLine(
      details,
      "输入 LLM 旁审",
      inputLlmReviewEnabled ? "fallback 中已开启" : "fallback 中未开启",
    );
    appendOverviewLine(
      details,
      "输出 LLM 旁审",
      outputLlmReviewEnabled ? "fallback 中已开启" : "fallback 中未开启",
    );
    action.textContent = "策略详情";
    action.disabled = true;
  }
  identity.className = "overview-default-policy-identity";
  identity.append(title, description);
  action.type = "button";
  action.className = "button-secondary overview-inline-action";
  overviewDefaultPolicyPath.append(identity, details, action);
}
function renderOverviewPriority(overview) {
  overviewPrioritySummary.replaceChildren();
  const messages = [];
  const diagnosticCount = latestDiagnostics.length || overviewCount(overview.warning_count);
  if (diagnosticCount) {
    messages.push({
      tone: "is-warning",
      title: "发现 " + diagnosticCount + " 项配置诊断",
      detail: "请先确认诊断是否会使节点降级或使保存失败。",
    });
  }
  if (!String(overview.effective_policy_id || "").trim()) {
    messages.push({
      tone: "is-attention",
      title: "未指定默认策略",
      detail: "未匹配到合法策略的请求会使用系统 fallback 图。",
    });
  }
  if (overview.graph?.has_cycle_suspect) {
    messages.push({
      tone: "is-danger",
      title: "检测到依赖图循环迹象",
      detail: "请在策略编排中检查节点依赖关系。",
    });
  }
  if (!messages.length) {
    messages.push({
      tone: "is-clear",
      title: "当前没有待处理的配置提示",
      detail: "当前快照没有返回需要处理的配置项。",
    });
  }
  for (const message of messages.slice(0, 3)) {
    const item = document.createElement("article");
    const title = document.createElement("strong");
    const detail = document.createElement("span");
    item.className = "overview-priority-item " + message.tone;
    title.textContent = message.title;
    detail.textContent = message.detail;
    item.append(title, detail);
    overviewPrioritySummary.append(item);
  }
}
function renderOverviewRails(overview) {
  overviewRailCoverage.replaceChildren();
  let enabledCount = 0;
  let enabledNodes = 0;
  let totalNodes = 0;
  const activePolicyId = String(overview.effective_policy_id || "").trim();
  for (const definition of overviewRailDefinitions) {
    const rail = overview.rails?.[definition.rail] || {};
    const enabled = rail.enabled !== false;
    const activeNodes = overviewCount(rail.enabled_nodes);
    const nodes = overviewCount(rail.total_nodes);
    if (enabled) enabledCount += 1;
    enabledNodes += activeNodes;
    totalNodes += nodes;
    const card = document.createElement("button");
    const step = document.createElement("span");
    const title = document.createElement("strong");
    const state = document.createElement("small");
    const coverage = document.createElement("em");
    card.type = "button";
    card.className = "overview-rail-card " + (enabled ? "is-enabled" : "is-disabled");
    card.dataset.rail = definition.rail;
    step.textContent = definition.step;
    title.textContent = definition.label;
    state.textContent = enabled ? "已启用" : "未启用";
    coverage.textContent = String(activeNodes) + " / " + String(nodes) + " 有效节点";
    card.append(step, title, state, coverage);
    card.addEventListener("click", () => showOverviewPolicyPath(activePolicyId));
    overviewRailCoverage.append(card);
  }
  overviewRailSummary.textContent = String(enabledCount)
    + " / " + String(overviewRailDefinitions.length)
    + " 个 Step 已开启 · " + String(enabledNodes)
    + " / " + String(totalNodes) + " 个有效节点";
}
function renderOverviewAssets(overview) {
  overviewAssets.replaceChildren();
  const componentTypeCount = Object.keys(componentDefinitions).length;
  overviewAssets.append(
    createOverviewMetric("规则", overviewCount(overview.rule_library_count), "可复用规则本体"),
    createOverviewMetric("策略", overviewCount(overview.policy_library_count), "策略图与默认路径"),
    createOverviewMetric("可用元件", componentTypeCount, "当前可放置的元件种类"),
    createOverviewMetric("公用常量", overviewCount(overview.system_constant_count), "策略与 fallback 共用文本"),
  );
}
function renderOverviewBoundary() {
  overviewBoundary.replaceChildren();
  const banned = accessRecords.filter((record) => record.decision === "ban").length;
  const pardoned = accessRecords.filter((record) => record.decision === "pardon").length;
  overviewBoundary.append(
    createOverviewMetric("有效封禁", banned, "当前访问控制决定"),
    createOverviewMetric("有效赦免", pardoned, "仅跳过访问控制"),
    createOverviewMetric(
      "会话观测",
      sessionPolicyMonitoringEnabled ? sessionPolicyStateTotal : "未启用",
      sessionPolicyMonitoringEnabled ? "已观测 UMO" : "会话状态未记录",
    ),
    createOverviewMetric("RAG 经验", ragExperienceTotal, "本地命中经验记录"),
  );
}
function renderOverview(overview) {
  if (!overview || typeof overview !== "object") return;
  summary.replaceChildren();
  const diagnosticCount = latestDiagnostics.length || overviewCount(overview.warning_count);
  overviewHealthState.textContent = diagnosticCount ? String(diagnosticCount) + " 项提示" : "已发布";
  overviewHealthState.className = "overview-state-pill " + (diagnosticCount ? "is-warning" : "is-ready");
  addSummary("当前 revision", overview.revision);
  addSummary("最近保存", formatOverviewTime(overview.saved_at));
  addSummary("配置版本", overview.schema_version);
  renderOverviewDefaultPolicyPath(overview);
  renderOverviewPriority(overview);
  renderOverviewRails(overview);
  renderOverviewAssets(overview);
  renderOverviewBoundary();
}
function rerenderOverviewIfReady() {
  if (latestOverview) renderOverview(latestOverview);
}
function renderDiagnostics(items) {
  diagnostics.replaceChildren();
  const messages = Array.isArray(items)
    ? items.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  if (!messages.length) {
    const item = document.createElement("li");
    item.className = "overview-diagnostic-item is-clear";
    item.textContent = "当前已发布快照未发现配置诊断。";
    diagnostics.append(item);
    return;
  }
  for (const message of messages) {
    const item = document.createElement("li");
    item.className = "overview-diagnostic-item is-warning";
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
function createUmoTextarea(value) {
  const textarea = document.createElement("textarea");
  textarea.rows = 4;
  textarea.className = "list-value";
  textarea.value = Array.isArray(value) ? value.join("\n") : "";
  textarea.placeholder = "每行一个 UMO，也可用逗号分隔";
  return textarea;
}
function parseUmoList(value) {
  return String(value ?? "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
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
    return createUmoTextarea(value);
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
  if (multilineSystemSettingKeys.has(fieldKey)) {
    const textarea = document.createElement("textarea");
    textarea.rows = 4;
    textarea.value = String(value ?? "");
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
function createSystemConstantRow(name = "", value = "") {
  const row = document.createElement("div");
  row.className = "system-constant-row";
  row.dataset.systemConstantRow = "true";

  const nameField = document.createElement("label");
  nameField.className = "system-constant-name-field";
  nameField.textContent = "名称";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = name;
  nameInput.placeholder = "SAFETY_PREAMBLE";
  nameInput.pattern = "[A-Z0-9_]{1,64}";
  nameInput.maxLength = 64;
  nameInput.dataset.systemConstantName = "true";
  nameInput.addEventListener("input", clearSystemConstantValidation);
  nameField.append(nameInput);

  const valueField = document.createElement("label");
  valueField.className = "system-constant-value-field";
  valueField.textContent = "文本值";
  const valueInput = document.createElement("textarea");
  valueInput.rows = 3;
  valueInput.value = value;
  valueInput.placeholder = "可在策略文本模板中通过 ${SAFETY_PREAMBLE} 复用";
  valueInput.dataset.systemConstantValue = "true";
  valueInput.addEventListener("input", clearSystemConstantValidation);
  valueField.append(valueInput);

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "button-secondary system-constant-remove";
  remove.textContent = "删除";
  remove.addEventListener("click", () => row.remove());

  row.append(nameField, valueField, remove);
  return row;
}
function renderSharedConstantsEditor(constants) {
  sharedConstants.replaceChildren();
  const editor = document.createElement("div");
  editor.className = "system-constants-editor";
  editor.dataset.systemConstantsEditor = "true";
  const rows = document.createElement("div");
  rows.className = "system-constants-rows";
  const values = constants && typeof constants === "object" && !Array.isArray(constants)
    ? constants
    : {};
  for (const [name, value] of Object.entries(values)) {
    rows.append(createSystemConstantRow(name, String(value ?? "")));
  }
  const validation = document.createElement("p");
  validation.className = "system-constants-validation";
  validation.dataset.systemConstantsValidation = "true";
  validation.hidden = true;
  validation.setAttribute("role", "alert");
  const add = document.createElement("button");
  add.type = "button";
  add.className = "button-secondary system-constant-add";
  add.textContent = "添加常量";
  add.addEventListener("click", () => {
    const row = createSystemConstantRow();
    rows.append(row);
    row.querySelector("[data-system-constant-name]")?.focus();
  });
  editor.append(rows, validation, add);
  sharedConstants.append(editor);
}
function clearSystemConstantValidation() {
  const validation = sharedConstants.querySelector("[data-system-constants-validation]");
  if (validation) {
    validation.textContent = "";
    validation.hidden = true;
  }
  for (const row of sharedConstants.querySelectorAll("[data-system-constant-row].is-invalid")) {
    row.classList.remove("is-invalid");
  }
  for (const control of sharedConstants.querySelectorAll("[data-system-constant-name].is-invalid")) {
    control.classList.remove("is-invalid");
    control.removeAttribute("aria-invalid");
  }
}
function systemConstantValidationError(message, control, relatedControl = null) {
  const validation = sharedConstants.querySelector("[data-system-constants-validation]");
  if (validation) {
    validation.textContent = message;
    validation.hidden = false;
  }
  for (const candidate of [control, relatedControl]) {
    if (!candidate) continue;
    candidate.classList.add("is-invalid");
    candidate.setAttribute("aria-invalid", "true");
    candidate.closest("[data-system-constant-row]")?.classList.add("is-invalid");
  }
  control?.focus();
  return new Error(message);
}
function collectSharedConstants() {
  clearSystemConstantValidation();
  const constants = {};
  const names = new Map();
  const rows = sharedConstants.querySelectorAll("[data-system-constant-row]");
  for (const row of rows) {
    const nameControl = row.querySelector("[data-system-constant-name]");
    const name = nameControl?.value.trim() || "";
    const value = row.querySelector("[data-system-constant-value]")?.value ?? "";
    if (!name) {
      if (value) {
        throw systemConstantValidationError(
          "公用常量填写了文本值，但没有填写名称。",
          nameControl,
        );
      }
      continue;
    }
    if (!systemConstantNamePattern.test(name)) {
      throw systemConstantValidationError(
        `公用常量名称“${name}”只能使用 1 至 64 个大写字母、数字和下划线。`,
        nameControl,
      );
    }
    if (Object.hasOwn(constants, name)) {
      throw systemConstantValidationError(
        `公用常量名称“${name}”重复。`,
        nameControl,
        names.get(name),
      );
    }
    constants[name] = value;
    names.set(name, nameControl);
  }
  return constants;
}
function renderSystemSettings(payload) {
  systemSettings.replaceChildren();
  systemSettingsSchema = payload.schema || {};
  systemSettingsDraft = structuredClone(payload.settings || {});
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
          : groupKey === "session_control"
            ? parseUmoList(control.value)
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
    item.classList.toggle("is-pending-deletion", pendingRuleDeletionIds.has(rule.rule_id));
    title.textContent = rule.rule_id || "未命名规则";
    summaryText.textContent = ruleSummary(rule);
    chip.className = "template-chip";
    chip.textContent =
      templateDescriptions[rule.template_key] || rule.template_key || "未选择模板";
    item.append(title, summaryText, chip);
    if (pendingRuleDeletionIds.has(rule.rule_id)) {
      const pendingMarker = document.createElement("span");
      pendingMarker.className = "rule-pending-deletion-marker";
      pendingMarker.textContent = "待删除 · 点击取消";
      item.append(pendingMarker);
    }
    item.addEventListener("click", () => {
      if (pendingRuleDeletionIds.has(rule.rule_id)) {
        pendingRuleDeletionIds.delete(rule.rule_id);
        publishReport(`已取消删除规则“${rule.rule_id}”。`);
        renderRuleList();
        return;
      }
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
function customPolicies() { return policyLibrary.policies; }
function renderPolicyList() {
  policyList.replaceChildren();
  const policies = customPolicies();
  policyCount.textContent = String(policies.length);
  renderDefaultPolicySummary(policies);
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
    const componentCount = Array.isArray(policy.components) ? policy.components.length : 0;
    const umoCount = Array.isArray(policy.umo_list) ? policy.umo_list.length : 0;
    metadata.textContent = `${bindingCount} 条规则 · ${componentCount} 个元件 · ${umoCount} 个 UMO`;
    item.append(title, description, metadata);
    item.addEventListener("click", () => showPolicyDetail(policy.policy_id));
    policyList.append(item);
  }
}
const policyStepDefinitions = [
  { rail: "input_rail", title: "Step 1 · 输入分析", fields: [
    ["enabled", "启用 Step 1", "boolean"], ["max_text_chars", "最大检查字符数", "number"],
    ["default_llm_provider", "默认辅助 Provider", "provider"], ["default_action_on_hit", "默认命中动作", "select", ["observe", "block"]],
    ["default_action_on_error", "默认错误动作", "select", ["discard", "record", "block"]], ["block_message", "阻断提示", "text"],
    ["output_redirect_template", "输出重定向", "text"],
  ] },
  { rail: "routing_rail", title: "Step 2 · 模型路由", fields: [["enabled", "启用 Step 2", "boolean"]] },
  { rail: "request_rail", title: "Step 3 · 请求审查", fields: [
    ["enabled", "启用 Step 3", "boolean"], ["max_text_chars", "最大检查字符数", "number"],
    ["default_llm_provider", "默认辅助 Provider", "provider"], ["default_action_on_hit", "默认命中动作", "select", ["observe", "block"]],
    ["default_action_on_error", "默认错误动作", "select", ["discard", "record", "block"]], ["block_message", "阻断提示", "text"],
    ["output_redirect_template", "输出重定向", "text"],
  ] },
  { rail: "prompt_rail", title: "Step 4 · 提示词强化", fields: [["enabled", "启用 Step 4", "boolean"]] },
  { rail: "output_rail", title: "Step 5 · 输出检查", fields: [
    ["enabled", "启用 Step 5", "boolean"], ["max_text_chars", "最大检查字符数", "number"],
    ["default_llm_provider", "默认辅助 Provider", "provider"], ["max_retries", "最大重试次数", "number"],
    ["default_action_on_hit", "默认命中动作", "select", ["block", "retry_generation"]], ["default_action_on_error", "默认错误动作", "select", ["discard", "record", "block"]],
    ["block_message", "阻断提示", "text"], ["output_redirect_template", "输出重定向", "text"],
  ] },
];
const policyStepSettingHints = {
  enabled: "关闭后，该 Step 中的所有规则与电子元件都不会执行。",
  max_text_chars: "限制该 Step 每次送入检查的文本长度；留空沿用系统设置。",
  default_llm_provider: "该 Step 的 LLM 类规则默认使用的辅助 Provider；留空沿用系统设置。",
  max_retries: "仅 Step 5 使用；限制 retry_generation 的最大重试次数；留空沿用系统设置。",
  default_action_on_hit: "留空时沿用规则或系统默认动作（default）。",
  default_action_on_error: "留空时沿用规则或系统默认动作（default）。",
  block_message: "该 Step 阻断请求或输出时使用的提示；支持 ${user_id} 和 ${step_number}；留空沿用系统设置。",
  output_redirect_template: "阶段结束时唯一允许提交给 AstrBot 的文本模板。origin 是不可变快照：Step 1 可用 ${event_origin}；Step 3 还可用 ${req_origin}；Step 5 还可用 ${res_origin}。默认模板分别为 ${event_origin}、${req_origin}、${res_origin}。",
};
// Canvas does not inherit CSS custom properties. Keep its palette explicit and
// six-digit so lane color alpha suffixes (for grid and selection overlays) stay valid.
const policyGraphPalette = Object.freeze({
  disabled: "#71837e",
  disabledFill: "#111a18",
  disabledLabel: "#a7bbb5",
  disabledBorder: "#61746e",
  fallbackEdge: "#a2b8b0",
  logicEdge: "#c8ddd5",
  invalid: "#ff6d7a",
  warning: "#ffd166",
  warningLabel: "#ffe2a0",
  unavailable: "#ff6472",
  unavailableLabel: "#ffabb3",
  normalGlow: "#ffffff",
  selectedRing: "#ffffff",
  candidateGlow: "#61dfb5",
  candidateRing: "#9bf1d2",
  label: "#e1f0ea",
  collapsedLabel: "#c5d9d2",
});
const policyGraphSteps = [
  { rail: "input_rail", step: 1, label: "Step 1 · 输入分析", color: "#ff7d8a", fill: "#29171b" },
  { rail: "routing_rail", step: 2, label: "Step 2 · 模型路由", color: "#f6b35c", fill: "#2d2216" },
  { rail: "request_rail", step: 3, label: "Step 3 · 请求审查", color: "#e5d274", fill: "#292715" },
  { rail: "prompt_rail", step: 4, label: "Step 4 · 提示词增强", color: "#6ed8b4", fill: "#123025" },
  { rail: "output_rail", step: 5, label: "Step 5 · 输出检查", color: "#79b9ff", fill: "#132940" },
];
const supportedTemplatesByRail = {
  input_rail: new Set(["plain_keywords", "regex_pattern", "contains_request_user_id", "rag_judge", "llm_review"]),
  request_rail: new Set(["plain_keywords", "regex_pattern", "rag_judge", "llm_review"]),
  prompt_rail: new Set(["strengthen_prompt"]),
  routing_rail: new Set(["route_policy"]),
  output_rail: new Set(["plain_keywords", "regex_pattern", "rag_judge", "llm_review", "format_violation_detector", "poor_quality_detector", "metadata_leakage_detector", "refusal_leakage_detector", "language_drift_detector", "sensitive_echo_detector"]),
};
const inputRedirectTemplates = new Set([
  "plain_keywords",
  "regex_pattern",
  "rag_judge",
  "llm_review",
  "encoded_payload_detector",
  "length_anomaly_detector",
  "role_marker_spoofing_detector",
  "external_fetch_detector",
  "instruction_override_detector",
]);
const componentDefinitions = {
  logic_gate: {
    label: "逻辑门",
    description: "组合当前策略内节点结果；带 payload 字段的输入还可按顺序汇集首个值或拼接文本。",
    rails: new Set(policyGraphSteps.map((step) => step.rail)),
    defaultConfig: () => ({
      gate: "all",
      invert: false,
      inputs: [],
      value_item_template: "${value}",
      value_separator: "\n",
    }),
  },
  encoded_payload_detector: {
    label: "编码载荷检测器",
    description: "检测长编码段、转义、字节序列、显式 ROT13 包装与零宽字符；只判断混淆结构。",
    rails: new Set(["input_rail", "request_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "编码形态扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "min_base64_chars", label: "Base64 最小长度", hint: "达到该长度的连续候选段才检查。", type: "integer", default: 80 },
      { key: "min_base64_distinct_chars", label: "Base64 最少字符种类", hint: "用于排除长重复字母等普通文本。", type: "integer", default: 4 },
      { key: "min_percent_escape_count", label: "百分号转义最少单元", hint: "连续 %HH 单元达到该数量才计入。", type: "integer", default: 8 },
      { key: "min_unicode_escape_count", label: "Unicode 转义最少单元", hint: "连续 Unicode escape 达到该数量才计入。", type: "integer", default: 6 },
      { key: "min_hex_bytes", label: "Hex 字节最少数量", hint: "带分隔符或 0x 前缀的字节对数量。", type: "integer", default: 24 },
      { key: "min_rot13_chars", label: "ROT13 最小长度", hint: "只检查显式 rot13 包装内达到该长度的字母段。", type: "integer", default: 32 },
      { key: "min_encoded_ratio", label: "单段强命中覆盖率", hint: "单一合法候选覆盖文本达到该比例时可独立命中。", type: "number", default: 0.35 },
      { key: "min_zero_width_chars", label: "零宽字符最少数量", hint: "达到该数量后才计算零宽字符比例。", type: "integer", default: 8 },
      { key: "min_zero_width_ratio", label: "零宽字符最小比例", hint: "同时达到数量和比例时可独立命中。", type: "number", default: 0.02 },
      { key: "max_candidate_segments", label: "最多候选段", hint: "限制本次扫描的候选段数量。", type: "integer", default: 32 },
      { key: "max_decode_bytes", label: "候选解码字节上限", hint: "仅作格式验证；解码文本不会保存或传递。", type: "integer", default: 4096 },
      { key: "min_signal_families", label: "最少编码形态", hint: "未满足单段强命中时，至少需要多少种形态。", type: "integer", default: 2 },
      { key: "detect_base64", label: "检测 Base64", hint: "识别长且格式合法的 Base64 候选段。", type: "boolean", default: true },
      { key: "detect_percent_encoding", label: "检测百分号转义", hint: "识别连续 URL 百分号转义单元。", type: "boolean", default: true },
      { key: "detect_unicode_escape", label: "检测 Unicode 转义", hint: "识别连续 Unicode escape 单元。", type: "boolean", default: true },
      { key: "detect_hex", label: "检测 Hex 字节序列", hint: "识别带分隔符或 0x 前缀的字节对序列。", type: "boolean", default: true },
      { key: "detect_rot13_wrapper", label: "检测 ROT13 包装", hint: "只识别显式 rot13: 或 rot13(...) 包装。", type: "boolean", default: true },
      { key: "detect_zero_width", label: "检测零宽字符", hint: "统计 Unicode 格式字符的数量与比例。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, min_base64_chars: 80, min_base64_distinct_chars: 4, min_percent_escape_count: 8, min_unicode_escape_count: 6, min_hex_bytes: 24, min_rot13_chars: 32, min_encoded_ratio: 0.35, min_zero_width_chars: 8, min_zero_width_ratio: 0.02, max_candidate_segments: 32, max_decode_bytes: 4096, min_signal_families: 2, detect_base64: true, detect_percent_encoding: true, detect_unicode_escape: true, detect_hex: true, detect_rot13_wrapper: true, detect_zero_width: true }),
  },
  length_anomaly_detector: {
    label: "长度异常检测器",
    description: "检测超长、重复、异常分隔符与不可见字符等输入形态；不判断文本语义。",
    rails: new Set(["input_rail", "request_rail"]),
    fields: [
      { key: "hard_max_chars", label: "硬长度上限", hint: "达到该字符数立即命中。", type: "integer", default: 8000 },
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "形态扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "max_code_fence_pairs", label: "代码围栏对数", hint: "超过该数量作为一个结构信号。", type: "integer", default: 6 },
      { key: "max_separator_run", label: "分隔符连续长度", hint: "超过该长度作为一个结构信号。", type: "integer", default: 48 },
      { key: "max_repeat_run", label: "重复字符连续长度", hint: "超过该长度作为一个结构信号。", type: "integer", default: 80 },
      { key: "duplicate_line_min_chars", label: "重复行最小长度", hint: "只统计达到该长度的非空行。", type: "integer", default: 16 },
      { key: "duplicate_line_min_count", label: "重复行最少次数", hint: "达到该次数才视为重复行信号。", type: "integer", default: 4 },
      { key: "duplicate_line_ratio", label: "重复行比例", hint: "相同长行的最高占比阈值。", type: "number", default: 0.66 },
      { key: "min_invisible_chars", label: "不可见字符最少数量", hint: "达到该数量后才计算不可见字符比例。", type: "integer", default: 8 },
      { key: "max_invisible_ratio", label: "不可见字符比例", hint: "超过该比例作为一个结构信号。", type: "number", default: 0.04 },
      { key: "min_structural_signals", label: "最少结构信号", hint: "未超硬长度时需要满足的信号数量。", type: "integer", default: 2 },
    ],
    defaultConfig: () => ({ hard_max_chars: 8000, scan_limit_chars: 12000, max_code_fence_pairs: 6, max_separator_run: 48, max_repeat_run: 80, duplicate_line_min_chars: 16, duplicate_line_min_count: 4, duplicate_line_ratio: 0.66, min_invisible_chars: 8, max_invisible_ratio: 0.04, min_structural_signals: 2 }),
  },
  external_fetch_detector: {
    label: "外部资源操作检测器",
    description: "检测外部资源与读取、导入、执行或外传动作的组合；不访问链接。",
    rails: new Set(["input_rail", "request_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "资源与动作结构扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "max_resources", label: "最多外部资源", hint: "限制本次扫描的 URL 或远程图片数量。", type: "integer", default: 24 },
      { key: "max_action_gap_chars", label: "动作邻近距离", hint: "动作与资源相距不超过该字符数才形成关系。", type: "integer", default: 120 },
      { key: "min_evidence", label: "最少关系证据", hint: "资源与动作关系的最少证据数量。", type: "integer", default: 2 },
      { key: "detect_http_resources", label: "检测 HTTP 资源", hint: "识别 http、https 和协议相对 URL。", type: "boolean", default: true },
      { key: "detect_markdown_remote_image", label: "检测远程 Markdown 图片", hint: "识别 Markdown 中的远程图片目标。", type: "boolean", default: true },
      { key: "detect_command_fetch", label: "检测拉取并执行命令", hint: "识别 curl/wget/IWR 拉取后交给解释器执行的同一行结构。", type: "boolean", default: true },
      { key: "detect_prompt_import", label: "检测提示词导入", hint: "识别外部资源、读取动作与提示词／指令目标的组合。", type: "boolean", default: true },
      { key: "detect_external_transfer", label: "检测外部传递", hint: "识别资源与发送、上传、转发等动作的组合。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, max_resources: 24, max_action_gap_chars: 120, min_evidence: 2, detect_http_resources: true, detect_markdown_remote_image: true, detect_command_fetch: true, detect_prompt_import: true, detect_external_transfer: true }),
  },
  role_marker_spoofing_detector: {
    label: "角色标记伪造检测器",
    description: "检测伪造角色、消息包络、工具调用与保留分隔符的组合结构。",
    rails: new Set(["input_rail", "request_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "结构扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "min_indicators", label: "最少结构指标", hint: "至少满足多少种独立指标才命中。", type: "integer", default: 2 },
      { key: "max_lines", label: "扫描最大行数", hint: "只分析窗口中的前若干行。", type: "integer", default: 160 },
      { key: "detect_serialized_message_envelope", label: "检测消息包络", hint: "识别序列化消息结构。", type: "boolean", default: true },
      { key: "detect_tool_invocation_envelope", label: "检测工具包络", hint: "识别工具调用结构。", type: "boolean", default: true },
      { key: "detect_reserved_delimiters", label: "检测保留分隔符", hint: "识别成对协议分隔符。", type: "boolean", default: true },
      { key: "detect_log_like_headers", label: "检测伪日志头", hint: "只在角色头共现时视为独立结构指标。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, min_indicators: 2, detect_serialized_message_envelope: true, detect_tool_invocation_envelope: true, detect_reserved_delimiters: true, detect_log_like_headers: true }),
  },
  instruction_override_detector: {
    label: "指令覆盖检测器",
    description: "检测覆盖约束、索取隐藏内容与冒充权限的显性组合意图。",
    rails: new Set(["input_rail", "request_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "意图结构扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "min_evidence", label: "最少证据", hint: "满足多少类意图证据才命中。", type: "integer", default: 2 },
      { key: "max_token_gap", label: "最大邻近距离", hint: "操作与目标在文本中的最大邻近范围。", type: "integer", default: 12 },
      { key: "detect_instruction_replacement", label: "检测指令替换", hint: "检测覆盖既有约束的结构。", type: "boolean", default: true },
      { key: "detect_hidden_content_request", label: "检测隐藏内容索取", hint: "检测索取受保护内容的结构。", type: "boolean", default: true },
      { key: "detect_authority_claim", label: "检测权限冒充", hint: "检测伪造高权限的结构。", type: "boolean", default: true },
      { key: "detect_role_reassignment", label: "检测角色重设", hint: "仅在同时存在覆盖既有约束意图时命中。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, min_evidence: 2, max_token_gap: 12, detect_instruction_replacement: true, detect_hidden_content_request: true, detect_authority_claim: true, detect_role_reassignment: true }),
  },
  context_extractor: {
    label: "对话上下文提取器",
    description: "读取当前 AstrBot 对话分支的既有历史，产出仅供后续检查内容重定向使用的中性上下文数据；不构成风险命中。",
    rails: new Set(["input_rail", "request_rail", "output_rail"]),
    fields: [
      { key: "turns", label: "历史用户轮次", hint: "0 表示不读取历史；正整数取最近 N 个用户轮次。实际文本始终受 12,000 字符系统上限约束。", type: "integer", default: 3 },
      { key: "user_only", label: "仅保留用户消息", hint: "开启后省略同轮 Bot 回复；system、tool、空和损坏历史仍以中性说明保留。", type: "boolean", default: false },
    ],
    defaultConfig: () => ({ turns: 3, user_only: false }),
    defaultAction: "observe",
  },
  format_violation_detector: {
    label: "输出格式违约检测器",
    description: "从最终请求提取明确的 JSON、单行、纯文本或代码围栏要求，并只做确定性结构校验；不要求手填预期格式，建议交给输出 LLM 旁审裁决语境。",
    rails: new Set(["output_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "请求和候选回复分别使用的最大文本窗口。", type: "integer", default: 12000 },
      { key: "max_contract_candidates", label: "最大格式合同候选数", hint: "一次只处理有限数量的明确格式命令；达到上限时仅记录扫描受限。", type: "integer", default: 8 },
      { key: "allow_surrounding_whitespace", label: "允许首尾空白", hint: "启用时，JSON 和可见行数校验忽略回复的首尾空白。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, max_contract_candidates: 8, allow_surrounding_whitespace: true }),
    defaultAction: "observe",
  },
  poor_quality_detector: {
    label: "异常低质回复检测器",
    description: "检测空白、纯标点、长重复、重复长行和未格式化错误包络；不评价回答内容或风格。",
    rails: new Set(["output_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "回复形态扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "min_visible_chars", label: "最少可见字符", hint: "少于该数量的非空白内容视为空回复。", type: "integer", default: 1 },
      { key: "max_punctuation_ratio", label: "纯标点比例", hint: "可见字符中标点达到该比例时作为低质信号。", type: "number", default: 0.95 },
      { key: "min_repeat_run", label: "重复字符连续长度", hint: "达到该长度的同字符连续段作为低质信号。", type: "integer", default: 80 },
      { key: "duplicate_line_min_chars", label: "重复行最小长度", hint: "只统计达到该长度的非空行。", type: "integer", default: 16 },
      { key: "duplicate_line_min_count", label: "重复行最少次数", hint: "同一长行达到该次数作为低质信号。", type: "integer", default: 4 },
      { key: "min_signal_families", label: "最少低质信号", hint: "需要同时满足的独立形态数量。", type: "integer", default: 1 },
      { key: "detect_unformatted_error_envelope", label: "检测未格式化错误包络", hint: "识别完整 traceback、异常头或结构化错误对象。", type: "boolean", default: true },
      { key: "ignore_fenced_code", label: "忽略代码围栏", hint: "不把教学代码或错误示例当作异常回复。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, min_visible_chars: 1, max_punctuation_ratio: 0.95, min_repeat_run: 80, duplicate_line_min_chars: 16, duplicate_line_min_count: 4, min_signal_families: 1, detect_unformatted_error_envelope: true, ignore_fenced_code: true }),
  },
  metadata_leakage_detector: {
    label: "运行时工件泄漏检测器",
    description: "识别完整 traceback、工具调用包络或内部控制标记等机器运行时工件候选；不按技术术语或普通 JSON 命中。建议交给 LLM 旁审作语境裁决。",
    rails: new Set(["output_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "机器工件结构扫描的最大窗口。", type: "integer", default: 12000 },
      { key: "max_structures", label: "最大 JSON 结构数", hint: "最多解析的平衡 JSON 对象数量，达到上限时只报告扫描受限。", type: "integer", default: 24 },
      { key: "ignore_fenced_code", label: "忽略代码围栏", hint: "默认不把围栏中的 traceback 或调用示例当作运行时泄漏候选。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, max_structures: 24, ignore_fenced_code: true }),
    defaultAction: "observe",
  },
  refusal_leakage_detector: {
    label: "拒答内部边界泄漏检测器",
    description: "识别拒答同时解释 system、developer、tool 指令或其他内部边界的风险候选；普通拒答和一般安全说明不会单独命中，建议由输出 LLM 旁审结合语境裁决。",
    rails: new Set(["output_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "对候选回复使用的最大文本窗口。", type: "integer", default: 12000 },
      { key: "max_relation_gap_chars", label: "拒答与边界最大关系距离", hint: "拒答姿态和内部边界锚点相距不超过该字符数时，才作为同一说明关系评估。", type: "integer", default: 160 },
      { key: "min_evidence_families", label: "最少证据族数", hint: "默认要求拒答和内部边界两类；设为 3 时还要求明确的因果或依据连接词。", type: "integer", default: 2 },
      { key: "ignore_fenced_code", label: "忽略代码围栏", hint: "默认不把代码或教学示例中的拒答文本当作候选。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, max_relation_gap_chars: 160, min_evidence_families: 2, ignore_fenced_code: true }),
    defaultAction: "observe",
  },
  language_drift_detector: {
    label: "对话语言漂移检测器",
    description: "从最终请求中的明确回答语言命令或主导文字脚本推断期望，检测整体脚本漂移与连续异脚本文字污染；不要求预设语言，建议交给输出 LLM 旁审作语境裁决。",
    rails: new Set(["output_rail"]),
    fields: [
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "请求与回复分别使用的最大文本窗口。", type: "integer", default: 12000 },
      { key: "min_analyzable_chars", label: "最少可分析文字数", hint: "请求或回复达到该自然语言字符数后，才允许形成语言漂移候选。", type: "integer", default: 80 },
      { key: "dominant_script_ratio", label: "主导脚本比例", hint: "用于确认请求基线、整体输出漂移和局部污染前的主导语言比例。", type: "number", default: 0.7 },
      { key: "max_baseline_script_ratio", label: "整体漂移时的基线脚本上限", hint: "候选回复若仍保留超过此比例的期望脚本，不作为整体漂移候选。", type: "number", default: 0.2 },
      { key: "min_foreign_script_run_chars", label: "异脚本连续最小长度", hint: "总体语言合格时，连续达到该长度的非期望文字脚本才形成污染候选。", type: "integer", default: 4 },
      { key: "ignore_fenced_code", label: "忽略代码围栏", hint: "不把 fenced code 中的多语言示例作为语言漂移证据。", type: "boolean", default: true },
      { key: "ignore_inline_code", label: "忽略行内代码", hint: "不把反引号包裹的技术 token 或示例作为语言漂移证据。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ scan_limit_chars: 12000, min_analyzable_chars: 80, dominant_script_ratio: 0.7, max_baseline_script_ratio: 0.2, min_foreign_script_run_chars: 4, ignore_fenced_code: true, ignore_inline_code: true }),
    defaultAction: "observe",
  },
  sensitive_echo_detector: {
    label: "风险信号复判",
    description: "自动复判本轮全部已命中的 Step 1/3 可重放规则是否也命中最终输出；可按节点 ID 跳过个别来源，不做片段相似度或语义泄漏推断。",
    rails: new Set(["output_rail"]),
    fields: [
      { key: "skip_source_node_ids", label: "跳过来源规则节点 ID", hint: "可选。每行一个不参与复判的同策略 Step 1/3 可重放规则节点 ID；其余本轮命中来源自动复判。", type: "list", default: [] },
      { key: "scan_limit_chars", label: "扫描字符上限", hint: "复判输出时使用的最大文本窗口。", type: "integer", default: 12000 },
      { key: "min_rechecked_sources", label: "最少复判命中来源", hint: "达到该数量的来源规则在输出上再次命中才命中。", type: "integer", default: 1 },
      { key: "max_rechecked_sources", label: "最大来源复判数", hint: "运行时按节点 ID 稳定排序后，最多复判该数量的未跳过命中来源。", type: "integer", default: 4 },
      { key: "max_external_rechecks", label: "最大外部复判次数", hint: "RAG 与 LLM 来源合计最多重跑次数；超出的来源仅记录为未执行。", type: "integer", default: 2 },
      { key: "ignore_fenced_code", label: "忽略代码围栏", hint: "不把代码示例中的风险文本当作输出复判命中。", type: "boolean", default: true },
    ],
    defaultConfig: () => ({ skip_source_node_ids: [], scan_limit_chars: 12000, min_rechecked_sources: 1, max_rechecked_sources: 4, max_external_rechecks: 2, ignore_fenced_code: true }),
  },
  contains_forward: {
    label: "转发消息检测器",
    description: "检测 AstrBot Forward、Node 或 Nodes 消息段；不展开转发内容。",
    rails: new Set(["input_rail"]),
    defaultConfig: () => ({}),
    defaultAction: "observe",
  },
  contains_file: {
    label: "文件消息检测器",
    description: "检测 AstrBot File 消息段；不下载或解析文件。",
    rails: new Set(["input_rail"]),
    defaultConfig: () => ({}),
    defaultAction: "observe",
  },
  contains_image: {
    label: "图片消息检测器",
    description: "检测 AstrBot Image 消息段；不执行 OCR 或图片理解。",
    rails: new Set(["input_rail"]),
    defaultConfig: () => ({}),
    defaultAction: "observe",
  },
  contains_record: {
    label: "语音消息检测器",
    description: "检测 AstrBot Record 消息段；不进行音频转写。",
    rails: new Set(["input_rail"]),
    defaultConfig: () => ({}),
    defaultAction: "observe",
  },
  contains_video: {
    label: "视频消息检测器",
    description: "检测 AstrBot Video 段，或带视频 MIME／扩展名的 File 段；不下载或分析视频。",
    rails: new Set(["input_rail"]),
    defaultConfig: () => ({}),
    defaultAction: "observe",
  },
};
const policyGraphStepByRail = new Map(
  policyGraphSteps.map((item) => [item.rail, item]),
);
function parsePolicyGraphReference(value) {
  const raw = String(value || "").trim();
  if (!raw) return { raw, targetId: "", mode: "none" };
  const prefix = raw[0] === "!" || raw[0] === "?" || raw[0] === "~" ? raw[0] : "";
  const mode = { "!": "not_matched", "?": "executed", "~": "failed" }[prefix] || "matched";
  let targetAndPath = prefix ? raw.slice(1).trim() : raw;
  const dot = targetAndPath.indexOf(".");
  const allowEmptyString = dot >= 0 && targetAndPath.endsWith("?");
  if (allowEmptyString) targetAndPath = targetAndPath.slice(0, -1);
  const targetId = dot < 0 ? targetAndPath : targetAndPath.slice(0, dot);
  const payloadPath = dot < 0 ? "" : targetAndPath.slice(dot + 1);
  return { raw, targetId, mode, payloadPath, allowEmptyString };
}
function graphNodeInputs(node) {
  const inputs = node?.component?.config?.inputs || node?.rule?.template_config?.inputs;
  return Array.isArray(inputs)
    ? inputs.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}
function graphPriority(nodeData, rule) {
  const value = nodeData?.priority;
  if (Number.isFinite(Number(value))) return Number(value);
  return Number.isFinite(Number(rule?.default_priority)) ? Number(rule.default_priority) : 100;
}
function buildPolicyGraphModel(policy) {
  const ruleById = new Map(
    (Array.isArray(ruleLibrary.rules) ? ruleLibrary.rules : []).map((rule) => [rule.rule_id, rule]),
  );
  const nodes = [];
  const nodeById = new Map();
  const appendNode = ({ id, kind, binding = null, component = null, rule = null }) => {
    const nodeData = component || binding;
    const rail = nodeData?.rail;
    const theme = policyGraphStepByRail.get(rail);
    const stepEnabled = policy?.rail_settings?.[rail]?.enabled !== false;
    const node = {
      id: String(id || ""),
      kind,
      binding,
      component,
      rule,
      rail,
      step: theme?.step || 0,
      theme,
      priority: graphPriority(nodeData, rule),
      enabled: nodeData?.enabled !== false && stepEnabled,
      bindingEnabled: nodeData?.enabled !== false,
      stepEnabled,
      isComponent: kind === "component",
      isLogicGate: component?.component_type === "logic_gate",
      isDirty: policyGraphState.dirtyNodeIds.has(String(id || "")),
      issues: [],
      state: "available",
      depth: 0,
      x: 0,
      y: 0,
    };
    if (kind === "rule" && !rule) node.issues.push({ level: "error", message: "规则库中找不到该规则。" });
    if (kind === "component" && !componentDefinitions[component?.component_type]) {
      node.issues.push({ level: "error", message: "未知电子元件类型。" });
    }
    if (component?.component_type === "logic_gate") {
      const gate = String(component.config?.gate || "all").trim().toLowerCase();
      if (!new Set(["all", "any"]).has(gate)) {
        node.issues.push({ level: "error", message: "逻辑门关系必须为 all 或 any。" });
      }
      if (!graphNodeInputs({ component }).length) {
        node.issues.push({ level: "error", message: "逻辑门至少需要一个输入节点。" });
      }
    }
    if (!theme) node.issues.push({ level: "error", message: "节点绑定到未知 Step。" });
    if (node.id && nodeById.has(node.id)) node.issues.push({ level: "error", message: "节点 ID 与当前策略中的其他节点重复。" });
    nodes.push(node);
    if (node.id && !nodeById.has(node.id)) nodeById.set(node.id, node);
  };
  for (const binding of Array.isArray(policy?.bindings) ? policy.bindings : []) {
    appendNode({
      id: binding.rule_id,
      kind: "rule",
      binding,
      rule: ruleById.get(binding.rule_id) || null,
    });
  }
  for (const component of Array.isArray(policy?.components) ? policy.components : []) {
    appendNode({
      id: component.component_id,
      kind: "component",
      component,
    });
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
    const nodeData = node.component || node.binding;
    if (nodeData?.depend_on) addEdge(node, nodeData.depend_on, "depend_on");
    if (node.isLogicGate) {
      for (const input of graphNodeInputs(node)) addEdge(node, input, "logic_input");
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
  const lanesHeight = policyGraphSteps.reduce((height, step) => (
    height + policyGraphMinimumLaneHeight(step, policyGraphState.model)
  ), 0);
  return Math.max(lanesHeight, policyGraphStage?.clientHeight || 0);
}
function isPolicyGraphNodeVisible(node) {
  return !policyGraphState.collapsedRails.has(node.rail)
    && !policyGraphState.hiddenNodeStates.has(node.state);
}
function renderPolicyGraphStepToggles(model) {
  policyGraphStepToggles.replaceChildren();
  for (const step of policyGraphSteps) {
    const count = model.nodes.filter((node) => node.rail === step.rail).length;
    const collapsed = policyGraphState.collapsedRails.has(step.rail);
    const stepEnabled = model.policy?.rail_settings?.[step.rail]?.enabled !== false;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "policy-graph-step-toggle";
    button.classList.toggle("is-expanded", !collapsed);
    button.classList.toggle("is-collapsed", collapsed);
    button.classList.toggle("is-step-disabled", !stepEnabled);
    button.setAttribute("aria-pressed", String(!collapsed));
    button.textContent = `${step.label}${stepEnabled ? "" : " · 已关闭"} · ${count}`;
    button.addEventListener("click", () => {
      if (collapsed) policyGraphState.collapsedRails.delete(step.rail);
      else {
        policyGraphState.collapsedRails.add(step.rail);
        if (policyGraphState.selectedRail === step.rail) policyGraphState.selectedRail = null;
        if (policyGraphState.model?.nodeById.get(policyGraphState.selectedNodeId)?.rail === step.rail) {
          policyGraphState.selectedNodeId = null;
        }
      }
      renderPolicyGraphStepToggles(model);
      renderPolicyGraphEditor();
      schedulePolicyGraphRender();
    });
    policyGraphStepToggles.append(button);
  }
  const filters = [
    { state: "disabled", label: "未启用" },
    { state: "warning", label: "警告" },
    { state: "unavailable", label: "不可用" },
  ];
  for (const filter of filters) {
    const count = model.nodes.filter((node) => node.state === filter.state).length;
    const hidden = policyGraphState.hiddenNodeStates.has(filter.state);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "policy-graph-step-toggle policy-graph-state-toggle";
    button.classList.toggle("is-expanded", !hidden);
    button.classList.toggle("is-collapsed", hidden);
    button.classList.toggle(`is-${filter.state}`, true);
    button.setAttribute("aria-pressed", String(!hidden));
    button.textContent = `${filter.label} · ${count}`;
    button.title = hidden ? `显示${filter.label}节点` : `隐藏${filter.label}节点`;
    button.addEventListener("click", () => {
      if (hidden) policyGraphState.hiddenNodeStates.delete(filter.state);
      else policyGraphState.hiddenNodeStates.add(filter.state);
      if (policyGraphState.selectedNodeId
        && policyGraphState.model?.nodeById.get(policyGraphState.selectedNodeId)?.state === filter.state
        && !hidden) {
        policyGraphState.selectedNodeId = null;
      }
      renderPolicyGraphStepToggles(model);
      renderPolicyGraphEditor();
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
function policyGraphLayoutKey(width, height) {
  return [
    Math.round(width),
    Math.round(height),
    [...policyGraphState.collapsedRails].sort().join(","),
    [...policyGraphState.hiddenNodeStates].sort().join(","),
  ].join("|");
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
function policyGraphNodesByRail(model) {
  const nodesByRail = new Map(policyGraphSteps.map((step) => [step.rail, []]));
  for (const node of model.nodes) {
    if (isPolicyGraphNodeVisible(node)) nodesByRail.get(node.rail)?.push(node);
  }
  for (const nodes of nodesByRail.values()) {
    nodes.sort((leftNode, rightNode) => (
      leftNode.priority - rightNode.priority || leftNode.id.localeCompare(rightNode.id)
    ));
  }
  return nodesByRail;
}
function policyGraphMinimumLaneHeight(step, model) {
  if (policyGraphState.collapsedRails.has(step.rail)) return 42;
  const nodes = (model?.nodes || []).filter((node) => (
    node.rail === step.rail && isPolicyGraphNodeVisible(node)
  ));
  const { maxRank } = policyGraphLaneRanks(nodes, model);
  // 标题区约 42px，底部和节点半径约 20px；每个依赖层之间至少留出 42px。
  return Math.max(104, 62 + maxRank * 42);
}
function policyGraphNeighborMap(model, visibleNodeIds) {
  const neighbors = new Map([...visibleNodeIds].map((nodeId) => [nodeId, []]));
  for (const edge of model?.edges || []) {
    if (edge.invalid || !edge.source || !edge.target || edge.source === edge.target
      || !visibleNodeIds.has(edge.source.id) || !visibleNodeIds.has(edge.target.id)) continue;
    const distance = Math.max(1, Math.abs(edge.source.step - edge.target.step));
    const weight = 1 / distance;
    neighbors.get(edge.source.id)?.push({ node: edge.target, weight });
    neighbors.get(edge.target.id)?.push({ node: edge.source, weight });
  }
  return neighbors;
}
function policyGraphLaneRanks(nodes, model) {
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const outgoing = new Map(nodes.map((node) => [node.id, new Set()]));
  const incomingCount = new Map(nodes.map((node) => [node.id, 0]));
  for (const edge of model?.edges || []) {
    if (edge.invalid || !edge.source || !edge.target || edge.source.rail !== edge.target.rail
      || !nodeById.has(edge.source.id) || !nodeById.has(edge.target.id)) continue;
    const targets = outgoing.get(edge.source.id);
    if (!targets?.has(edge.target.id)) {
      targets.add(edge.target.id);
      incomingCount.set(edge.target.id, (incomingCount.get(edge.target.id) || 0) + 1);
    }
  }
  const compareNodes = (leftNode, rightNode) => (
    leftNode.priority - rightNode.priority || leftNode.id.localeCompare(rightNode.id)
  );
  const ready = nodes.filter((node) => !incomingCount.get(node.id)).sort(compareNodes);
  const rankById = new Map(nodes.map((node) => [node.id, 0]));
  const processedIds = new Set();
  while (ready.length) {
    const node = ready.shift();
    processedIds.add(node.id);
    for (const targetId of outgoing.get(node.id) || []) {
      rankById.set(targetId, Math.max(
        rankById.get(targetId) || 0,
        (rankById.get(node.id) || 0) + 1,
      ));
      const nextCount = (incomingCount.get(targetId) || 0) - 1;
      incomingCount.set(targetId, nextCount);
      if (!nextCount) {
        ready.push(nodeById.get(targetId));
        ready.sort(compareNodes);
      }
    }
  }
  // 循环依赖本身已标为错误。它不参与硬性分层，以免坏数据挤压合法节点。
  for (const node of nodes) {
    if (!processedIds.has(node.id)) rankById.set(node.id, 0);
  }
  const maxRank = Math.max(0, ...rankById.values());
  return { rankById, maxRank };
}
function clampPolicyGraphNodesInLane(nodes, desired, left, right) {
  if (!nodes.length) return;
  const usableLeft = left + 10;
  const usableRight = Math.max(usableLeft, right - 10);
  if (nodes.length === 1) {
    nodes[0].x = Math.min(
      usableRight,
      Math.max(usableLeft, desired.get(nodes[0].id) ?? (usableLeft + usableRight) / 2),
    );
    return;
  }
  const gap = Math.min(108, (usableRight - usableLeft) / (nodes.length - 1));
  for (let index = 0; index < nodes.length; index += 1) {
    const fallback = usableLeft + (usableRight - usableLeft) * index / (nodes.length - 1);
    const wanted = desired.get(nodes[index].id) ?? fallback;
    const minimum = usableLeft + gap * index;
    const maximum = usableRight - gap * (nodes.length - index - 1);
    nodes[index].x = Math.max(minimum, Math.min(maximum, wanted));
  }
  for (let index = nodes.length - 2; index >= 0; index -= 1) {
    nodes[index].x = Math.min(nodes[index].x, nodes[index + 1].x - gap);
  }
}
function layoutPolicyGraph(model, width, height) {
  const laneLayouts = new Map();
  const expandedSteps = policyGraphSteps.filter(
    (step) => !policyGraphState.collapsedRails.has(step.rail),
  );
  const minimumHeights = new Map(
    policyGraphSteps.map((step) => [step.rail, policyGraphMinimumLaneHeight(step, model)]),
  );
  const minimumTotal = [...minimumHeights.values()].reduce((total, value) => total + value, 0);
  const extraHeight = expandedSteps.length ? Math.max(0, height - minimumTotal) / expandedSteps.length : 0;
  let top = 0;
  for (const step of policyGraphSteps) {
    const collapsed = policyGraphState.collapsedRails.has(step.rail);
    const laneHeight = minimumHeights.get(step.rail) + (collapsed ? 0 : extraHeight);
    laneLayouts.set(step.rail, { step, top, height: laneHeight, collapsed });
    top += laneHeight;
  }
  const left = 92;
  const right = Math.max(left + 90, width - 34);
  const nodesByRail = policyGraphNodesByRail(model);
  const visibleNodeIds = new Set(
    [...nodesByRail.values()].flatMap((nodes) => nodes.map((node) => node.id)),
  );
  const neighbors = policyGraphNeighborMap(model, visibleNodeIds);
  const anchors = new Map();
  const rowsByRail = new Map();
  for (const step of policyGraphSteps) {
    const lane = laneLayouts.get(step.rail);
    if (lane.collapsed) continue;
    const nodes = nodesByRail.get(step.rail) || [];
    const { rankById, maxRank } = policyGraphLaneRanks(nodes, model);
    const rows = new Map();
    for (const node of nodes) {
      const rank = rankById.get(node.id) || 0;
      if (!rows.has(rank)) rows.set(rank, []);
      rows.get(rank).push(node);
    }
    for (const rowNodes of rows.values()) {
      rowNodes.sort((leftNode, rightNode) => (
        leftNode.priority - rightNode.priority || leftNode.id.localeCompare(rightNode.id)
      ));
      rowNodes.forEach((node, index) => {
        anchors.set(node.id, left + (right - left) * (index + .5) / rowNodes.length);
        node.x = anchors.get(node.id);
      });
    }
    const topY = lane.top + 42;
    const bottomY = lane.top + lane.height - 20;
    for (const [rank, rowNodes] of rows) {
      const y = maxRank === 0
        ? topY + 10
        : topY + (bottomY - topY) * rank / maxRank;
      rowNodes.forEach((node) => { node.y = y; });
    }
    rowsByRail.set(step.rail, rows);
  }
  // 同一依赖层保持优先级顺序和最小间距，再向相邻节点横向对齐。
  for (let pass = 0; pass < 18; pass += 1) {
    const currentX = new Map(model.nodes.map((node) => [node.id, node.x]));
    for (const step of policyGraphSteps) {
      const lane = laneLayouts.get(step.rail);
      if (lane.collapsed) continue;
      for (const nodes of rowsByRail.get(step.rail)?.values() || []) {
        const desired = new Map();
        for (const node of nodes) {
          let total = 0;
          let weightTotal = 0;
          for (const item of neighbors.get(node.id) || []) {
            const x = currentX.get(item.node.id);
            if (!Number.isFinite(x)) continue;
            total += x * item.weight;
            weightTotal += item.weight;
          }
          const anchor = anchors.get(node.id) ?? left + (right - left) / 2;
          desired.set(node.id, weightTotal ? anchor * .38 + (total / weightTotal) * .62 : anchor);
        }
        clampPolicyGraphNodesInLane(nodes, desired, left, right);
      }
    }
  }
  return { laneLayouts, width, height };
}
function graphColorForEdge(edge) {
  if (edge.source?.state === "disabled" || edge.target?.state === "disabled") return policyGraphPalette.disabled;
  if (edge.invalid || edge.source?.state === "unavailable" || edge.target?.state === "unavailable") return policyGraphPalette.invalid;
  if (edge.kind === "logic_input") return policyGraphPalette.logicEdge;
  return edge.target?.theme?.color || policyGraphPalette.fallbackEdge;
}
function drawPolicyGraphGrid(context, lane, timestamp, reducedMotion, stepEnabled) {
  const color = stepEnabled ? lane.step.color : policyGraphPalette.disabled;
  context.fillStyle = stepEnabled ? lane.step.fill : policyGraphPalette.disabledFill;
  context.fillRect(0, lane.top, lane.width, lane.height);
  if (policyGraphState.selectedRail === lane.step.rail) {
    context.fillStyle = stepEnabled ? `${lane.step.color}18` : `${policyGraphPalette.disabled}14`;
    context.fillRect(0, lane.top, lane.width, lane.height);
  }
  const offset = reducedMotion || !stepEnabled ? 0 : (timestamp / 7000) % 24;
  context.strokeStyle = stepEnabled ? `${color}35` : `${policyGraphPalette.disabled}22`;
  context.lineWidth = policyGraphState.selectedRail === lane.step.rail ? 1.4 : 1;
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
  context.strokeStyle = stepEnabled ? `${color}aa` : `${policyGraphPalette.disabledBorder}aa`;
  context.strokeRect(.5, lane.top + .5, lane.width - 1, lane.height - 1);
  context.fillStyle = stepEnabled ? color : policyGraphPalette.disabledLabel;
  context.font = "600 14px \"Cascadia Code\", \"JetBrains Mono\", monospace";
  context.fillText(`${lane.step.label}${stepEnabled ? "" : " · 已关闭"}`, 14, lane.top + 22);
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
  const sourceRadius = source.isComponent ? 10 : 8;
  const targetRadius = target.isComponent ? 10 : 8;
  const deltaY = target.y - source.y;
  const direction = Math.sign(deltaY) || 1;
  const startX = source.x;
  const startY = source.y + direction * sourceRadius;
  const endX = target.x;
  const endY = target.y - direction * targetRadius;
  context.beginPath();
  context.moveTo(startX, startY);
  if (Math.abs(deltaY) < sourceRadius + targetRadius + 4) {
    context.lineTo(endX, endY);
  } else {
    const controlY = Math.max(20, Math.abs(endY - startY) * .42);
    context.bezierCurveTo(
      startX, startY + direction * controlY,
      endX, endY - direction * controlY,
      endX, endY,
    );
  }
  context.stroke();
  const angle = Math.abs(deltaY) < sourceRadius + targetRadius + 4
    ? Math.atan2(endY - startY, endX - startX)
    : direction > 0 ? Math.PI / 2 : -Math.PI / 2;
  const size = 6;
  context.setLineDash([]);
  context.beginPath();
  context.moveTo(endX, endY);
  context.lineTo(endX - size * Math.cos(angle - Math.PI / 6), endY - size * Math.sin(angle - Math.PI / 6));
  context.lineTo(endX - size * Math.cos(angle + Math.PI / 6), endY - size * Math.sin(angle + Math.PI / 6));
  context.closePath();
  context.fill();
  context.restore();
}
function graphGlowForNode(node) {
  if (node.state === "disabled") return null;
  if (node.state === "warning") return policyGraphPalette.warning;
  if (node.state === "unavailable") return policyGraphPalette.unavailable;
  return policyGraphPalette.normalGlow;
}
function markPolicyGraphNodeDirty(ruleId) {
  if (ruleId) policyGraphState.dirtyNodeIds.add(String(ruleId));
}
function policyGraphDependencyCandidates(dependentId) {
  const model = policyGraphState.model;
  const dependent = model?.nodeById.get(dependentId);
  if (!model || !dependent) return new Set();
  const outgoing = new Map(model.nodes.map((node) => [node.id, []]));
  for (const edge of model.edges) {
    // Replacing the current ordinary dependency must not disqualify its own target.
    if (edge.kind === "depend_on" && edge.targetId === dependentId) continue;
    if (edge.source && edge.target) outgoing.get(edge.source.id)?.push(edge.target.id);
  }
  const wouldCreateCycle = (sourceId) => {
    const pending = [dependentId];
    const visited = new Set();
    while (pending.length) {
      const current = pending.pop();
      if (current === sourceId) return true;
      if (visited.has(current)) continue;
      visited.add(current);
      pending.push(...(outgoing.get(current) || []));
    }
    return false;
  };
  return new Set(model.nodes.filter((node) => (
    node.id !== dependentId
      && node.enabled
      && node.step <= dependent.step
      && !wouldCreateCycle(node.id)
  )).map((node) => node.id));
}
function cancelPolicyDependencySelection(message = "", isError = false) {
  policyGraphState.dependencySelection = null;
  policyGraphState.pendingDependencySourceId = null;
  policyGraphCanvas.classList.remove("is-dependency-selecting");
  renderPolicyGraphEditor();
  if (message) setPolicyGraphEditorStatus(message, isError);
  schedulePolicyGraphRender();
}
function beginPolicyDependencySelection(dependentId) {
  const candidates = policyGraphDependencyCandidates(dependentId);
  if (!candidates.size) {
    setPolicyGraphEditorStatus("没有可用的依赖项：候选规则必须已启用、位于当前或更早的 Step，且不能形成循环依赖。", true);
    return;
  }
  policyGraphState.dependencySelection = { dependentId };
  policyGraphState.pendingDependencySourceId = null;
  policyGraphCanvas.classList.add("is-dependency-selecting");
  policyGraphState.selectedNodeId = dependentId;
  policyGraphState.selectedRail = null;
  renderPolicyGraphEditor();
  setPolicyGraphEditorStatus(`正在选择依赖项：图中高亮的 ${candidates.size} 个节点可被“${dependentId}”依赖。`);
  schedulePolicyGraphRender();
}
function openPolicyDependencyModeDialog(sourceId) {
  const dependentId = policyGraphState.dependencySelection?.dependentId;
  if (!dependentId) return;
  policyGraphState.pendingDependencySourceId = sourceId;
  policyDependencyMode.value = "matched";
  policyDependencyModeDescription.textContent = `“${dependentId}” 将依赖 “${sourceId}”。请选择何时允许当前规则继续执行。`;
  policyDependencyModeDialog.showModal();
}
function findPolicyGraphDraftNode(nodeId, draft = getPolicyGraphDraft()) {
  const binding = draft?.bindings?.find((item) => item.rule_id === nodeId);
  if (binding) return { kind: "rule", data: binding };
  const component = draft?.components?.find((item) => item.component_id === nodeId);
  if (component) return { kind: "component", data: component };
  return null;
}
function removePolicyGraphDraftNode(nodeId, draft = getPolicyGraphDraft()) {
  if (!draft) return false;
  const bindingCount = draft.bindings?.length || 0;
  const componentCount = draft.components?.length || 0;
  draft.bindings = (draft.bindings || []).filter((binding) => binding.rule_id !== nodeId);
  draft.components = (draft.components || []).filter((component) => component.component_id !== nodeId);
  draft.node_order = (draft.node_order || []).filter((id) => id !== nodeId);
  return draft.bindings.length !== bindingCount || draft.components.length !== componentCount;
}
function applyPolicyDependencySelection() {
  const dependentId = policyGraphState.dependencySelection?.dependentId;
  const sourceId = policyGraphState.pendingDependencySourceId;
  const candidates = dependentId ? policyGraphDependencyCandidates(dependentId) : new Set();
  if (!dependentId || !sourceId || !candidates.has(sourceId)) {
    policyDependencyModeDialog.close();
    cancelPolicyDependencySelection("依赖候选已变化，请重新选择。", true);
    return;
  }
  const draft = getPolicyGraphDraft();
  const node = findPolicyGraphDraftNode(dependentId, draft);
  if (!node) return;
  const prefix = { matched: "", not_matched: "!", executed: "?", failed: "~" }[policyDependencyMode.value] ?? "";
  node.data.depend_on = `${prefix}${sourceId}`;
  markPolicyGraphNodeDirty(dependentId);
  policyDependencyModeDialog.close();
  policyGraphState.dependencySelection = null;
  policyGraphState.pendingDependencySourceId = null;
  policyGraphCanvas.classList.remove("is-dependency-selecting");
  renderPolicyGraph(draft);
  renderPolicyGraphEditor();
  setPolicyGraphEditorStatus(`已暂存依赖：${dependentId} ← ${node.data.depend_on}。点击“保存策略”后写入快照。`);
}
function policyGraphDependentsOf(ruleId) {
  const model = policyGraphState.model;
  if (!model) return [];
  return [...new Set(model.edges
    .filter((edge) => edge.sourceId === ruleId)
    .map((edge) => edge.targetId)
    .filter((id) => id && id !== ruleId))];
}
function requestPolicyBindingRemoval(ruleId) {
  const node = policyGraphState.model?.nodeById.get(ruleId);
  if (!node) return;
  pendingPolicyBindingRemovalId = ruleId;
  const dependents = policyGraphDependentsOf(ruleId);
  const dependentNote = dependents.length
    ? `仍引用它的节点：${dependents.join("、")}。移除后这些节点会保留原依赖，并在图中标红；必须修复后才能保存策略。`
    : node.kind === "component"
      ? "没有其他节点依赖它；移除后该策略内元件将被删除。"
      : "没有其他节点依赖它；移除不会自动修改规则库本体。";
  confirmPolicyBindingRemoveMessage.textContent = `将仅从当前策略移除节点“${ruleId}”。该节点自身的依赖会一并移除。${dependentNote}`;
  confirmPolicyBindingRemoveDialog.showModal();
}
function clearPolicyGraphNodeDependency(nodeId) {
  const draft = getPolicyGraphDraft();
  const currentNode = findPolicyGraphDraftNode(nodeId, draft);
  if (!currentNode?.data?.depend_on) {
    setPolicyGraphEditorStatus("当前节点没有可解除的依赖项。", true);
    return;
  }
  delete currentNode.data.depend_on;
  markPolicyGraphNodeDirty(nodeId);
  renderPolicyGraph(draft);
  renderPolicyGraphEditor();
  setPolicyGraphEditorStatus("已暂存解除依赖项；点击“保存策略”后写入快照。");
}
function removePolicyBinding() {
  const ruleId = pendingPolicyBindingRemovalId;
  const draft = getPolicyGraphDraft();
  if (!ruleId || !draft) return;
  if (!removePolicyGraphDraftNode(ruleId, draft)) return;
  pendingPolicyBindingRemovalId = null;
  confirmPolicyBindingRemoveDialog.close();
  policyGraphState.dependencySelection = null;
  policyGraphState.pendingDependencySourceId = null;
  policyGraphCanvas.classList.remove("is-dependency-selecting");
  renderPolicyGraph(draft, { resetSelection: true });
  renderPolicyGraphEditor();
  const unresolved = policyGraphDependentsOf(ruleId).length;
  setPolicyGraphEditorStatus(
    unresolved
      ? `已暂存移除“${ruleId}”。仍依赖它的节点已标红；请修复它们后再保存策略。`
      : `已暂存从当前策略移除“${ruleId}”；点击“保存策略”后写入快照。`,
    unresolved > 0,
  );
}
function drawPolicyGraphNode(context, node, timestamp, reducedMotion) {
  if (!isPolicyGraphNodeVisible(node)) return;
  const color = node.state === "disabled"
    ? policyGraphPalette.disabled
    : node.state === "unavailable"
      ? policyGraphPalette.unavailable
      : node.state === "warning"
        ? policyGraphPalette.warning
      : node.theme?.color || policyGraphPalette.fallbackEdge;
  const glow = graphGlowForNode(node);
  context.save();
  context.strokeStyle = color;
  context.lineWidth = node.isComponent ? 2.6 : 2.2;
  if (glow) {
    context.shadowColor = glow;
    context.shadowBlur = node.state === "unavailable"
      ? 24
      : node.state === "warning"
        ? 18
        : 10;
  }
  if (node.state === "unavailable" || node.state === "warning") {
    const radius = 9;
    context.beginPath();
    if (node.state === "warning") {
      context.moveTo(node.x - radius, node.y - radius * .8);
      context.lineTo(node.x + radius, node.y - radius * .8);
      context.lineTo(node.x, node.y + radius);
    } else {
      context.moveTo(node.x, node.y - radius);
      context.lineTo(node.x + radius, node.y + radius * .8);
      context.lineTo(node.x - radius, node.y + radius * .8);
    }
    context.closePath();
    context.stroke();
  } else if (node.isComponent) {
    const radius = 8;
    context.beginPath();
    context.moveTo(node.x, node.y - radius);
    context.lineTo(node.x + radius, node.y);
    context.lineTo(node.x, node.y + radius);
    context.lineTo(node.x - radius, node.y);
    context.closePath();
    context.stroke();
    if (node.isLogicGate) {
      context.shadowBlur = 0;
      context.fillStyle = color;
      context.font = "600 9px \"Cascadia Code\", \"JetBrains Mono\", monospace";
      const symbol = node.component?.config?.gate === "any" ? "∨" : "∧";
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(symbol, node.x, node.y + .5);
    }
  } else {
    context.beginPath();
    context.arc(node.x, node.y, 7, 0, Math.PI * 2);
    context.stroke();
  }
  const selected = policyGraphState.selectedNodeId === node.id;
  if (node.isDirty || selected) {
    const phase = selected && !reducedMotion ? (timestamp / 900) % 1 : 0;
    context.shadowBlur = 0;
    context.strokeStyle = policyGraphPalette.selectedRing;
    context.lineWidth = 1.4;
    context.setLineDash([3, 3]);
    context.lineDashOffset = -phase * 12;
    context.beginPath();
    context.arc(node.x, node.y, 13, 0, Math.PI * 2);
    context.stroke();
  }
  const dependentId = policyGraphState.dependencySelection?.dependentId;
  if (dependentId && node.id !== dependentId && policyGraphDependencyCandidates(dependentId).has(node.id)) {
    context.shadowBlur = 10;
    context.shadowColor = policyGraphPalette.candidateGlow;
    context.strokeStyle = policyGraphPalette.candidateRing;
    context.lineWidth = 1.5;
    context.setLineDash([2, 3]);
    context.beginPath();
    context.arc(node.x, node.y, 13, 0, Math.PI * 2);
    context.stroke();
  }
  context.shadowBlur = 0;
  context.setLineDash([]);
  context.fillStyle = node.state === "disabled"
    ? policyGraphPalette.disabled
    : node.state === "unavailable"
      ? policyGraphPalette.unavailableLabel
      : node.state === "warning"
        ? policyGraphPalette.warningLabel
      : policyGraphPalette.label;
  context.font = "500 11px \"Cascadia Code\", \"JetBrains Mono\", monospace";
  context.textAlign = "left";
  context.textBaseline = "alphabetic";
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
  const layoutKey = policyGraphLayoutKey(rect.width, rect.height);
  let layout = policyGraphState.layout;
  if (!layout || layout.model !== model || layout.key !== layoutKey) {
    layout = layoutPolicyGraph(model, rect.width, rect.height);
    layout.model = model;
    layout.key = layoutKey;
    policyGraphState.layout = layout;
  }
  const reducedMotion = policyGraphReducedMotion();
  for (const lane of layout.laneLayouts.values()) {
    lane.width = rect.width;
    const stepEnabled = model.policy?.rail_settings?.[lane.step.rail]?.enabled !== false;
    drawPolicyGraphGrid(context, lane, timestamp, reducedMotion, stepEnabled);
    if (lane.collapsed) {
      const count = model.nodes.filter((node) => node.rail === lane.step.rail).length;
      context.fillStyle = policyGraphPalette.collapsedLabel;
      context.font = "500 11px \"Cascadia Code\", \"JetBrains Mono\", monospace";
      context.fillText(`${count} 个节点已折叠`, rect.width - 88, lane.top + 22);
    }
  }
  for (const edge of model.edges) {
    if (!edge.source || !isPolicyGraphNodeVisible(edge.source) || !isPolicyGraphNodeVisible(edge.target)) continue;
    drawPolicyGraphArrow(context, edge.source, edge.target, edge);
  }
  for (const node of model.nodes) drawPolicyGraphNode(context, node, timestamp, reducedMotion);
}
function policyGraphNodeAt(clientX, clientY) {
  const rect = policyGraphCanvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  return policyGraphState.model?.nodes.find((node) => (
    isPolicyGraphNodeVisible(node)
      && Math.hypot(node.x - x, node.y - y) <= 15
  )) || null;
}
function policyGraphRailAt(clientX, clientY) {
  const rect = policyGraphCanvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  if (x < 0 || x > rect.width || y < 0 || y > rect.height) return null;
  for (const [rail, lane] of policyGraphState.layout?.laneLayouts || []) {
    if (!lane.collapsed && y >= lane.top && y <= lane.top + lane.height) return rail;
  }
  return null;
}
function renderPolicyGraph(policy, { resetSelection = false } = {}) {
  if (resetSelection) {
    policyGraphState.selectedNodeId = null;
    policyGraphState.selectedRail = null;
  }
  policyGraphState.layout = null;
  policyGraphState.model = buildPolicyGraphModel(policy);
  renderPolicyGraphStepToggles(policyGraphState.model);
  const issues = policyGraphState.model.nodes.flatMap((node) => node.issues);
  policyGraphStatus.textContent = issues.length
    ? `图中有 ${issues.length} 项需要处理的问题；保存时以后端校验为准。`
    : `共 ${policyGraphState.model.nodes.length} 个节点、${policyGraphState.model.edges.length} 条依赖。`;
  policyGraphCanvas.classList.toggle("is-interactive", policyGraphState.model.nodes.length > 0);
  policyGraphCanvas.classList.toggle("is-dependency-selecting", Boolean(policyGraphState.dependencySelection));
  updatePolicyGraphAnimation();
}
function createPolicyStepControl(key, type, value, options) {
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
    inherit.textContent = ["default_action_on_hit", "default_action_on_error"].includes(key)
      ? "沿用规则或系统默认动作（default）"
      : "沿用系统设置";
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
function getPolicyGraphDraft(policy = null) {
  const currentPolicy = policy || policyLibrary.policies.find(
    (item) => item.policy_id === selectedPolicyId,
  );
  if (!currentPolicy) return null;
  if (!policyGraphState.draft || policyGraphState.draft.policy_id !== currentPolicy.policy_id) {
    policyGraphState.draft = structuredClone(currentPolicy);
  }
  if (!Array.isArray(policyGraphState.draft.bindings)) policyGraphState.draft.bindings = [];
  if (!Array.isArray(policyGraphState.draft.components)) policyGraphState.draft.components = [];
  if (!Array.isArray(policyGraphState.draft.node_order)) policyGraphState.draft.node_order = [];
  if (!policyGraphState.draft.rail_settings || typeof policyGraphState.draft.rail_settings !== "object") {
    policyGraphState.draft.rail_settings = {};
  }
  return policyGraphState.draft;
}
function policyStepDefinition(rail) {
  return policyStepDefinitions.find((definition) => definition.rail === rail) || null;
}
function setPolicyGraphEditorStatus(message = "", isError = false) {
  if (message) publishReport(message, { tone: isError ? "error" : "success" });
}
function createPolicyGraphEditorField(labelText, hintText, control, fullWidth = false) {
  const label = document.createElement("label");
  if (fullWidth) label.classList.add("full-width");
  const title = document.createElement("span");
  title.textContent = labelText;
  label.append(title);
  if (hintText) label.append(createRuleFieldHint(hintText));
  label.append(control);
  return label;
}
function policyRuleBusinessValue(field, value) {
  if (field.type === "boolean") return value ? "已启用" : "未启用";
  if (field.type === "select") {
    const option = (field.options || []).find(([optionValue]) => optionValue === value);
    return option ? option[1] : String(value ?? "未设置");
  }
  if (field.type === "list") {
    const values = Array.isArray(value) ? value.filter((item) => String(item).trim()) : [];
    return values.length ? values.join("\n") : "未设置";
  }
  const text = String(value ?? "").trim();
  return text || "未设置";
}
function renderPolicyRuleBusinessSummary(rule) {
  const section = document.createElement("section");
  section.className = "policy-rule-business-summary";
  const title = document.createElement("h5");
  title.textContent = "规则业务参数";
  const note = document.createElement("p");
  note.textContent = "规则本体参数仅供核对；如需修改，可直接进入规则库编辑。";
  const grid = document.createElement("div");
  grid.className = "policy-rule-business-grid";
  const config = rule?.template_config || {};
  const fields = templateParameterFields[rule?.template_key] || [];
  for (const field of fields) {
    const item = document.createElement("div");
    item.className = "policy-rule-business-field";
    if (field.fullWidth || field.type === "list" || field.type === "text") item.classList.add("full-width");
    const label = document.createElement("strong");
    label.textContent = field.label;
    const value = document.createElement("pre");
    value.textContent = policyRuleBusinessValue(field, templateConfigValue(config, field));
    item.append(label, value);
    grid.append(item);
  }
  if (!fields.length) {
    const empty = document.createElement("p");
    empty.className = "policy-graph-editor-note";
    empty.textContent = "该模板暂未定义可展示的业务参数。";
    section.append(title, note, empty);
  } else section.append(title, note, grid);
  const openRuleButton = document.createElement("button");
  openRuleButton.type = "button";
  openRuleButton.className = "button-secondary policy-graph-editor-action policy-rule-business-action";
  openRuleButton.textContent = "打开规则本体";
  openRuleButton.addEventListener("click", () => {
    switchTab("rules");
    switchRuleLibrarySection("rules");
    openRule(rule.rule_id);
    renderRuleList();
  });
  section.append(openRuleButton);
  return section;
}
function policyStepControlValue(type, control) {
  if (type === "boolean") return control.checked;
  if (type === "provider") return control.providerValue();
  if (type === "number") return control.value.trim();
  return control.value;
}
function updatePolicyStepSetting(rail, key, type, control) {
  const draft = getPolicyGraphDraft();
  if (!draft) return;
  const settings = draft.rail_settings;
  const railSettings = { ...(settings[rail] || {}) };
  let value = policyStepControlValue(type, control);
  if (type === "number" && value !== "") {
    value = Number(value);
    if (!Number.isFinite(value)) {
      setPolicyGraphEditorStatus("数值设置必须是有效数字。", true);
      return;
    }
  }
  if (value === "") delete railSettings[key];
  else railSettings[key] = value;
  settings[rail] = railSettings;
  setPolicyGraphEditorStatus("修改已暂存；点击“保存策略”后写入快照。");
  renderPolicyGraph(draft);
}
function createPolicyBindingActionSelect(values, value) {
  const select = document.createElement("select");
  const inherit = document.createElement("option");
  inherit.value = "";
  inherit.textContent = "继承规则默认动作";
  select.append(inherit);
  populateRuleActionOptions(select, values);
  ensureOption(select, String(value ?? ""));
  select.value = String(value ?? "");
  return select;
}
function updatePolicyBinding(nodeId, field, control) {
  const draft = getPolicyGraphDraft();
  const node = findPolicyGraphDraftNode(nodeId, draft);
  if (!node) return;
  const binding = node.data;
  if (field === "enabled") {
    binding.enabled = control.checked;
  } else if (field === "priority") {
    const raw = control.value.trim();
    if (!raw) delete binding.priority;
    else if (!Number.isInteger(Number(raw))) {
      setPolicyGraphEditorStatus("优先级必须是整数；留空可继承规则默认优先级。", true);
      return;
    } else binding.priority = Number(raw);
  } else {
    const value = control.value;
    if (!value) delete binding[field];
    else binding[field] = value;
  }
  markPolicyGraphNodeDirty(nodeId);
  setPolicyGraphEditorStatus("修改已暂存；点击“保存策略”后写入快照。");
  renderPolicyGraph(draft);
}
function appendPolicyGraphEditorHeading(container, eyebrow, titleText, descriptionText) {
  const heading = document.createElement("div");
  heading.className = "policy-graph-editor-heading";
  const eyebrowElement = document.createElement("p");
  eyebrowElement.className = "eyebrow";
  eyebrowElement.textContent = eyebrow;
  const title = document.createElement("h4");
  title.textContent = titleText;
  const description = document.createElement("p");
  description.textContent = descriptionText;
  heading.append(eyebrowElement, title, description);
  container.append(heading);
}
function updatePolicyComponentConfig(componentId, key, value) {
  const draft = getPolicyGraphDraft();
  const node = findPolicyGraphDraftNode(componentId, draft);
  if (!node || node.kind !== "component") return;
  node.data.config = { ...(node.data.config || {}), [key]: value };
  markPolicyGraphNodeDirty(componentId);
  setPolicyGraphEditorStatus("元件参数已暂存；点击“保存策略”后写入快照。");
  renderPolicyGraph(draft);
}
function renderPolicyGraphNodeEditor(node) {
  const editor = document.createElement("section");
  editor.className = "policy-graph-editor-card";
  const nodeData = node.component || node.binding;
  const rule = node.rule;
  const templateKey = node.component?.component_type || rule?.template_key || "";
  const isComponent = node.kind === "component";
  appendPolicyGraphEditorHeading(
    editor,
    isComponent ? "POLICY COMPONENT" : "RULE BINDING",
    `${isComponent ? "编辑电子元件" : "编辑规则绑定"} · ${node.id || "未命名节点"}`,
    isComponent
      ? "元件仅属于当前策略，所有参数会随策略快照保存。"
      : rule?.description || "未说明。这里的修改只作用于当前策略，不会修改规则库本体。",
  );
  const summary = document.createElement("div");
  summary.className = "policy-graph-editor-summary";
  const step = policyGraphStepByRail.get(node.rail);
  for (const [label, value] of [
    [isComponent ? "元件 ID" : "规则 ID", node.id || "未命名"],
    [isComponent ? "类型" : "模板", templateDescriptions[templateKey] || componentDefinitions[templateKey]?.label || templateKey || "未知类型"],
    ["所属 Step", step?.label || node.rail],
    ["依赖", nodeData.depend_on || "未设置"],
    ["检查内容", templateKey === "context_extractor" ? "当前对话历史（payload.value）" : (nodeData.inspection_template || "当前阶段原文")],
  ]) {
    const item = document.createElement("span");
    item.textContent = `${label}：${value}`;
    summary.append(item);
  }
  editor.append(summary);
  if (rule) editor.append(renderPolicyRuleBusinessSummary(rule));
  const grid = document.createElement("div");
  grid.className = "form-grid";
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.className = "setting-checkbox";
  enabled.checked = nodeData.enabled !== false;
  enabled.addEventListener("change", () => updatePolicyBinding(node.id, "enabled", enabled));
  grid.append(createPolicyGraphEditorField(
    isComponent ? "启用此元件" : "启用此规则",
    node.stepEnabled ? "关闭后该节点不会执行。" : "当前 Step 已关闭；此开关恢复后仍需重新启用 Step。",
    enabled,
  ));
  const priority = document.createElement("input");
  priority.type = "number";
  priority.step = "1";
  priority.value = nodeData.priority == null ? "" : String(nodeData.priority);
  priority.placeholder = isComponent ? "默认值 100" : `继承规则默认值 ${rule?.default_priority ?? 100}`;
  priority.addEventListener("change", () => updatePolicyBinding(node.id, "priority", priority));
  grid.append(createPolicyGraphEditorField(
    isComponent ? "优先级" : "优先级覆写",
    isComponent ? "数值越小越先执行；默认值为 100。" : "数值越小越先执行；留空继承规则默认优先级。",
    priority,
  ));
  if (inputRedirectTemplates.has(templateKey)) {
    const inputRedirect = document.createElement("textarea");
    inputRedirect.rows = 4;
    inputRedirect.value = nodeData.inspection_template || "";
    inputRedirect.placeholder = "留空使用当前阶段原文";
    inputRedirect.addEventListener("change", () => updatePolicyBinding(
      node.id,
      "inspection_template",
      inputRedirect,
    ));
    grid.append(createPolicyGraphEditorField(
      "检查内容重定向",
      "仅作用于当前策略的这个节点。可引用本阶段可见的 origin 或 ${node_id.field}；缺失引用为空，不等待也不自动建立 depends_on。",
      inputRedirect,
      true,
    ));
  }
  if (isComponent && templateKey === "context_extractor") {
    const fixedAction = document.createElement("input");
    fixedAction.type = "text";
    fixedAction.value = "observe（固定）";
    fixedAction.disabled = true;
    grid.append(createPolicyGraphEditorField(
      "执行语义",
      "该元件永远以 true 表示“上下文已就绪”，只供 depend_on 与检查内容重定向消费；不会执行风险动作。",
      fixedAction,
    ));
    const fixedError = document.createElement("input");
    fixedError.type = "text";
    fixedError.value = "discard（fail-open）";
    fixedError.disabled = true;
    grid.append(createPolicyGraphEditorField(
      "读取失败",
      "读取失败时产出空上下文与诊断，后续节点继续检查其当前阶段对象。",
      fixedError,
    ));
  } else {
    const hitAction = isComponent
      ? createActionSelect(hitActionsForTemplate(templateKey), nodeData.action_on_hit || "default")
      : createPolicyBindingActionSelect(hitActionsForTemplate(templateKey), nodeData.action_on_hit);
    hitAction.addEventListener("change", () => updatePolicyBinding(node.id, "action_on_hit", hitAction));
    grid.append(createPolicyGraphEditorField(
      isComponent ? "命中动作" : "命中动作覆写",
      isComponent ? "元件命中后的处理方式。" : "留空继承规则默认动作；不可用动作已按模板限制隐藏。",
      hitAction,
    ));
    const errorAction = isComponent
      ? createActionSelect(errorActions, nodeData.action_on_error || "default")
      : createPolicyBindingActionSelect(errorActions, nodeData.action_on_error);
    errorAction.addEventListener("change", () => updatePolicyBinding(node.id, "action_on_error", errorAction));
    grid.append(createPolicyGraphEditorField(
      isComponent ? "错误动作" : "错误动作覆写",
      isComponent ? "元件执行失败时的处理方式。" : "留空继承规则默认动作。",
      errorAction,
    ));
  }
  editor.append(grid);
  if (node.isLogicGate) {
    const componentGrid = document.createElement("div");
    componentGrid.className = "form-grid";
    const gate = document.createElement("select");
    for (const [value, label] of [["all", "全部满足（all）"], ["any", "任一满足（any）"]]) {
      const option = document.createElement("option"); option.value = value; option.textContent = label; gate.append(option);
    }
    gate.value = node.component?.config?.gate === "any" ? "any" : "all";
    gate.addEventListener("change", () => updatePolicyComponentConfig(node.id, "gate", gate.value));
    componentGrid.append(createPolicyGraphEditorField("逻辑关系", "决定所有输入都满足还是任一输入满足。", gate));
    const invert = document.createElement("input");
    invert.type = "checkbox";
    invert.className = "setting-checkbox";
    invert.checked = Boolean(node.component?.config?.invert);
    invert.addEventListener("change", () => updatePolicyComponentConfig(node.id, "invert", invert.checked));
    componentGrid.append(createPolicyGraphEditorField("结果取反", "开启后反转逻辑门的计算结果。", invert));
    const inputs = document.createElement("textarea");
    inputs.rows = 3;
    inputs.placeholder = "每行一个：[!|?|~]节点 ID[.payload 字段[?]]";
    inputs.value = graphNodeInputs(node).join("\n");
    inputs.addEventListener("change", () => updatePolicyComponentConfig(
      node.id,
      "inputs",
      inputs.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean),
    ));
    componentGrid.append(createPolicyGraphEditorField(
      "逻辑门输入",
      "每行一个：[!|?|~]节点 ID[.payload 字段[?]]，裸节点只参与布尔判断；带 .字段 的输入在前缀条件成立后读取 payload。尾随 ? 只允许已存在的空字符串。",
      inputs,
      true,
    ));
    const valueItemTemplate = document.createElement("textarea");
    valueItemTemplate.rows = 2;
    valueItemTemplate.value = String(node.component?.config?.value_item_template ?? "${value}");
    valueItemTemplate.placeholder = "${value}";
    valueItemTemplate.addEventListener("change", () => updatePolicyComponentConfig(
      node.id,
      "value_item_template",
      valueItemTemplate.value,
    ));
    componentGrid.append(createPolicyGraphEditorField(
      "payload 项模板",
      "仅用于 joined_string；只允许 ${value}（字段值）与 ${source}（来源节点 ID）。",
      valueItemTemplate,
      true,
    ));
    const valueSeparator = document.createElement("textarea");
    valueSeparator.rows = 2;
    valueSeparator.value = String(node.component?.config?.value_separator ?? "\n");
    valueSeparator.placeholder = "默认换行";
    valueSeparator.addEventListener("change", () => updatePolicyComponentConfig(
      node.id,
      "value_separator",
      valueSeparator.value,
    ));
    componentGrid.append(createPolicyGraphEditorField(
      "payload 拼接分隔符",
      "仅用于 joined_string；默认是换行，可以留空以直接拼接。",
      valueSeparator,
      true,
    ));
    editor.append(componentGrid);
  } else if (isComponent && componentDefinitions[templateKey]?.fields) {
    const componentGrid = document.createElement("div");
    componentGrid.className = "form-grid";
    const config = node.component?.config || {};
    for (const field of componentDefinitions[templateKey].fields) {
      const value = Object.hasOwn(config, field.key) ? config[field.key] : field.default;
      const control = createTemplateParameterControl(field, value);
      control.addEventListener("change", () => {
        let nextValue;
        if (field.type === "boolean") nextValue = control.checked;
        else if (field.type === "list") {
          nextValue = control.value
            .split(/\r?\n/)
            .map((value) => value.trim())
            .filter(Boolean);
        }
        else if (field.type === "integer") {
          const parsed = Number.parseInt(control.value, 10);
          nextValue = Number.isNaN(parsed) ? field.default : parsed;
        } else if (field.type === "number") {
          const parsed = Number.parseFloat(control.value);
          nextValue = Number.isNaN(parsed) ? field.default : parsed;
        } else nextValue = control.value;
        updatePolicyComponentConfig(node.id, field.key, nextValue);
      });
      componentGrid.append(createPolicyGraphEditorField(
        field.label,
        field.hint,
        control,
        Boolean(field.fullWidth),
      ));
    }
    editor.append(componentGrid);
  }
  const dependencyHint = document.createElement("p");
  dependencyHint.className = "policy-graph-editor-note";
  dependencyHint.textContent = nodeData.depend_on
    ? `当前依赖：${nodeData.depend_on}。可重新选择依赖项或移除当前依赖。`
    : "当前未设置依赖。选择依赖项后，再在图中点击高亮的候选节点。";
  editor.append(dependencyHint);
  const dependencyActions = document.createElement("div");
  dependencyActions.className = "policy-graph-editor-actions";
  const selectDependencyButton = document.createElement("button");
  selectDependencyButton.type = "button";
  selectDependencyButton.className = "button-secondary policy-graph-editor-action";
  const selectingDependency = policyGraphState.dependencySelection?.dependentId === node.id;
  selectDependencyButton.textContent = selectingDependency ? "取消选择依赖项 · D" : "选择依赖项 · D";
  selectDependencyButton.addEventListener("click", () => {
    if (selectingDependency) cancelPolicyDependencySelection("已取消依赖项选择。");
    else beginPolicyDependencySelection(node.id);
  });
  dependencyActions.append(selectDependencyButton);
  if (nodeData.depend_on) {
    const clearDependencyButton = document.createElement("button");
    clearDependencyButton.type = "button";
    clearDependencyButton.className = "button-secondary policy-graph-editor-action";
    clearDependencyButton.textContent = "解除依赖项 · ⇧D";
    clearDependencyButton.addEventListener("click", () => clearPolicyGraphNodeDependency(node.id));
    dependencyActions.append(clearDependencyButton);
  }
  editor.append(dependencyActions);
  const removeBindingButton = document.createElement("button");
  removeBindingButton.type = "button";
  removeBindingButton.className = "danger-button policy-graph-editor-action";
  removeBindingButton.textContent = "从当前策略移除 · ⇧Del";
  removeBindingButton.addEventListener("click", () => requestPolicyBindingRemoval(node.id));
  editor.append(removeBindingButton);
  if (node.issues.length) {
    const issue = document.createElement("p");
    issue.className = "form-status";
    issue.textContent = node.issues.map((item) => item.message).join("；");
    editor.append(issue);
  }
  return editor;
}
function availableRulesForPolicyRail(rail) {
  const draft = getPolicyGraphDraft();
  const supportedTemplates = supportedTemplatesByRail[rail] || new Set();
  const boundRuleIds = new Set((draft?.bindings || []).map((binding) => binding.rule_id));
  return ruleLibrary.rules.filter((rule) => (
    !pendingRuleDeletionIds.has(rule.rule_id)
    && supportedTemplates.has(rule.template_key) && !boundRuleIds.has(rule.rule_id)
  ));
}
function renderPolicyRulePicker(rail) {
  const definition = policyStepDefinition(rail);
  const rules = availableRulesForPolicyRail(rail);
  policyRulePickerTitle.textContent = `添加已有规则 · ${definition?.title || rail}`;
  policyRulePickerDescription.textContent = "仅显示与当前 Step 兼容、且尚未加入此策略的规则。可一次添加多条；新节点会先留在策略草稿中。";
  policyRulePickerStatus.textContent = rules.length ? "" : "没有可添加的规则。可先到规则库创建兼容的规则。";
  policyRulePickerList.replaceChildren();
  for (const rule of rules) {
    const item = document.createElement("label");
    item.className = "policy-rule-picker-item";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = rule.rule_id;
    const body = document.createElement("span");
    const heading = document.createElement("strong");
    heading.textContent = rule.rule_id;
    const template = document.createElement("span");
    template.className = "policy-rule-picker-template";
    template.textContent = templateDescriptions[rule.template_key] || rule.template_key;
    const description = document.createElement("span");
    description.className = "policy-rule-picker-description";
    description.textContent = String(rule.description || "").trim() || "未说明";
    body.append(heading, template, description);
    item.append(checkbox, body);
    policyRulePickerList.append(item);
  }
  confirmPolicyRulePicker.disabled = !rules.length;
}
function openPolicyRulePicker(rail) {
  if (!getPolicyGraphDraft() || !supportedTemplatesByRail[rail]) return;
  pendingPolicyBindingRail = rail;
  renderPolicyRulePicker(rail);
  policyRulePickerDialog.showModal();
}
function addSelectedPolicyRules() {
  const rail = pendingPolicyBindingRail;
  const draft = getPolicyGraphDraft();
  if (!rail || !draft) return;
  const selectedRuleIds = [...policyRulePickerList.querySelectorAll("input:checked")]
    .map((input) => input.value);
  if (!selectedRuleIds.length) {
    policyRulePickerStatus.textContent = "请至少选择一条规则。";
    return;
  }
  const availableRuleIds = new Set(availableRulesForPolicyRail(rail).map((rule) => rule.rule_id));
  const validRuleIds = selectedRuleIds.filter((ruleId) => availableRuleIds.has(ruleId));
  if (!validRuleIds.length) {
    policyRulePickerStatus.textContent = "可添加规则已变化，请重新选择。";
    renderPolicyRulePicker(rail);
    return;
  }
  const nodeOrder = completePolicyGraphNodeOrder(draft);
  for (const ruleId of validRuleIds) {
    draft.bindings.push({ rule_id: ruleId, rail, enabled: true });
    nodeOrder.push(ruleId);
    markPolicyGraphNodeDirty(ruleId);
  }
  draft.node_order = nodeOrder;
  policyRulePickerDialog.close();
  pendingPolicyBindingRail = null;
  renderPolicyGraph(draft);
  renderPolicyGraphEditor();
  setPolicyGraphEditorStatus(`已暂存添加 ${validRuleIds.length} 条规则；点击“保存策略”后写入快照。`);
}
function policyGraphDraftNodeIds(draft = getPolicyGraphDraft()) {
  return new Set([
    ...(draft?.bindings || []).map((binding) => binding.rule_id),
    ...(draft?.components || []).map((component) => component.component_id),
  ].filter(Boolean));
}
function completePolicyGraphNodeOrder(draft = getPolicyGraphDraft()) {
  const allIds = [
    ...(draft?.bindings || []).map((binding) => binding.rule_id),
    ...(draft?.components || []).map((component) => component.component_id),
  ].filter(Boolean);
  const allIdSet = new Set(allIds);
  const order = [];
  for (const id of draft?.node_order || []) {
    if (allIdSet.has(id) && !order.includes(id)) order.push(id);
  }
  for (const id of allIds) {
    if (!order.includes(id)) order.push(id);
  }
  return order;
}
function renderPolicyComponentOptions(rail) {
  policyComponentOptions.replaceChildren();
  for (const [type, definition] of Object.entries(componentDefinitions)) {
    if (!definition.rails.has(rail)) continue;
    const option = document.createElement("button");
    option.type = "button";
    option.className = "template-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", String(selectedNewComponentType === type));
    option.classList.toggle("is-selected", selectedNewComponentType === type);
    const title = document.createElement("strong");
    title.textContent = definition.label;
    const description = document.createElement("span");
    description.textContent = definition.description;
    option.append(title, description);
    option.addEventListener("click", () => {
      selectedNewComponentType = type;
      renderPolicyComponentOptions(rail);
    });
    policyComponentOptions.append(option);
  }
}
function renderDefaultPolicySummary(policies = customPolicies()) {
  defaultPolicySummary.replaceChildren();
  const policy = policies.find((item) => item.policy_id === policyLibrary.active_policy_id);
  if (!policy) {
    const description = document.createElement("p");
    description.textContent = "尚未指定默认策略。未匹配到合法策略的请求将直接使用系统 fallback 图，并按系统设置执行兜底检查。";
    defaultPolicySummary.append(description);
    return;
  }
  const title = document.createElement("strong");
  const description = document.createElement("p");
  const actions = document.createElement("div");
  const viewButton = document.createElement("button");
  const clearButton = document.createElement("button");
  title.textContent = policy.name || policy.policy_id || "未命名策略";
  description.textContent = String(policy.description || "").trim() || "未说明";
  actions.className = "default-policy-actions";
  viewButton.type = "button";
  viewButton.className = "button-secondary";
  viewButton.textContent = "查看策略";
  viewButton.addEventListener("click", () => showPolicyDetail(policy.policy_id));
  clearButton.type = "button";
  clearButton.className = "danger-button";
  clearButton.textContent = "取消默认策略";
  clearButton.addEventListener("click", () => clearDefaultPolicyFromList(clearButton));
  actions.append(viewButton, clearButton);
  defaultPolicySummary.append(title, description, actions);
}
async function clearDefaultPolicyFromList(button) {
  const previousDefaultPolicyId = policyLibrary.active_policy_id;
  if (!previousDefaultPolicyId) return;
  policyLibrary.active_policy_id = "";
  button.disabled = true;
  const saved = await persistPolicyLibrary(
    (revision) => `已取消默认策略，revision ${revision}。`,
    { operation: "取消默认策略" },
  );
  if (!saved) {
    policyLibrary.active_policy_id = previousDefaultPolicyId;
  }
  renderPolicyList();
}
function openPolicyComponentCreation(rail) {
  if (!getPolicyGraphDraft()) return;
  pendingPolicyComponentRail = rail;
  selectedNewComponentType = null;
  newPolicyComponentId.value = "";
  policyComponentCreationStatus.textContent = "";
  policyComponentCreationTitle.textContent = `添加电子元件 · ${policyStepDefinition(rail)?.title || rail}`;
  policyComponentCreationDescription.textContent = "电子元件仅属于当前策略，会随策略快照保存；创建后可在节点编辑器中调整全部参数。";
  renderPolicyComponentOptions(rail);
  policyComponentCreationDialog.showModal();
  newPolicyComponentId.focus();
}
function createPolicyComponent() {
  const rail = pendingPolicyComponentRail;
  const type = selectedNewComponentType;
  const id = newPolicyComponentId.value.trim();
  if (!id) {
    policyComponentCreationStatus.textContent = "请输入元件 ID。";
    newPolicyComponentId.focus();
    return;
  }
  if (!/^[a-z][a-z0-9_]{0,63}$/.test(id)) {
    policyComponentCreationStatus.textContent = "元件 ID 必须以小写字母开头，并只包含小写字母、数字和下划线。";
    newPolicyComponentId.focus();
    return;
  }
  const draft = getPolicyGraphDraft();
  if (policyGraphDraftNodeIds(draft).has(id)) {
    policyComponentCreationStatus.textContent = "元件 ID 已被当前策略中的节点使用。";
    newPolicyComponentId.focus();
    return;
  }
  if (!type) {
    policyComponentCreationStatus.textContent = "请选择元件类型。";
    return;
  }
  const definition = componentDefinitions[type];
  if (!rail || !definition?.rails.has(rail)) {
    policyComponentCreationStatus.textContent = "所选元件不适用于当前 Step。";
    return;
  }
  const nodeOrder = completePolicyGraphNodeOrder(draft);
  draft.components = [...(draft.components || []), {
    component_id: id,
    component_type: type,
    rail,
    enabled: true,
    priority: 100,
    action_on_hit: definition.defaultAction || "default",
    action_on_error: "default",
    depend_on: "",
    inspection_template: "",
    config: definition.defaultConfig(),
  }];
  draft.node_order = [...nodeOrder, id];
  markPolicyGraphNodeDirty(id);
  policyComponentCreationDialog.close();
  pendingPolicyComponentRail = null;
  policyGraphState.selectedNodeId = id;
  policyGraphState.selectedRail = null;
  renderPolicyGraph(draft);
  renderPolicyGraphEditor();
  setPolicyGraphEditorStatus(`已暂存添加${definition.label}“${id}”；请完成参数配置后保存策略。`);
}
function renderPolicyGraphStepEditor(rail) {
  const definition = policyStepDefinition(rail);
  const editor = document.createElement("section");
  editor.className = "policy-graph-editor-card";
  if (!definition) {
    appendPolicyGraphEditorHeading(editor, "STEP SETTINGS", "未知 Step", "无法编辑该 Step 的设置。");
    return editor;
  }
  const draft = getPolicyGraphDraft();
  const settings = draft?.rail_settings?.[rail] || {};
  const ruleCount = (draft?.bindings || []).filter((binding) => binding.rail === rail).length;
  const componentCount = (draft?.components || []).filter((component) => component.rail === rail).length;
  const nodeCount = ruleCount + componentCount;
  appendPolicyGraphEditorHeading(
    editor,
    "STEP SETTINGS",
    `编辑 ${definition.title}`,
    `当前 Step 有 ${nodeCount} 个节点（${ruleCount} 条规则、${componentCount} 个元件）。未填写的动作项会沿用规则或系统默认动作（default）；其他项沿用系统设置。`,
  );
  const grid = document.createElement("div");
  grid.className = "form-grid";
  for (const [key, labelText, type, options] of definition.fields) {
    const control = createPolicyStepControl(key, type, settings[key], options);
    const apply = () => updatePolicyStepSetting(rail, key, type, control);
    control.addEventListener("change", apply);
    if (type !== "boolean" && type !== "number") control.addEventListener("input", apply);
    grid.append(createPolicyGraphEditorField(labelText, policyStepSettingHints[key], control));
  }
  editor.append(grid);
  const rulesById = new Map((policyLibrary.rules || []).map((rule) => [rule.rule_id, rule]));
  const sanitizeBindings = (draft?.bindings || []).filter((binding) => {
    if (binding.rail !== rail || binding.enabled === false) return false;
    const rule = rulesById.get(binding.rule_id);
    const action = binding.action_on_hit ?? rule?.default_action_on_hit;
    return action === "sanitize";
  });
  if (sanitizeBindings.length) {
    const notice = document.createElement("div");
    notice.className = "policy-graph-editor-summary";
    const warning = document.createElement("span");
    warning.textContent = "此 Step 含 sanitize 节点；请确认输出重定向是否符合预期。";
    notice.append(warning);
    if (sanitizeBindings.length === 1 && sanitizeBindings[0].rule_id) {
      const ruleId = sanitizeBindings[0].rule_id;
      const suggestion = `\${${ruleId}.sanitized}`;
      const applySuggestion = document.createElement("button");
      applySuggestion.type = "button";
      applySuggestion.className = "button-secondary policy-graph-editor-action";
      applySuggestion.textContent = `建议使用 ${suggestion}`;
      applySuggestion.addEventListener("click", () => {
        const updated = { ...(draft.rail_settings[rail] || {}), output_redirect_template: suggestion };
        draft.rail_settings[rail] = updated;
        setPolicyGraphEditorStatus(`已暂存输出重定向 ${suggestion}；点击“保存策略”后生效。`);
        renderPolicyGraphEditor();
      });
      notice.append(applySuggestion);
    }
    editor.append(notice);
  }
  const addRulesButton = document.createElement("button");
  addRulesButton.type = "button";
  addRulesButton.className = "button-secondary policy-graph-editor-action";
  addRulesButton.textContent = "添加已有规则";
  addRulesButton.addEventListener("click", () => openPolicyRulePicker(rail));
  const addComponentButton = document.createElement("button");
  addComponentButton.type = "button";
  addComponentButton.className = "button-secondary policy-graph-editor-action";
  addComponentButton.textContent = "添加电子元件";
  addComponentButton.addEventListener("click", () => openPolicyComponentCreation(rail));
  const actions = document.createElement("div");
  actions.className = "policy-graph-editor-actions";
  actions.append(addRulesButton, addComponentButton);
  editor.append(actions);
  return editor;
}
function renderPolicyGraphEditor() {
  policyGraphEditor.replaceChildren();
  setPolicyGraphEditorStatus("");
  const draft = getPolicyGraphDraft();
  if (!draft) return;
  const node = policyGraphState.selectedNodeId
    ? policyGraphState.model?.nodeById.get(policyGraphState.selectedNodeId)
    : null;
  if (node) {
    policyGraphEditor.append(renderPolicyGraphNodeEditor(node));
    return;
  }
  if (policyGraphState.selectedRail) {
    policyGraphEditor.append(renderPolicyGraphStepEditor(policyGraphState.selectedRail));
    return;
  }
  const placeholder = document.createElement("div");
  placeholder.className = "policy-graph-editor-placeholder";
  placeholder.textContent = "点击图中的规则节点，或点击某个 Step 的空白处以开始编辑。";
  policyGraphEditor.append(placeholder);
}
function renderPolicyDetail(policy) {
  policyDetailName.textContent = policy.name || policy.policy_id || "未命名策略";
  policyDetailDescription.textContent = String(policy.description || "").trim() || "未说明";
  policyNameInput.value = policy.name || "";
  policyDescriptionInput.value = policy.description || "";
  policyBasicStatus.textContent = "";
  const bindings = Array.isArray(policy.bindings) ? policy.bindings : [];
  const components = Array.isArray(policy.components) ? policy.components : [];
  policyDetailMeta.replaceChildren(
    document.createTextNode("策略 ID："),
    Object.assign(document.createElement("code"), { textContent: policy.policy_id || "未设置" }),
    document.createTextNode(` · 节点：${bindings.length + components.length} 个（规则 ${bindings.length}、元件 ${components.length}）`),
  );
  policyGraphState.draft = structuredClone(policy);
  policyGraphState.dirtyNodeIds.clear();
  renderPolicyGraph(policyGraphState.draft, { resetSelection: true });
  renderPolicyGraphEditor();
  policyUmoList.replaceChildren();
  policyUmoList.umoEditor = createUmoTextarea(policy.umo_list || []);
  policyUmoList.append(policyUmoList.umoEditor);
  const isDefaultPolicy = policy.policy_id === policyLibrary.active_policy_id;
  defaultPolicyIndicator.hidden = !isDefaultPolicy;
  setDefaultPolicy.textContent = isDefaultPolicy ? "取消默认规则" : "设为默认策略";
  setDefaultPolicy.classList.toggle("danger-button", isDefaultPolicy);
  setDefaultPolicy.classList.toggle("button-secondary", !isDefaultPolicy);
  policySessionStatus.textContent = "";
  savePolicyAs.hidden = policy.builtin;
  deletePolicyButton.hidden = policy.builtin;
}
function collectPolicyDetailDraft(policy) {
  const name = policyNameInput.value.trim();
  if (!name) {
    policyBasicStatus.textContent = "请填写策略名称。";
    policyNameInput.focus();
    return null;
  }
  const draft = getPolicyGraphDraft(policy);
  if (!draft) return null;
  const umoEditor = policyUmoList.umoEditor;
  return {
    ...structuredClone(policy),
    name,
    description: policyDescriptionInput.value.trim(),
    bindings: structuredClone(draft.bindings || []),
    components: structuredClone(draft.components || []),
    node_order: completePolicyGraphNodeOrder(draft),
    rail_settings: structuredClone(draft.rail_settings || {}),
    umo_list: typeof umoEditor?.value === "string" ? parseUmoList(umoEditor.value) : [],
  };
}
function validCustomPolicyId(id) {
  return /^[a-z][a-z0-9_]{0,63}$/.test(id);
}
function currentPolicyGraphIssues() {
  return policyGraphState.model?.nodes
    .flatMap((node) => node.issues.map((issue) => `${node.id}：${issue.message}`)) || [];
}
function showPolicySaveIssues(title, messages, intro = "请修复以下问题后再试。") {
  const uniqueMessages = [...new Set(messages.map((message) => String(message || "").trim()).filter(Boolean))];
  policySaveIssuesTitle.textContent = title;
  policySaveIssuesIntro.textContent = intro;
  policySaveIssuesList.replaceChildren();
  for (const message of uniqueMessages.length ? uniqueMessages : ["保存请求未完成，请检查策略配置后重试。"]) {
    const item = document.createElement("li");
    item.textContent = message;
    policySaveIssuesList.append(item);
  }
  if (!policySaveIssuesDialog.open) policySaveIssuesDialog.showModal();
}
function policySaveFailureMessages(result) {
  const messages = [];
  if (Array.isArray(result?.diagnostics)) messages.push(...result.diagnostics);
  if (typeof result?.detail === "string") messages.push(...result.detail.split(/\r?\n/));
  if (!messages.length && result?.error) messages.push(result.error);
  return [...currentPolicyGraphIssues(), ...messages];
}
async function persistPolicyLibrary(successMessage, { showIssues = false, operation = "保存策略" } = {}) {
  if (!Number.isInteger(currentRevision)) return false;
  try {
    const result = await bridge.apiPost("save_policy_library", {
      expected_revision: currentRevision,
      policy_library: policyLibrary,
    });
    if (!result.success) {
      const message = result.detail || result.error || "保存策略失败。";
      policyLibraryStatus.textContent = "";
      publishReport(message, { tone: "error" });
      if (showIssues) showPolicySaveIssues(`${operation}失败`, policySaveFailureMessages(result));
      return false;
    }
    currentRevision = result.revision;
    policyLibraryStatus.textContent = "";
    publishReport(successMessage(result.revision));
    rerenderOverviewIfReady();
    return true;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    policyLibraryStatus.textContent = "";
    publishReport(`保存策略失败：${message}`, { tone: "error" });
    if (showIssues) showPolicySaveIssues(`${operation}失败`, [...currentPolicyGraphIssues(), message]);
    return false;
  }
}
async function saveCurrentPolicy(makeDefault = false, clearDefault = false) {
  const policy = policyLibrary.policies.find((item) => item.policy_id === selectedPolicyId);
  if (!policy) return false;
  const draft = collectPolicyDetailDraft(policy);
  if (!draft) {
    showPolicySaveIssues("策略暂不能保存", [policyBasicStatus.textContent || "策略基本信息不完整。"]);
    return false;
  }
  const previousPolicy = structuredClone(policy);
  const previousDefaultPolicyId = policyLibrary.active_policy_id;
  Object.assign(policy, draft);
  if (makeDefault) policyLibrary.active_policy_id = policy.policy_id;
  if (clearDefault) policyLibrary.active_policy_id = "";
  savePolicy.disabled = true;
  setDefaultPolicy.disabled = true;
  const saved = await persistPolicyLibrary((revision) => makeDefault
    ? `策略“${policy.name || policy.policy_id}”已设为默认策略，revision ${revision}。`
    : clearDefault
      ? `已取消默认策略，revision ${revision}。`
      : `策略“${policy.name || policy.policy_id}”已保存为 revision ${revision}。`, {
    showIssues: true,
    operation: makeDefault ? "设置默认策略" : clearDefault ? "取消默认策略" : "保存策略",
  });
  savePolicy.disabled = false;
  setDefaultPolicy.disabled = false;
  if (!saved) {
    Object.assign(policy, previousPolicy);
    policyLibrary.active_policy_id = previousDefaultPolicyId;
    return false;
  }
  renderPolicyList();
  renderPolicyDetail(policy);
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
  const policy = {
    policy_id: id,
    name,
    description: newPolicyDescription.value.trim(),
    bindings: [],
    components: [],
    node_order: [],
    session_scope: {},
    builtin: false,
  };
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
  const draft = collectPolicyDetailDraft(source);
  const issues = currentPolicyGraphIssues();
  if (!draft || issues.length) {
    showPolicySaveIssues(
      "策略暂不能另存为",
      [
        ...issues,
        ...(!draft ? [policyBasicStatus.textContent || "策略基本信息不完整。"] : []),
      ],
      "请先修复当前策略草稿的问题，再创建副本。",
    );
    return;
  }
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
  if (!validCustomPolicyId(id)) {
    const message = "新策略 ID 格式无效。";
    saveAsPolicyStatus.textContent = message;
    showPolicySaveIssues("策略另存为失败", [message]);
    return;
  }
  if (!name) {
    const message = "请填写策略名称。";
    saveAsPolicyStatus.textContent = message;
    showPolicySaveIssues("策略另存为失败", [message]);
    return;
  }
  if (policyLibrary.policies.some((policy) => policy.policy_id === id)) {
    const message = "策略 ID 已存在。";
    saveAsPolicyStatus.textContent = message;
    showPolicySaveIssues("策略另存为失败", [message]);
    return;
  }
  const draft = collectPolicyDetailDraft(source);
  if (!draft) {
    showPolicySaveIssues("策略另存为失败", [policyBasicStatus.textContent || "策略基本信息不完整。"]);
    return;
  }
  const copy = { ...draft, policy_id: id, name, description: saveAsPolicyDescription.value.trim(), builtin: false };
  policyLibrary.policies.push(copy);
  confirmSavePolicyAs.disabled = true;
  const saved = await persistPolicyLibrary(
    (revision) => `策略“${name}”已另存为 revision ${revision}。`,
    { showIssues: true, operation: "策略另存为" },
  );
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
  if (policyLibrary.active_policy_id === policyId) policyLibrary.active_policy_id = "";
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
  if (field.type === "list" || field.type === "text" || field.key === "sanitizer") {
    const textarea = document.createElement("textarea");
    textarea.className = field.type === "list" ? "template-list-value" : "template-text-value";
    textarea.spellcheck = field.type !== "list";
    textarea.value = field.type === "list"
      ? (Array.isArray(value) ? value.join("\n") : "")
      : String(value ?? "");
    return textarea;
  }
  const input = document.createElement("input");
  input.type = field.type === "string" ? "text" : "number";
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
    if (field.fullWidth || field.key === "sanitizer") label.classList.add("full-width");
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
  const hitLabel = document.createElement("label"); hitLabel.textContent = "默认命中动作"; hitLabel.append(createRuleFieldHint("命中时的默认处理；策略编排可覆盖。retry_generation 仅在 Step 5 生效，在其他 Step 会回退为默认动作。"), hitAction);
  const errorAction = createActionSelect(errorActions, rule.default_action_on_error); errorAction.className = "rule-error-action";
  const errorLabel = document.createElement("label"); errorLabel.textContent = "默认错误动作"; errorLabel.append(createRuleFieldHint("规则执行出错时的默认处理；策略编排可覆盖。"), errorAction);
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
  const deletedRuleIds = new Set(pendingRuleDeletionIds);
  const savedRuleLibrary = {
    ...ruleLibrary,
    rules: ruleLibrary.rules.filter((rule) => !deletedRuleIds.has(rule.rule_id)),
  };
  try {
    const result = await bridge.apiPost("save_rule_library", {
      expected_revision: currentRevision,
      rule_library: savedRuleLibrary,
    });
    if (!result.success) {
      ruleStatus.textContent = "";
      publishReport(result.detail || result.error || "保存失败。", { tone: "error" });
      return false;
    }
    currentRevision = result.revision;
    if (deletedRuleIds.size) {
      ruleLibrary.rules = savedRuleLibrary.rules;
      for (const ruleId of deletedRuleIds) {
        openRuleIds = openRuleIds.filter((id) => id !== ruleId);
        openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`)?.remove();
        pendingRuleDeletionIds.delete(ruleId);
      }
      ruleEmptyState.hidden = openRuleIds.length > 0;
    }
    ruleStatus.textContent = "";
    publishReport(successMessage(result.revision));
    rerenderOverviewIfReady();
    return true;
  } catch (error) {
    ruleStatus.textContent = "";
    publishReport(`保存失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
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
  confirmRuleDeleteMessage.textContent = `规则“${ruleId}”会标记为待删除；保存规则库时才会真正移除。若策略仍绑定它，保存会被拒绝。`;
  confirmRuleDeleteDialog.showModal();
}
function deleteRule(ruleId) {
  openRuleIds = openRuleIds.filter((id) => id !== ruleId);
  openRuleEditors.querySelector(`[data-rule-id="${ruleId}"]`)?.remove();
  ruleEmptyState.hidden = openRuleIds.length > 0;
  pendingRuleDeletionIds.add(ruleId);
  ruleStatus.textContent = "";
  publishReport("规则已标记为待删除；再次点击该卡片可取消，保存规则库时才会真正移除。", { tone: "warning" });
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
  ruleStatus.textContent = "";
  publishReport("已新建规则，保存后才会发布。", { tone: "warning" });
  cancelNewRuleCreation();
  openRule(id);
  renderRuleList();
}
function accessReasonOptions(decision) {
  const options = Array.isArray(accessReasonCodes?.[decision])
    ? accessReasonCodes[decision]
    : [];
  if (options.length) return options;
  return decision === "ban"
    ? [{ code: "manual_ban", label: "手动封禁" }]
    : [{ code: "manual_pardon", label: "手动赦免" }];
}
function renderAccessReasonCodeOptions(selectedCode = "") {
  const currentDecision = accessDecision.value === "pardon" ? "pardon" : "ban";
  const options = accessReasonOptions(currentDecision);
  accessReasonCode.replaceChildren();
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.code;
    option.textContent = `${item.label}（${item.code}）`;
    accessReasonCode.append(option);
  }
  const known = options.some((item) => item.code === selectedCode);
  accessReasonCode.value = known ? selectedCode : options[0]?.code || "";
}
function syncAccessDurationControl() {
  const permanent = accessDurationMode.value === "permanent";
  accessDurationRow.hidden = permanent;
  accessDurationMinutes.disabled = permanent;
}
function resetAccessFormState() {
  accessPlatformId.value = "";
  accessUserId.value = "";
  accessPlatformId.disabled = false;
  accessUserId.disabled = false;
  accessDecision.value = "ban";
  accessDurationMode.value = "temporary";
  accessDurationMinutes.value = "60";
  accessFormExpectedRecordRevision = null;
  syncAccessDurationControl();
  renderAccessReasonCodeOptions();
  accessFormStatus.textContent = "填写主体后可创建新的手动封禁或赦免决定。";
}
function formatAccessTime(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return "永久";
  return new Date(seconds * 1000).toLocaleString("zh-CN", { hour12: false });
}
function formatAccessSource(value) {
  return value === "automatic" ? "自动" : value === "manual" ? "手动" : "-";
}
function appendAccessMeta(container, label, value) {
  const item = document.createElement("div");
  const term = document.createElement("span");
  const detail = document.createElement("strong");
  term.textContent = label;
  detail.textContent = String(value || "-");
  item.append(term, detail);
  container.append(item);
}
function editAccessRecord(record) {
  accessPlatformId.value = String(record.platform_id || "");
  accessUserId.value = String(record.user_id || "");
  // A record revision belongs to this exact principal key.  Replacing its
  // decision must never accidentally turn into a write against another key.
  accessPlatformId.disabled = true;
  accessUserId.disabled = true;
  accessDecision.value = record.decision === "pardon" ? "pardon" : "ban";
  const expiration = Number(record.decision_expires_at);
  if (expiration === 0) {
    accessDurationMode.value = "permanent";
  } else {
    accessDurationMode.value = "temporary";
    const remainingMinutes = Math.max(1, Math.ceil((expiration * 1000 - Date.now()) / 60000));
    accessDurationMinutes.value = String(remainingMinutes);
  }
  accessFormExpectedRecordRevision = Number.isInteger(record.record_revision)
    ? record.record_revision
    : null;
  syncAccessDurationControl();
  renderAccessReasonCodeOptions(record.decision_reason_code);
  accessFormStatus.textContent = `正在替换 ${record.principal_id} 的当前决定；主体标识已锁定，保存会校验记录版本。`;
  accessPlatformId.focus();
}
function renderAccessRecords() {
  accessRecordList.replaceChildren();
  const filter = accessDecisionFilter.value;
  const records = accessRecords.filter((record) => filter === "all" || record.decision === filter);
  accessRecordCount.textContent = String(records.length);
  if (!records.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "没有符合筛选条件的有效访问决定。";
    accessRecordList.append(empty);
    return;
  }
  for (const record of records) {
    const card = document.createElement("article");
    card.className = `access-record is-${record.decision}`;
    const heading = document.createElement("div");
    heading.className = "access-record-heading";
    const identity = document.createElement("strong");
    const badge = document.createElement("span");
    identity.textContent = record.principal_id || "未知主体";
    badge.className = `access-decision-badge is-${record.decision}`;
    badge.textContent = record.decision === "pardon" ? "赦免" : "封禁";
    heading.append(identity, badge);
    const metadata = document.createElement("div");
    metadata.className = "access-record-meta";
    appendAccessMeta(metadata, "来源", formatAccessSource(record.decision_source));
    appendAccessMeta(metadata, "到期", formatAccessTime(record.decision_expires_at));
    appendAccessMeta(metadata, "违规计数", record.violation_count ?? 0);
    appendAccessMeta(metadata, "决定原因", record.decision_reason_label || record.decision_reason_code || "-");
    appendAccessMeta(metadata, "最近违规", record.last_violation_reason_label || record.last_violation_reason_code || "-");
    const actions = document.createElement("div");
    actions.className = "access-record-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "button-secondary";
    edit.textContent = "替换决定";
    edit.disabled = accessMutationInFlight;
    edit.addEventListener("click", () => editAccessRecord(record));
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "button-danger";
    clear.textContent = record.decision === "pardon" ? "撤销赦免" : "解除封禁";
    clear.disabled = accessMutationInFlight;
    clear.addEventListener("click", () => clearAccessDecision(record));
    actions.append(edit, clear);
    card.append(heading, metadata, actions);
    accessRecordList.append(card);
  }
}
function setAccessMutationBusy(busy) {
  accessMutationInFlight = busy;
  saveAccessDecision.disabled = busy;
  resetAccessForm.disabled = busy;
  refreshAccessRecords.disabled = busy;
  renderAccessRecords();
}
function applyAccessRecordsPayload(payload) {
  accessRecords = Array.isArray(payload?.records) ? payload.records : [];
  accessReasonCodes = payload?.reason_codes && typeof payload.reason_codes === "object"
    ? payload.reason_codes
    : { ban: [], pardon: [] };
  renderAccessReasonCodeOptions(accessReasonCode.value);
  renderAccessRecords();
  rerenderOverviewIfReady();
}
async function refreshAccessControl() {
  if (!bridge) return;
  const epoch = ++accessRefreshEpoch;
  refreshAccessRecords.disabled = true;
  try {
    const payload = await bridge.apiGet("get_access_control_records");
    if (epoch !== accessRefreshEpoch) return;
    if (!payload?.success) {
      accessRecordsStatus.textContent = "";
      publishReport(payload?.error || "无法读取访问控制状态。", { tone: "error" });
      return;
    }
    applyAccessRecordsPayload(payload);
    accessRecordsStatus.textContent = "";
  } catch (error) {
    if (epoch === accessRefreshEpoch) {
      accessRecordsStatus.textContent = "";
      publishReport(`读取访问控制状态失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
    }
  } finally {
    if (epoch === accessRefreshEpoch && !accessMutationInFlight) {
      refreshAccessRecords.disabled = false;
    }
  }
}
async function saveAccessDecisionMutation() {
  if (!bridge || accessMutationInFlight) return;
  const platformId = accessPlatformId.value.trim();
  const userId = accessUserId.value.trim();
  if (!platformId || !userId) {
    accessFormStatus.textContent = "平台适配器名和发送者 ID 都不能为空。";
    return;
  }
  const permanent = accessDurationMode.value === "permanent";
  const durationMinutes = permanent ? -1 : Number(accessDurationMinutes.value);
  if (!permanent && (!Number.isInteger(durationMinutes) || durationMinutes < 1)) {
    accessFormStatus.textContent = "临时时长必须是正整数分钟。";
    return;
  }
  const payload = {
    platform_id: platformId,
    user_id: userId,
    decision: accessDecision.value,
    duration_minutes: durationMinutes,
    reason_code: accessReasonCode.value,
  };
  if (Number.isInteger(accessFormExpectedRecordRevision)) {
    payload.expected_record_revision = accessFormExpectedRecordRevision;
  }
  setAccessMutationBusy(true);
  try {
    const result = await bridge.apiPost("set_access_control_decision", payload);
    if (!result?.success) {
      accessFormStatus.textContent = result?.error || "访问决定保存失败。";
      if (result?.conflict) await refreshAccessControl();
      return;
    }
    accessFormStatus.textContent = "";
    resetAccessFormState();
    await refreshAccessControl();
    publishReport("访问决定已保存。");
  } catch (error) {
    accessFormStatus.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    setAccessMutationBusy(false);
  }
}
async function clearAccessDecision(record) {
  if (!bridge || accessMutationInFlight) return;
  setAccessMutationBusy(true);
  accessRecordsStatus.textContent = "";
  try {
    const result = await bridge.apiPost("clear_access_control_decision", {
      platform_id: record.platform_id,
      user_id: record.user_id,
      expected_decision: record.decision,
      expected_record_revision: record.record_revision,
    });
    if (!result?.success) {
      publishReport(result?.error || "访问决定解除失败。", { tone: "error" });
      if (result?.conflict) await refreshAccessControl();
      return;
    }
    await refreshAccessControl();
    publishReport("访问决定已解除。");
  } catch (error) {
    publishReport(`解除访问决定失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
  } finally {
    setAccessMutationBusy(false);
  }
}
function formatStateTime(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) return "未记录";
  return new Date(seconds * 1000).toLocaleString("zh-CN", { hour12: false });
}
function appendSessionStateMeta(container, label, value) {
  const item = document.createElement("div");
  const term = document.createElement("span");
  const detail = document.createElement("strong");
  term.textContent = label;
  detail.textContent = String(value || "-");
  item.append(term, detail);
  container.append(item);
}
function formatObservedTarget(target) {
  if (!target) return "未记录";
  const providerId = String(target.provider_id || "").trim();
  const modelId = String(target.model_id || "").trim();
  if (!providerId && target.source) return "未观察到目标";
  const provider = providerId || "AstrBot 默认（未显式指定 Provider）";
  return modelId ? `${provider} · ${modelId}` : provider;
}
function requestTargetSourceLabel(source) {
  return source === "provider_request"
    ? "ProviderRequest 字段"
    : source === "event_selected_provider"
      ? "Step 3 显式请求选择"
      : "当前请求未提供可观察目标";
}
function sessionPolicyOutcomeLabel(outcome) {
  return outcome === "blocked" ? "已阻断" : outcome === "allowed" ? "已放行" : "已跳过";
}
function sessionPolicyRailOutcomeLabel(outcome) {
  return {
    blocked: "已阻断",
    allowed: "已放行",
    skipped: "已跳过",
    completed: "已完成",
    selected: "已选中目标",
    abstained: "未选中目标",
    invalid: "路由无效",
  }[outcome] || String(outcome || "-");
}
function sessionPolicyActivityLabel(kind) {
  return {
    policy_stage_completed: "策略阶段完成",
    late_policy_stage_observed: "迟到策略阶段（未覆盖较新结果）",
    route_candidate_recorded: "记录路由候选",
    request_target_observed: "记录请求选择目标",
    retry_generation: "重试生成",
  }[kind] || String(kind || "活动");
}
function updateSessionPolicyPagination() {
  const totalPages = Math.max(1, Math.ceil(sessionPolicyStateTotal / sessionPolicyStatePageSize));
  sessionPolicyStatePage.textContent = `第 ${sessionPolicyStateCurrentPage} / ${totalPages} 页 · 共 ${sessionPolicyStateTotal} 个 UMO`;
  sessionPolicyStatePrevPage.disabled = sessionPolicyStateCurrentPage <= 1;
  sessionPolicyStateNextPage.disabled = sessionPolicyStateCurrentPage >= totalPages;
}
function renderSessionPolicyStateList() {
  sessionPolicyStateList.replaceChildren();
  sessionPolicyStateCount.textContent = String(sessionPolicyStateTotal);
  updateSessionPolicyPagination();
  if (!sessionPolicyStateItems.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "尚无符合条件的 UMO 状态记录。";
    sessionPolicyStateList.append(empty);
    return;
  }
  for (const item of sessionPolicyStateItems) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "policy-list-item session-policy-list-item";
    const title = document.createElement("strong");
    const summary = document.createElement("small");
    const targets = document.createElement("span");
    const metadata = document.createElement("span");
    const result = item.last_policy_result || {};
    title.textContent = item.umo || "未知 UMO";
    summary.textContent = result.policy_id
      ? `${result.policy_id} · ${sessionPolicyOutcomeLabel(result.outcome)}`
      : "尚未形成策略结果";
    targets.textContent = `策略候选：${formatObservedTarget(item.route_candidate)} · 请求选择：${formatObservedTarget(item.last_request_target_observation)}`;
    metadata.textContent = `观察模式，未参与执行 · 最近活动 ${formatStateTime(item.updated_at)}`;
    button.append(title, summary, targets, metadata);
    button.addEventListener("click", () => {
      void showSessionPolicyStateDetail(item.umo);
    });
    sessionPolicyStateList.append(button);
  }
}
function renderSessionPolicySignals(signals) {
  sessionPolicySignalList.replaceChildren();
  if (!Array.isArray(signals) || !signals.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "最近一次策略执行没有记录命中 NodeSignal。";
    sessionPolicySignalList.append(empty);
    return;
  }
  for (const item of signals) {
    const signal = document.createElement("article");
    signal.className = "session-policy-signal";
    const heading = document.createElement("strong");
    const metadata = document.createElement("small");
    const payload = document.createElement("pre");
    heading.textContent = item.node_id || "未知节点";
    metadata.textContent = [item.rail, item.template_key, item.user_node_id]
      .filter(Boolean)
      .join(" · ") || "节点来源未记录";
    payload.textContent = JSON.stringify(item.signal || {}, null, 2);
    signal.append(heading, metadata, payload);
    sessionPolicySignalList.append(signal);
  }
}
function renderSessionPolicyTarget(container, target, kind) {
  container.replaceChildren();
  if (!target) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = kind === "candidate" ? "未形成可记录的路由候选。" : "尚未记录请求选择目标。";
    container.append(empty);
    return;
  }
  const metadata = document.createElement("div");
  metadata.className = "session-target-meta";
  const providerId = String(target.provider_id || "").trim();
  const requestTargetUnavailable = kind === "request" && !providerId;
  appendSessionStateMeta(
    metadata,
    "Provider",
    providerId || (requestTargetUnavailable ? "未观察到目标" : "AstrBot 默认（未显式指定 Provider）"),
  );
  appendSessionStateMeta(
    metadata,
    "模型",
    String(target.model_id || "").trim() || (requestTargetUnavailable ? "未观察到" : "未显式指定"),
  );
  if (kind === "candidate") {
    appendSessionStateMeta(metadata, "来源节点", target.source_route_node_id || "未定位");
    appendSessionStateMeta(metadata, "模式", "observe_only（观察模式）");
    appendSessionStateMeta(metadata, "记录时间", formatStateTime(target.created_at || target.observed_at));
  } else {
    appendSessionStateMeta(metadata, "来源", requestTargetSourceLabel(target.source));
    appendSessionStateMeta(metadata, "观察时间", formatStateTime(target.observed_at));
  }
  appendSessionStateMeta(metadata, "run_id", target.run_id || "未关联");
  container.append(metadata);
}
function renderSessionPolicyActivities(items) {
  sessionPolicyActivityList.replaceChildren();
  if (!Array.isArray(items) || !items.length) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "尚无可展示的状态活动。";
    sessionPolicyActivityList.append(empty);
    return;
  }
  for (const item of items) {
    const activity = document.createElement("article");
    activity.className = "session-policy-activity";
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    const timestamp = document.createElement("time");
    const detail = document.createElement("small");
    title.textContent = sessionPolicyActivityLabel(item.kind);
    timestamp.textContent = formatStateTime(item.at);
    const retryProgress = item.kind === "retry_generation"
      ? `第 ${Number(item.attempt || 0)}/${Number(item.max_retries || 0)} 次`
      : "";
    const parts = [item.phase, item.policy_id, item.provider_id, retryProgress, item.outcome]
      .filter(Boolean)
      .map((value) => String(value));
    detail.textContent = parts.join(" · ") || "无额外摘要";
    heading.append(title, timestamp);
    activity.append(heading, detail);
    sessionPolicyActivityList.append(activity);
  }
}
function sessionPolicySelectionSourceLabel(source) {
  return {
    explicit: "明确指定",
    explicit_fallback_umo_list: "明确指定暂不可用，已按 UMO 匹配回退",
    explicit_fallback_system: "明确指定暂不可用，当前使用系统 fallback",
    umo_list: "自动选路：UMO 匹配",
    global_default: "自动选路：全局默认",
    system_fallback: "自动选路：系统 fallback",
  }[source] || "当前选路来源未知";
}
function renderSessionPolicySelection(selection) {
  sessionPolicySelection.replaceChildren();
  sessionPolicySelectionStatus.textContent = "";
  if (!selection || typeof selection !== "object") {
    const option = document.createElement("option");
    option.textContent = "正在加载策略指定…";
    option.value = "";
    sessionPolicySelection.append(option);
    sessionPolicySelection.disabled = true;
    saveSessionPolicySelection.disabled = true;
    return;
  }
  const explicitPolicyId = String(selection.explicit_policy_id || "").trim();
  const availablePolicies = Array.isArray(selection.available_policies)
    ? selection.available_policies
    : [];
  const automatic = document.createElement("option");
  automatic.value = "";
  automatic.textContent = "自动选路（取消明确指定）";
  sessionPolicySelection.append(automatic);
  let hasExplicitOption = !explicitPolicyId;
  for (const policy of availablePolicies) {
    const option = document.createElement("option");
    option.value = String(policy.policy_id || "");
    option.textContent = `${policy.name || option.value} · ${option.value}${policy.umo_matched ? "（匹配当前 UMO）" : ""}`;
    if (option.value === explicitPolicyId) hasExplicitOption = true;
    sessionPolicySelection.append(option);
  }
  if (explicitPolicyId && !hasExplicitOption) {
    const unavailable = document.createElement("option");
    unavailable.value = explicitPolicyId;
    unavailable.textContent = `当前明确指定：${explicitPolicyId}（已不可用）`;
    unavailable.disabled = true;
    sessionPolicySelection.append(unavailable);
  }
  sessionPolicySelection.value = hasExplicitOption ? explicitPolicyId : "";
  sessionPolicySelection.disabled = false;
  saveSessionPolicySelection.disabled = false;
  saveSessionPolicySelection.textContent = explicitPolicyId
    ? "更新指定"
    : "保存指定";
  const effectivePolicyId = String(selection.effective_policy_id || "").trim();
  const requested = explicitPolicyId
    ? `明确指定：${explicitPolicyId}`
    : "当前未明确指定策略";
  const effective = effectivePolicyId
    ? `实际解析：${effectivePolicyId}`
    : "实际解析：系统 fallback";
  sessionPolicySelectionStatus.textContent = `${requested} · ${effective} · ${sessionPolicySelectionSourceLabel(selection.source)}`;
}
function renderSessionPolicyStateDetail(record, policySelection = null) {
  const result = record?.last_policy_result || null;
  selectedSessionPolicyRecordRevision = Number.isInteger(record?.record_revision)
    && record.record_revision > 0 ? record.record_revision : null;
  clearSessionPolicyState.disabled = selectedSessionPolicyRecordRevision === null;
  sessionPolicyDetailUmo.textContent = record?.umo || "会话策略状态";
  sessionPolicyDetailMeta.textContent = record
    ? `记录版本 ${record.record_revision ?? 0} · 最近活动 ${formatStateTime(record.updated_at)}`
    : "未找到该 UMO 状态。";
  renderSessionPolicySelection(policySelection);
  sessionPolicyResultSummary.replaceChildren();
  if (!result) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "该 UMO 尚未形成可展示的策略结果。";
    sessionPolicyResultSummary.append(empty);
  } else {
    appendSessionStateMeta(sessionPolicyResultSummary, "策略", result.policy_id || "未记录");
    appendSessionStateMeta(sessionPolicyResultSummary, "快照 revision", result.snapshot_revision ?? "-");
    appendSessionStateMeta(sessionPolicyResultSummary, "最近阶段", result.last_stage || "-");
    appendSessionStateMeta(sessionPolicyResultSummary, "结果", sessionPolicyOutcomeLabel(result.outcome));
    appendSessionStateMeta(sessionPolicyResultSummary, "run_id", result.run_id || "-");
    appendSessionStateMeta(sessionPolicyResultSummary, "观察时间", formatStateTime(result.observed_at));
    const terminal = result.terminal_action;
    appendSessionStateMeta(
      sessionPolicyResultSummary,
      "终止动作",
      terminal ? [terminal.source_kind, terminal.node_id, terminal.action, terminal.target].filter(Boolean).join(" · ") : "无",
    );
    const rails = result.rail_outcomes && typeof result.rail_outcomes === "object"
      ? Object.entries(result.rail_outcomes)
        .map(([rail, value]) => `${rail}: ${sessionPolicyRailOutcomeLabel(value?.route_outcome || value?.outcome)}`)
        .join("；")
      : "-";
    appendSessionStateMeta(sessionPolicyResultSummary, "Rail 结果", rails);
  }
  renderSessionPolicySignals(result?.signals || []);
  renderSessionPolicyTarget(sessionPolicyRouteCandidate, record?.route_candidate, "candidate");
  renderSessionPolicyTarget(sessionPolicyRequestObservation, record?.last_request_target_observation, "request");
  const candidate = record?.route_candidate;
  const requestTarget = record?.last_request_target_observation;
  if (!candidate || !requestTarget) {
    sessionPolicyTargetComparison.textContent = "缺少其中一侧目标，暂不能比较。";
  } else if (requestTarget.source === "unavailable" || !String(requestTarget.provider_id || "").trim()) {
    sessionPolicyTargetComparison.textContent = "请求选择阶段未获得可比较的目标；不会据此判断策略候选是否生效。";
  } else if (candidate.run_id !== requestTarget.run_id) {
    sessionPolicyTargetComparison.textContent = "两个目标来自不同 run_id，未将它们作为同一次执行进行比较。";
  } else {
    const sameProvider = String(candidate.provider_id || "") === String(requestTarget.provider_id || "");
    const candidateModel = String(candidate.model_id || "").trim();
    const sameModel = !candidateModel || candidateModel === String(requestTarget.model_id || "").trim();
    if (sameProvider && sameModel) {
      sessionPolicyTargetComparison.textContent = candidateModel
        ? "同一次执行中，策略路由候选与请求选择目标一致。"
        : "同一次执行中，Provider 目标一致；策略未显式约束模型，因此未比较模型。";
    } else {
      sessionPolicyTargetComparison.textContent = "同一次执行中，策略路由候选与请求选择目标不同；这是一条观察事实，不会触发自动改写。";
    }
  }
  renderSessionPolicyActivities(record?.activities?.items || []);
}
function setSessionPolicyStateView(showDetail) {
  sessionPolicyListPanel.hidden = showDetail;
  sessionPolicyListPanel.style.display = showDetail ? "none" : "grid";
  sessionPolicyDetailPanel.hidden = !showDetail;
  sessionPolicyDetailPanel.style.display = showDetail ? "grid" : "none";
}
function showSessionPolicyStateList() {
  selectedSessionPolicyUmo = null;
  setSessionPolicyStateView(false);
  renderSessionPolicyStateList();
}
async function showSessionPolicyStateDetail(umo) {
  if (!bridge || !umo) return;
  const epoch = ++sessionPolicyStateDetailEpoch;
  selectedSessionPolicyUmo = String(umo);
  setSessionPolicyStateView(true);
  sessionPolicyDetailUmo.textContent = selectedSessionPolicyUmo;
  sessionPolicyDetailMeta.textContent = "正在加载 UMO 状态…";
  renderSessionPolicySelection(null);
  try {
    const payload = await bridge.apiGet("get_session_policy_state", { umo: selectedSessionPolicyUmo });
    if (epoch !== sessionPolicyStateDetailEpoch) return;
    if (!payload?.success) {
      sessionPolicyDetailMeta.textContent = payload?.error || "无法读取该 UMO 状态。";
      renderSessionPolicyStateDetail(null);
      return;
    }
    renderSessionPolicyStateDetail(payload.record, payload.policy_selection);
    if (!payload.monitoring_enabled) {
      sessionPolicyDetailMeta.textContent += " · 监控当前已关闭，已有记录仅供查看。";
    }
  } catch (error) {
    if (epoch === sessionPolicyStateDetailEpoch) {
      sessionPolicyDetailMeta.textContent = `读取失败：${error instanceof Error ? error.message : String(error)}`;
      renderSessionPolicyStateDetail(null);
    }
  }
}
async function saveCurrentSessionPolicySelection() {
  if (!bridge || !selectedSessionPolicyUmo || sessionPolicySelectionInFlight) return;
  const policyId = sessionPolicySelection.value.trim();
  if (!Number.isInteger(currentRevision)) {
    sessionPolicySelectionStatus.textContent = "尚未加载当前配置，无法保存指定。";
    return;
  }
  sessionPolicySelectionInFlight = true;
  sessionPolicySelection.disabled = true;
  saveSessionPolicySelection.disabled = true;
  sessionPolicySelectionStatus.textContent = "正在保存策略指定…";
  try {
    const result = await bridge.apiPost("set_umo_policy_selection", {
      umo: selectedSessionPolicyUmo,
      policy_id: policyId || null,
      expected_revision: currentRevision,
    });
    if (!result?.success) {
      sessionPolicySelectionStatus.textContent = result?.detail || result?.error || "保存策略指定失败。";
      return;
    }
    currentRevision = result.revision;
    await showSessionPolicyStateDetail(selectedSessionPolicyUmo);
    sessionPolicySelectionStatus.textContent = policyId
      ? `已为该 UMO 明确指定 ${policyId}。`
      : "已取消明确指定，后续请求恢复自动选路。";
  } catch (error) {
    sessionPolicySelectionStatus.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    sessionPolicySelectionInFlight = false;
    sessionPolicySelection.disabled = false;
    saveSessionPolicySelection.disabled = false;
  }
}
function requestSessionPolicyStateDeletion() {
  if (!selectedSessionPolicyUmo || !Number.isInteger(selectedSessionPolicyRecordRevision)
    || sessionPolicyStateDeleteInFlight) return;
  confirmSessionPolicyStateDeleteMessage.textContent = `将删除 UMO “${selectedSessionPolicyUmo}”的最近策略结果、路由候选、请求观察和活动记录；明确策略指定不会被删除。`;
  confirmSessionPolicyStateDeleteDialog.showModal();
}
async function clearCurrentSessionPolicyState() {
  if (!bridge || !selectedSessionPolicyUmo || !Number.isInteger(selectedSessionPolicyRecordRevision)
    || sessionPolicyStateDeleteInFlight) return;
  sessionPolicyStateDeleteInFlight = true;
  clearSessionPolicyState.disabled = true;
  try {
    const result = await bridge.apiPost("delete_session_policy_state", {
      umo: selectedSessionPolicyUmo,
      expected_record_revision: selectedSessionPolicyRecordRevision,
    });
    if (!result?.success) {
      sessionPolicyDetailMeta.textContent = result?.error || "清除会话状态失败。";
      if (result?.conflict) await showSessionPolicyStateDetail(selectedSessionPolicyUmo);
      return;
    }
    await refreshSessionPolicyStates();
    await showSessionPolicyStateDetail(selectedSessionPolicyUmo);
    sessionPolicyDetailMeta.textContent += " · 已清除全部运行状态；明确策略指定未受影响。";
  } catch (error) {
    sessionPolicyDetailMeta.textContent = `清除失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    sessionPolicyStateDeleteInFlight = false;
    clearSessionPolicyState.disabled = selectedSessionPolicyRecordRevision === null;
  }
}
async function refreshSessionPolicyStates(resetPage = false) {
  if (!bridge) return;
  if (resetPage) sessionPolicyStateCurrentPage = 1;
  const epoch = ++sessionPolicyStateRefreshEpoch;
  refreshSessionPolicyStatesButton.disabled = true;
  try {
    const payload = await bridge.apiGet("get_session_policy_states", {
      query: sessionPolicyStateQuery.value.trim(),
      page: sessionPolicyStateCurrentPage,
      page_size: sessionPolicyStatePageSize,
    });
    if (epoch !== sessionPolicyStateRefreshEpoch) return;
    if (!payload?.success) {
      sessionPolicyStateStatus.textContent = "";
      publishReport(payload?.error || "无法读取会话策略状态。", { tone: "error" });
      return;
    }
    sessionPolicyStateItems = Array.isArray(payload.items) ? payload.items : [];
    const pagination = payload.pagination || {};
    sessionPolicyStateCurrentPage = Number.isInteger(pagination.page)
      ? pagination.page
      : sessionPolicyStateCurrentPage;
    sessionPolicyStatePageSize = Number.isInteger(pagination.page_size)
      ? pagination.page_size
      : sessionPolicyStatePageSize;
    sessionPolicyStateTotal = Number.isInteger(pagination.total) ? pagination.total : 0;
    sessionPolicyMonitoringEnabled = Boolean(payload.monitoring_enabled);
    renderSessionPolicyStateList();
    rerenderOverviewIfReady();
    sessionPolicyStateStatus.textContent = "";
  } catch (error) {
    if (epoch === sessionPolicyStateRefreshEpoch) {
      sessionPolicyStateStatus.textContent = "";
      publishReport(`读取会话策略状态失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
    }
  } finally {
    if (epoch === sessionPolicyStateRefreshEpoch) {
      refreshSessionPolicyStatesButton.disabled = false;
      updateSessionPolicyPagination();
    }
  }
}
function formatRagExperienceScore(value) {
  const score = Number(value);
  if (!Number.isFinite(score)) return "未提供";
  return score.toLocaleString("zh-CN", { maximumFractionDigits: 4 });
}
function appendRagExperienceMeta(container, label, value) {
  const item = document.createElement("div");
  const term = document.createElement("span");
  const detail = document.createElement("strong");
  term.textContent = label;
  detail.textContent = String(value || "-");
  item.append(term, detail);
  container.append(item);
}
function hasRagExperienceSource(record) {
  return Boolean(
    String(record?.source_kb_id || "").trim() ||
    String(record?.source_kb_name || "").trim(),
  );
}
function ragExperienceHasUnsavedEdits() {
  const record = selectedRagExperience;
  return Boolean(
    record && (
      ragExperienceTitle.value !== String(record.title || "") ||
      ragExperienceContent.value !== String(record.content || "")
    ),
  );
}
function setRagExperienceMutationBusy(busy) {
  ragExperienceMutationInFlight = busy;
  updateRagExperienceActionState();
}
function updateRagExperienceActionState() {
  const record = selectedRagExperience;
  const hasRecord = Boolean(record && Number.isInteger(record.record_revision));
  const hasSource = hasRagExperienceSource(record);
  const hasContent = Boolean(ragExperienceContent.value.trim());
  const hasUnsavedEdits = ragExperienceHasUnsavedEdits();
  const disabled = ragExperienceMutationInFlight || !hasRecord;
  saveRagExperience.disabled = disabled;
  deleteRagExperience.disabled = disabled;
  uploadRagExperience.disabled = disabled || !hasSource || !hasContent || hasUnsavedEdits;
  uploadRagExperience.title = !hasRecord
    ? "请先选择一条经验记录。"
    : !hasSource
      ? "该最高分证据未提供可确认的原知识库。"
      : !hasContent
        ? "经验内容不能为空。"
        : hasUnsavedEdits
          ? "请先保存编辑，再写入原知识库。"
          : "将当前已保存的内容作为新 Markdown 文档写入原知识库。";
}
function updateRagExperiencePagination() {
  const totalPages = Math.max(1, Math.ceil(ragExperienceTotal / ragExperiencePageSize));
  ragExperiencePage.textContent = `第 ${ragExperienceCurrentPage} / ${totalPages} 页 · 共 ${ragExperienceTotal} 条`;
  ragExperiencePrevPage.disabled = ragExperienceCurrentPage <= 1;
  ragExperienceNextPage.disabled = ragExperienceCurrentPage >= totalPages;
}
function renderRagExperienceList() {
  ragExperienceList.replaceChildren();
  ragExperienceCount.textContent = String(ragExperienceTotal);
  updateRagExperiencePagination();
  if (!ragExperienceItems.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "尚无符合条件的 RAG 命中经验记录。";
    ragExperienceList.append(empty);
    return;
  }
  for (const item of ragExperienceItems) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "policy-list-item rag-experience-list-item";
    const title = document.createElement("strong");
    const summary = document.createElement("small");
    const source = document.createElement("span");
    const preview = document.createElement("span");
    const metadata = document.createElement("span");
    const sourceKb = String(item.source_kb_name || "").trim();
    const sourceDoc = String(item.source_doc_name || "").trim();
    title.textContent = item.title || "未命名经验";
    summary.textContent = [item.rail, item.rule_id].filter(Boolean).join(" · ") || "RAG 命中";
    source.textContent = sourceKb
      ? `最高分来源：${sourceKb}${sourceDoc ? ` · ${sourceDoc}` : ""} · 分数 ${formatRagExperienceScore(item.source_score)}`
      : "最高分来源未提供可确认的知识库，不能写入。";
    preview.textContent = item.content_preview || "（内容为空）";
    metadata.textContent = `最近编辑 ${formatStateTime(item.updated_at)} · 版本 ${item.record_revision ?? "-"}`;
    button.append(title, summary, source, preview, metadata);
    button.addEventListener("click", () => {
      void showRagExperienceDetail(item.record_id);
    });
    ragExperienceList.append(button);
  }
}
function renderRagExperienceDetail(record) {
  selectedRagExperience = record || null;
  ragExperienceDetailHeading.textContent = record?.title || "经验详情";
  ragExperienceDetailMeta.textContent = record
    ? `规则 ${record.rule_id || "-"} · ${record.rail || "-"} · 记录版本 ${record.record_revision ?? 0} · 最近编辑 ${formatStateTime(record.updated_at)}`
    : "未找到该经验记录。";
  ragExperienceTitle.value = record?.title || "";
  ragExperienceContent.value = record?.content || "";
  ragExperienceSourceMeta.replaceChildren();
  if (!record) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "无法读取来源信息。";
    ragExperienceSourceMeta.append(empty);
  } else if (!hasRagExperienceSource(record)) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "该次最高分证据没有提供可确认的知识库名称或 ID；记录仍可编辑，但不能推测写入目标。";
    ragExperienceSourceMeta.append(empty);
  } else {
    appendRagExperienceMeta(
      ragExperienceSourceMeta,
      "原知识库",
      record.source_kb_name || record.source_kb_id,
    );
    appendRagExperienceMeta(ragExperienceSourceMeta, "来源文档", record.source_doc_name || "未提供");
    appendRagExperienceMeta(ragExperienceSourceMeta, "检索分数", formatRagExperienceScore(record.source_score));
    appendRagExperienceMeta(ragExperienceSourceMeta, "记录时间", formatStateTime(record.created_at));
    if (record.source_evidence_preview) {
      const evidence = document.createElement("p");
      evidence.className = "rag-experience-evidence-preview";
      evidence.textContent = `命中证据摘要：${record.source_evidence_preview}`;
      ragExperienceSourceMeta.append(evidence);
    }
  }
  ragExperienceDetailStatus.textContent = record
    ? "编辑后请先保存；写入会新建 Markdown 文档，不会修改来源文档。"
    : "";
  updateRagExperienceActionState();
}
function setRagExperienceView(showDetail) {
  ragExperienceListPanel.hidden = showDetail;
  ragExperienceListPanel.style.display = showDetail ? "none" : "grid";
  ragExperienceDetailPanel.hidden = !showDetail;
  ragExperienceDetailPanel.style.display = showDetail ? "grid" : "none";
}
function showRagExperienceList() {
  selectedRagExperience = null;
  setRagExperienceView(false);
  renderRagExperienceList();
}
async function showRagExperienceDetail(recordId) {
  if (!bridge || !recordId) return;
  const epoch = ++ragExperienceDetailEpoch;
  setRagExperienceView(true);
  renderRagExperienceDetail(null);
  ragExperienceDetailHeading.textContent = "正在加载经验记录…";
  try {
    const payload = await bridge.apiGet("get_rag_experience", { record_id: String(recordId) });
    if (epoch !== ragExperienceDetailEpoch) return;
    if (!payload?.success || !payload.record) {
      ragExperienceDetailMeta.textContent = payload?.error || "无法读取该经验记录。";
      return;
    }
    renderRagExperienceDetail(payload.record);
  } catch (error) {
    if (epoch === ragExperienceDetailEpoch) {
      ragExperienceDetailMeta.textContent = `读取失败：${error instanceof Error ? error.message : String(error)}`;
    }
  }
}
async function refreshRagExperiences(resetPage = false) {
  if (!bridge) return;
  if (resetPage) ragExperienceCurrentPage = 1;
  const epoch = ++ragExperienceRefreshEpoch;
  refreshRagExperiencesButton.disabled = true;
  try {
    const payload = await bridge.apiGet("get_rag_experiences", {
      query: ragExperienceQuery.value.trim(),
      page: ragExperienceCurrentPage,
      page_size: ragExperiencePageSize,
    });
    if (epoch !== ragExperienceRefreshEpoch) return;
    if (!payload?.success) {
      ragExperienceStatus.textContent = "";
      publishReport(payload?.error || "无法读取 RAG 经验记录。", { tone: "error" });
      return;
    }
    ragExperienceItems = Array.isArray(payload.items) ? payload.items : [];
    const pagination = payload.pagination || {};
    ragExperienceCurrentPage = Number.isInteger(pagination.page)
      ? pagination.page
      : ragExperienceCurrentPage;
    ragExperiencePageSize = Number.isInteger(pagination.page_size)
      ? pagination.page_size
      : ragExperiencePageSize;
    ragExperienceTotal = Number.isInteger(pagination.total) ? pagination.total : 0;
    renderRagExperienceList();
    rerenderOverviewIfReady();
    ragExperienceStatus.textContent = "";
  } catch (error) {
    if (epoch === ragExperienceRefreshEpoch) {
      ragExperienceStatus.textContent = "";
      publishReport(`读取 RAG 经验记录失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
    }
  } finally {
    if (epoch === ragExperienceRefreshEpoch) {
      refreshRagExperiencesButton.disabled = false;
      updateRagExperiencePagination();
    }
  }
}
async function saveCurrentRagExperience() {
  const record = selectedRagExperience;
  if (!bridge || ragExperienceMutationInFlight || !record) return;
  const title = ragExperienceTitle.value.trim();
  if (!title) {
    ragExperienceDetailStatus.textContent = "文档标题不能为空。";
    return;
  }
  setRagExperienceMutationBusy(true);
  try {
    const result = await bridge.apiPost("save_rag_experience", {
      record_id: record.record_id,
      expected_record_revision: record.record_revision,
      title,
      content: ragExperienceContent.value,
    });
    if (!result?.success || !result.record) {
      ragExperienceDetailStatus.textContent = result?.error || "保存经验记录失败。";
      if (result?.conflict && result.record) {
        renderRagExperienceDetail(result.record);
        ragExperienceDetailStatus.textContent = "记录已被其他操作更新，已载入最新版本。";
      }
      return;
    }
    renderRagExperienceDetail(result.record);
    ragExperienceDetailStatus.textContent = "编辑已保存；现在可将该内容作为新文档写入原知识库。";
    await refreshRagExperiences();
  } catch (error) {
    ragExperienceDetailStatus.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    setRagExperienceMutationBusy(false);
  }
}
async function uploadCurrentRagExperience() {
  const record = selectedRagExperience;
  if (!bridge || ragExperienceMutationInFlight || !record) return;
  if (ragExperienceHasUnsavedEdits()) {
    ragExperienceDetailStatus.textContent = "请先保存编辑，再写入原知识库。";
    return;
  }
  if (!hasRagExperienceSource(record)) {
    ragExperienceDetailStatus.textContent = "该记录没有可确认的原知识库，不能安全地选择写入目标。";
    return;
  }
  if (!String(record.content || "").trim()) {
    ragExperienceDetailStatus.textContent = "经验内容不能为空。";
    return;
  }
  setRagExperienceMutationBusy(true);
  try {
    const result = await bridge.apiPost("upload_rag_experience", {
      record_id: record.record_id,
      expected_record_revision: record.record_revision,
    });
    if (!result?.success) {
      ragExperienceDetailStatus.textContent = result?.error || "写入原知识库失败。";
      if (result?.conflict && result.record) {
        renderRagExperienceDetail(result.record);
        ragExperienceDetailStatus.textContent = "记录已被其他操作更新，已载入最新版本。";
      }
      return;
    }
    ragExperienceDetailStatus.textContent = `已新建文档 ${result.doc_name || result.doc_id || ""}（${result.chunk_count ?? 0} 个分块）到 ${result.source_knowledge_base || "原知识库"}；该文档后续由 AstrBot 管理。`;
  } catch (error) {
    ragExperienceDetailStatus.textContent = `写入失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    setRagExperienceMutationBusy(false);
  }
}
function requestRagExperienceDeletion() {
  const record = selectedRagExperience;
  if (!record || ragExperienceMutationInFlight) return;
  confirmRagExperienceDeleteMessage.textContent = `将删除“${record.title || "未命名经验"}”这条本地记录；任何 AstrBot 知识库文档都不会被删除。`;
  confirmRagExperienceDeleteDialog.showModal();
}
async function deleteCurrentRagExperience() {
  const record = selectedRagExperience;
  if (!bridge || ragExperienceMutationInFlight || !record) return;
  setRagExperienceMutationBusy(true);
  try {
    const result = await bridge.apiPost("delete_rag_experience", {
      record_id: record.record_id,
      expected_record_revision: record.record_revision,
    });
    if (!result?.success) {
      ragExperienceDetailStatus.textContent = result?.error || "删除经验记录失败。";
      if (result?.conflict && result.record) {
        renderRagExperienceDetail(result.record);
        ragExperienceDetailStatus.textContent = "记录已被其他操作更新，已载入最新版本。";
      }
      return;
    }
    showRagExperienceList();
    await refreshRagExperiences();
    ragExperienceStatus.textContent = "";
    publishReport("本地 RAG 经验记录已删除；AstrBot 知识库文档未受影响。");
  } catch (error) {
    ragExperienceDetailStatus.textContent = `删除失败：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    setRagExperienceMutationBusy(false);
  }
}
function applyOverviewPayload(payload) {
  if (!payload?.success || !payload.overview) {
    throw new Error(payload?.error || "无法读取配置快照。");
  }
  latestOverview = payload.overview;
  currentRevision = payload.overview.revision;
}
function hasUnsavedRuleDrafts() {
  return pendingRuleDeletionIds.size > 0
    || [...openRuleEditors.children].some((editor) => editor.classList.contains("is-dirty"));
}
function applyRuleLibraryPayload(payload) {
  if (!payload?.success) throw new Error(payload?.error || "无法读取规则库。");
  if (hasUnsavedRuleDrafts()) {
    ruleStatus.textContent = "";
    publishReport("检测到未保存的规则草稿，已保留本地编辑内容；未用远端数据覆盖。", { tone: "warning" });
    return false;
  }
  const previousOpenRuleIds = [...openRuleIds];
  ruleLibrary = {
    rules: Array.isArray(payload.rule_library?.rules) ? payload.rule_library.rules : [],
  };
  openRuleEditors.replaceChildren();
  openRuleIds = [];
  for (const ruleId of previousOpenRuleIds) openRule(ruleId);
  ruleEmptyState.hidden = openRuleIds.length > 0;
  renderRuleList();
  const validation = payload.validation || { warnings: [], fatal_errors: [] };
  const messages = [...(validation.fatal_errors || []), ...(validation.warnings || [])];
  ruleStatus.textContent = "";
  if (messages.length) publishReport(messages.join("；"), { tone: "warning" });
  return true;
}
function hasUnsavedPolicyDraft() {
  const policy = policyLibrary.policies.find((item) => item.policy_id === selectedPolicyId);
  if (!policy || policyDetailPanel.hidden || !policyGraphState.draft) return false;
  const draft = getPolicyGraphDraft(policy);
  const sameGraph = JSON.stringify({
    bindings: draft.bindings || [], components: draft.components || [],
    node_order: draft.node_order || [], rail_settings: draft.rail_settings || {},
  }) === JSON.stringify({
    bindings: policy.bindings || [], components: policy.components || [],
    node_order: policy.node_order || [], rail_settings: policy.rail_settings || {},
  });
  return !sameGraph
    || policyNameInput.value.trim() !== String(policy.name || "")
    || policyDescriptionInput.value.trim() !== String(policy.description || "")
    || JSON.stringify(parseUmoList(policyUmoList.umoEditor?.value)) !== JSON.stringify(policy.umo_list || []);
}
function applyPolicyLibraryPayload(payload) {
  if (!payload?.success) throw new Error(payload?.error || "无法读取策略库。");
  if (hasUnsavedPolicyDraft()) {
    policyLibraryStatus.textContent = "";
    publishReport("检测到未保存的策略草稿，已保留本地编辑内容；未用远端数据覆盖。", { tone: "warning" });
    return false;
  }
  policyLibrary = {
    policies: Array.isArray(payload.policy_library?.policies) ? payload.policy_library.policies : [],
    active_policy_id: String(payload.policy_library?.active_policy_id || ""),
    umo_policy_selections: payload.policy_library?.umo_policy_selections
      && typeof payload.policy_library.umo_policy_selections === "object"
      ? payload.policy_library.umo_policy_selections : {},
  };
  const policy = selectedPolicyId
    ? policyLibrary.policies.find((item) => item.policy_id === selectedPolicyId) : null;
  if (policy) renderPolicyDetail(policy);
  else {
    selectedPolicyId = null;
    policyDetailPanel.hidden = true;
    policyListPanel.hidden = false;
    renderPolicyList();
  }
  if (pendingOverviewPolicyId) {
    const pending = policyLibrary.policies.find((item) => item.policy_id === pendingOverviewPolicyId);
    if (pending) showPolicyDetail(pending.policy_id);
    pendingOverviewPolicyId = null;
  }
  const validation = payload.validation || { warnings: [], fatal_errors: [] };
  const messages = [...(validation.fatal_errors || []), ...(validation.warnings || [])];
  policyLibraryStatus.textContent = "";
  if (messages.length) publishReport(messages.join("；"), { tone: "warning" });
  return true;
}
function applySystemSettingsPayload(payload) {
  if (!payload?.success) throw new Error(payload?.error || "无法读取系统设置。");
  if (systemSettingsDirty) {
    systemSettingsStatus.textContent = "";
    publishReport("检测到未保存的系统设置草稿，已保留本地编辑内容；未用远端数据覆盖。", { tone: "warning" });
    return false;
  }
  renderSystemSettings(payload);
  systemSettingsStatus.textContent = "";
  return true;
}
function applyProviderOptionsPayload(payload) {
  if (!payload?.success) throw new Error(payload?.error || "无法读取已注册 Provider 列表。");
  registeredProviders = Array.isArray(payload.providers)
    ? payload.providers.filter(
      (provider) => provider && typeof provider.id === "string" && typeof provider.name === "string",
    ) : [];
}
function applySharedConstantsPayload(payload) {
  if (!payload?.success) throw new Error(payload?.error || "无法读取公用常量。");
  if (sharedConstantsDirty) {
    ruleStatus.textContent = "";
    publishReport("检测到未保存的公用常量草稿，已保留本地编辑内容；未用远端数据覆盖。", { tone: "warning" });
    return false;
  }
  renderSharedConstantsEditor(payload.constants);
  return true;
}
async function loadTabData(name) {
  if (!bridge) return;
  const epoch = ++tabLoadEpoch;
  const isCurrent = () => epoch === tabLoadEpoch && activeTabName === name;
  status.textContent = `正在刷新${({ overview: "总览", rules: "规则库", policies: "策略编排", access: "访问控制", knowledge: "知识库经验", session: "会话策略监控", system: "系统设置" })[name] || "页面"}…`;
  try {
    if (name === "overview") {
      const [overviewResult, diagnosticsResult] = await Promise.all([
        bridge.apiGet("get_overview"), bridge.apiGet("get_diagnostics"),
      ]);
      if (!isCurrent()) return;
      applyOverviewPayload(overviewResult);
      latestDiagnostics = Array.isArray(diagnosticsResult?.diagnostics) ? diagnosticsResult.diagnostics : [];
      renderDiagnostics(latestDiagnostics);
      renderOverview(latestOverview);
      await Promise.all([refreshAccessControl(), refreshSessionPolicyStates(), refreshRagExperiences()]);
    } else if (name === "rules") {
      const [overviewResult, ruleResult, constantsResult, providersResult] = await Promise.all([
        bridge.apiGet("get_overview"), bridge.apiGet("get_rule_library"), bridge.apiGet("get_shared_constants"), bridge.apiGet("get_registered_providers"),
      ]);
      if (!isCurrent()) return;
      applyOverviewPayload(overviewResult);
      applyProviderOptionsPayload(providersResult);
      applyRuleLibraryPayload(ruleResult);
      applySharedConstantsPayload(constantsResult);
    } else if (name === "policies") {
      const [overviewResult, ruleResult, policyResult, providersResult] = await Promise.all([
        bridge.apiGet("get_overview"), bridge.apiGet("get_rule_library"), bridge.apiGet("get_policy_library"), bridge.apiGet("get_registered_providers"),
      ]);
      if (!isCurrent()) return;
      applyOverviewPayload(overviewResult);
      applyProviderOptionsPayload(providersResult);
      applyRuleLibraryPayload(ruleResult);
      applyPolicyLibraryPayload(policyResult);
    } else if (name === "system") {
      const [overviewResult, systemResult] = await Promise.all([
        bridge.apiGet("get_overview"), bridge.apiGet("get_system_settings"),
      ]);
      if (!isCurrent()) return;
      applyOverviewPayload(overviewResult);
      applySystemSettingsPayload(systemResult);
    } else if (name === "access") {
      await refreshAccessControl();
    } else if (name === "session") {
      const overviewResult = await bridge.apiGet("get_overview");
      if (!isCurrent()) return;
      applyOverviewPayload(overviewResult);
      await refreshSessionPolicyStates();
    } else if (name === "knowledge") {
      await refreshRagExperiences();
    }
    if (isCurrent()) status.textContent = "";
  } catch (error) {
    if (isCurrent()) {
      status.textContent = "";
      publishReport(`刷新页面数据失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
    }
  }
}
function isPolicyGraphShortcutEditableTarget(target) {
  return target instanceof Element
    && Boolean(target.closest("input, textarea, select, button, [contenteditable='true']"));
}
function handlePolicyGraphShortcut(event) {
  if (
    activeTabName !== "policies"
    || policyDetailPanel.hidden
    || event.isComposing
    || event.altKey
    || event.ctrlKey
    || event.metaKey
    || isPolicyGraphShortcutEditableTarget(event.target)
    || document.querySelector("dialog[open]")
  ) return;
  const nodeId = policyGraphState.selectedNodeId;
  const node = nodeId ? policyGraphState.model?.nodeById.get(nodeId) : null;
  if (!node) return;
  const key = event.key.toLowerCase();
  if (key === "d" && !event.shiftKey) {
    event.preventDefault();
    if (policyGraphState.dependencySelection?.dependentId === nodeId) {
      cancelPolicyDependencySelection("已取消依赖项选择。");
    } else beginPolicyDependencySelection(nodeId);
    return;
  }
  if (key === "d" && event.shiftKey) {
    event.preventDefault();
    clearPolicyGraphNodeDependency(nodeId);
    return;
  }
  if (event.key === "Delete" && event.shiftKey) {
    event.preventDefault();
    requestPolicyBindingRemoval(nodeId);
  }
}
document.addEventListener("keydown", handlePolicyGraphShortcut);
policyGraphCanvas.addEventListener("click", (event) => {
  const node = policyGraphNodeAt(event.clientX, event.clientY);
  const dependencySelection = policyGraphState.dependencySelection;
  if (dependencySelection) {
    if (node && policyGraphDependencyCandidates(dependencySelection.dependentId).has(node.id)) {
      openPolicyDependencyModeDialog(node.id);
    } else if (node) {
      setPolicyGraphEditorStatus("该节点不能作为依赖项：它必须已启用、位于当前或更早的 Step，且不会形成循环依赖。", true);
    } else {
      setPolicyGraphEditorStatus("请点击图中高亮的候选节点，或点击“取消选择依赖项”。");
    }
    schedulePolicyGraphRender();
    return;
  }
  const rail = node ? null : policyGraphRailAt(event.clientX, event.clientY);
  policyGraphState.selectedNodeId = node?.id || null;
  policyGraphState.selectedRail = rail;
  if (node) {
    const stateLabel = {
      available: "可用",
      disabled: "禁用",
      warning: "警告",
      unavailable: "不可用",
    }[node.state] || node.state;
    const issueText = node.issues.length ? ` · ${node.issues[0].message}` : "";
    const nodeType = node.component?.component_type || node.rule?.template_key || "未知节点";
    policyGraphStatus.textContent = `已选中 ${node.id} · ${templateDescriptions[nodeType] || componentDefinitions[nodeType]?.label || nodeType} · ${stateLabel}${issueText}`;
  } else if (rail) {
    policyGraphStatus.textContent = `已选中 ${policyGraphStepByRail.get(rail)?.label || rail}；可在下方编辑 Step 设置。`;
  } else if (policyGraphState.model) {
    policyGraphStatus.textContent = `共 ${policyGraphState.model.nodes.length} 个节点、${policyGraphState.model.edges.length} 条依赖。`;
  }
  renderPolicyGraphEditor();
  schedulePolicyGraphRender();
});
policyGraphCanvas.addEventListener("mousemove", (event) => {
  const node = policyGraphNodeAt(event.clientX, event.clientY);
  const nodeType = node?.component?.component_type || node?.rule?.template_key || "未知节点";
  policyGraphCanvas.title = node
    ? `${node.id} · ${templateDescriptions[nodeType] || componentDefinitions[nodeType]?.label || nodeType}`
    : "";
});
cancelPolicyDependencyMode.addEventListener("click", () => {
  policyDependencyModeDialog.close();
  cancelPolicyDependencySelection("已取消依赖项选择。");
});
confirmPolicyDependencyMode.addEventListener("click", applyPolicyDependencySelection);
policyDependencyModeDialog.addEventListener("cancel", () => {
  cancelPolicyDependencySelection("已取消依赖项选择。");
});
cancelPolicyBindingRemove.addEventListener("click", () => {
  pendingPolicyBindingRemovalId = null;
  confirmPolicyBindingRemoveDialog.close();
});
confirmPolicyBindingRemove.addEventListener("click", removePolicyBinding);
cancelPolicyRulePicker.addEventListener("click", () => {
  pendingPolicyBindingRail = null;
  policyRulePickerDialog.close();
});
confirmPolicyRulePicker.addEventListener("click", addSelectedPolicyRules);
policyRulePickerDialog.addEventListener("cancel", () => {
  pendingPolicyBindingRail = null;
});
cancelPolicyComponentCreation.addEventListener("click", () => {
  pendingPolicyComponentRail = null;
  selectedNewComponentType = null;
  policyComponentCreationDialog.close();
});
confirmPolicyComponentCreation.addEventListener("click", createPolicyComponent);
policyComponentCreationDialog.addEventListener("cancel", () => {
  pendingPolicyComponentRail = null;
  selectedNewComponentType = null;
});
closePolicySaveIssues.addEventListener("click", () => policySaveIssuesDialog.close());
if (window.ResizeObserver) {
  new window.ResizeObserver(() => {
    if (policyGraphIsVisible()) schedulePolicyGraphRender();
  }).observe(policyGraphStage);
}
window.addEventListener("resize", schedulePolicyGraphRender);
document.addEventListener("visibilitychange", updatePolicyGraphAnimation);
showRuleLibraryRules.addEventListener("click", () => switchRuleLibrarySection("rules"));
showSharedConstants.addEventListener("click", () => switchRuleLibrarySection("constants"));
exportRules.addEventListener("click", () => openConfigurationExport("rules"));
exportPolicies.addEventListener("click", () => openConfigurationExport("policies"));
importSharedConstants.addEventListener("click", () => openConfigurationImport("shared_constants"));
exportSharedConstants.addEventListener("click", async () => {
  try {
    const constants = await getSharedConstantsForExport();
    downloadConfigurationPackage(buildSharedConstantsExportPackage(constants));
    publishReport(`已生成 ${Object.keys(constants).length} 项公用常量的 JSON 导出文件。`);
  } catch (error) {
    publishReport(`无法导出公用常量：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
  }
});
importRules.addEventListener("click", () => openConfigurationImport("rules"));
importPolicies.addEventListener("click", () => openConfigurationImport("policies"));
cancelConfigurationExport.addEventListener("click", () => configurationExportDialog.close());
confirmConfigurationExport.addEventListener("click", async () => {
  const selectedIds = selectedConfigurationExportIds();
  if (!selectedIds.length) {
    configurationExportStatus.textContent = "请至少选择一项。";
    return;
  }
  confirmConfigurationExport.disabled = true;
  try {
    const constants = await getSharedConstantsForExport();
    downloadConfigurationPackage(
      buildConfigurationExportPackage(configurationExportKind, selectedIds, constants),
    );
    configurationExportDialog.close();
    publishReport(`已生成 ${selectedIds.length} 项配置的 JSON 导出文件。`);
  } catch (error) {
    configurationExportStatus.textContent = `无法导出配置：${error instanceof Error ? error.message : String(error)}`;
  } finally {
    confirmConfigurationExport.disabled = false;
  }
});
cancelConfigurationImport.addEventListener("click", () => configurationImportDialog.close());
configurationImportFile.addEventListener("change", previewConfigurationImport);
configurationImportMode.addEventListener("change", () => {
  if (configurationImportFile.files?.length) previewConfigurationImport();
});
confirmConfigurationImport.addEventListener("click", importConfigurationPackage);
newRule.addEventListener("click", startRuleCreation);
cancelRuleCreation.addEventListener("click", cancelNewRuleCreation);
confirmRuleCreation.addEventListener("click", createRule);
backToPolicyList.addEventListener("click", showPolicyList);
savePolicy.addEventListener("click", () => saveCurrentPolicy());
setDefaultPolicy.addEventListener("click", () => {
  const isDefaultPolicy = selectedPolicyId === policyLibrary.active_policy_id;
  return saveCurrentPolicy(!isDefaultPolicy, isDefaultPolicy);
});
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
saveSharedConstants.addEventListener("click", async () => {
  if (!Number.isInteger(currentRevision)) {
    publishReport("尚未加载当前配置，无法保存公用常量。", { tone: "warning" });
    return;
  }
  let constants;
  try {
    constants = collectSharedConstants();
  } catch (error) {
    publishReport(`无法保存公用常量：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
    return;
  }
  saveSharedConstants.disabled = true;
  try {
    const result = await bridge.apiPost("save_shared_constants", {
      expected_revision: currentRevision,
      constants,
    });
    if (!result.success) {
      publishReport(result.detail || result.error || "保存公用常量失败。", { tone: "error" });
      return;
    }
    sharedConstantsDirty = false;
    await loadTabData("rules");
    publishReport(`公用常量已发布为 revision ${result.revision}。`);
  } catch (error) {
    publishReport(`保存公用常量失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
  } finally {
    saveSharedConstants.disabled = false;
  }
});
saveSystemSettings.addEventListener("click", async () => {
  if (!Number.isInteger(currentRevision)) {
    systemSettingsStatus.textContent = "";
    publishReport("尚未加载当前配置，无法保存。", { tone: "warning" });
    return;
  }
  let settings;
  try {
    settings = collectSystemSettings();
  } catch (error) {
    systemSettingsStatus.textContent = "";
    publishReport(`无法保存：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
    return;
  }
  saveSystemSettings.disabled = true;
  try {
    const result = await bridge.apiPost("save_system_settings", {
      expected_revision: currentRevision,
      settings,
    });
    if (!result.success) {
      systemSettingsStatus.textContent = "";
      publishReport(result.detail || result.error || "保存失败。", { tone: "error" });
      return;
    }
    const successMessage = `系统设置已发布为 revision ${result.revision}。`;
    systemSettingsStatus.textContent = "";
    systemSettingsDirty = false;
    await loadTabData("system");
    publishReport(successMessage);
  } catch (error) {
    systemSettingsStatus.textContent = "";
    publishReport(`保存失败：${error instanceof Error ? error.message : String(error)}`, { tone: "error" });
  } finally {
    saveSystemSettings.disabled = false;
  }
});
accessDecision.addEventListener("change", () => renderAccessReasonCodeOptions());
accessDurationMode.addEventListener("change", syncAccessDurationControl);
accessDecisionFilter.addEventListener("change", renderAccessRecords);
refreshAccessRecords.addEventListener("click", refreshAccessControl);
saveAccessDecision.addEventListener("click", saveAccessDecisionMutation);
resetAccessForm.addEventListener("click", resetAccessFormState);
backToSessionPolicyList.addEventListener("click", showSessionPolicyStateList);
clearSessionPolicyState.addEventListener("click", () => {
  requestSessionPolicyStateDeletion();
});
cancelSessionPolicyStateDelete.addEventListener("click", () => {
  confirmSessionPolicyStateDeleteDialog.close();
});
confirmSessionPolicyStateDelete.addEventListener("click", () => {
  confirmSessionPolicyStateDeleteDialog.close();
  void clearCurrentSessionPolicyState();
});
saveSessionPolicySelection.addEventListener("click", () => {
  void saveCurrentSessionPolicySelection();
});
refreshSessionPolicyStatesButton.addEventListener("click", () => {
  void refreshSessionPolicyStates(true);
});
sessionPolicyStateQuery.addEventListener("change", () => {
  void refreshSessionPolicyStates(true);
});
sessionPolicyStateQuery.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    void refreshSessionPolicyStates(true);
  }
});
sessionPolicyStatePrevPage.addEventListener("click", () => {
  if (sessionPolicyStateCurrentPage <= 1) return;
  sessionPolicyStateCurrentPage -= 1;
  void refreshSessionPolicyStates();
});
sessionPolicyStateNextPage.addEventListener("click", () => {
  const totalPages = Math.max(1, Math.ceil(sessionPolicyStateTotal / sessionPolicyStatePageSize));
  if (sessionPolicyStateCurrentPage >= totalPages) return;
  sessionPolicyStateCurrentPage += 1;
  void refreshSessionPolicyStates();
});
backToRagExperienceList.addEventListener("click", showRagExperienceList);
refreshRagExperiencesButton.addEventListener("click", () => {
  void refreshRagExperiences(true);
});
ragExperienceQuery.addEventListener("change", () => {
  void refreshRagExperiences(true);
});
ragExperienceQuery.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    void refreshRagExperiences(true);
  }
});
ragExperiencePrevPage.addEventListener("click", () => {
  if (ragExperienceCurrentPage <= 1) return;
  ragExperienceCurrentPage -= 1;
  void refreshRagExperiences();
});
ragExperienceNextPage.addEventListener("click", () => {
  const totalPages = Math.max(1, Math.ceil(ragExperienceTotal / ragExperiencePageSize));
  if (ragExperienceCurrentPage >= totalPages) return;
  ragExperienceCurrentPage += 1;
  void refreshRagExperiences();
});
ragExperienceTitle.addEventListener("input", updateRagExperienceActionState);
ragExperienceContent.addEventListener("input", updateRagExperienceActionState);
saveRagExperience.addEventListener("click", () => {
  void saveCurrentRagExperience();
});
uploadRagExperience.addEventListener("click", () => {
  void uploadCurrentRagExperience();
});
deleteRagExperience.addEventListener("click", () => {
  requestRagExperienceDeletion();
});
cancelRagExperienceDelete.addEventListener("click", () => {
  confirmRagExperienceDeleteDialog.close();
});
confirmRagExperienceDelete.addEventListener("click", () => {
  confirmRagExperienceDeleteDialog.close();
  void deleteCurrentRagExperience();
});
resetAccessFormState();
updateRagExperienceActionState();
systemSettings.addEventListener("input", () => { systemSettingsDirty = true; });
systemSettings.addEventListener("change", () => { systemSettingsDirty = true; });
sharedConstants.addEventListener("input", () => { sharedConstantsDirty = true; });
sharedConstants.addEventListener("change", () => { sharedConstantsDirty = true; });
if (!bridge) {
  status.textContent = "当前不在 AstrBot Pages 环境中，无法读取或保存配置。";
} else {
  try {
    await bridge.ready();
    await loadTabData("overview");
  } catch (error) {
    status.textContent = `无法读取 Guardrail 状态：${error instanceof Error ? error.message : String(error)}`;
  }
}
