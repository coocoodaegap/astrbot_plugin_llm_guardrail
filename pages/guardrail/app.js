const bridge = window.AstrBotPluginPage;

const status = document.getElementById("status");
const summary = document.getElementById("snapshot-summary");
const rails = document.getElementById("rails");
const diagnostics = document.getElementById("diagnostics");
const ruleEditor = document.getElementById("rule-library");
const policyEditor = document.getElementById("policy-library");
const ruleStatus = document.getElementById("rule-library-status");
const policyStatus = document.getElementById("policy-library-status");
const saveRuleLibrary = document.getElementById("save-rule-library");
const savePolicyLibrary = document.getElementById("save-policy-library");
let currentRevision = null;

function addSummary(label, value) {
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  detail.textContent = String(value);
  summary.append(term, detail);
}

function renderOverview(overview) {
  summary.replaceChildren();
  addSummary("Revision", overview.revision);
  addSummary("Schema", overview.schema_version);
  addSummary("Warnings", overview.warning_count);
  addSummary("Active policy", overview.active_policy_id);
  addSummary("Graph", `${overview.graph.node_count} rules / ${overview.graph.edge_count} edges`);

  rails.replaceChildren();
  for (const [name, rail] of Object.entries(overview.rails)) {
    const item = document.createElement("article");
    item.className = "rail";
    const title = document.createElement("strong");
    title.textContent = name;
    const state = document.createElement("span");
    state.textContent = rail.enabled ? "enabled" : "disabled";
    const count = document.createElement("small");
    count.textContent = `${rail.enabled_rules}/${rail.total_rules} valid rules`;
    item.append(title, state, count);
    rails.append(item);
  }
}

function renderValidation(target, result, label) {
  const validation = result.validation || { warnings: [], fatal_errors: [] };
  const messages = [...(validation.fatal_errors || []), ...(validation.warnings || [])];
  target.textContent = messages.length
    ? `revision ${result.revision}: ${messages.join("; ")}`
    : `revision ${result.revision}: ${label}有效。`;
}

function renderDiagnostics(items) {
  diagnostics.replaceChildren();
  if (!items.length) {
    const item = document.createElement("li");
    item.textContent = "未发现配置诊断。";
    diagnostics.append(item);
    return;
  }
  for (const message of items) {
    const item = document.createElement("li");
    item.textContent = message;
    diagnostics.append(item);
  }
}

async function refresh() {
  const [overviewResult, diagnosticsResult, ruleResult, policyResult] = await Promise.all([
    bridge.apiGet("get_overview"),
    bridge.apiGet("get_diagnostics"),
    bridge.apiGet("get_rule_library"),
    bridge.apiGet("get_policy_library"),
  ]);
  currentRevision = overviewResult.overview.revision;
  renderOverview(overviewResult.overview);
  renderDiagnostics(diagnosticsResult.diagnostics || []);
  ruleEditor.value = JSON.stringify(ruleResult.rule_library, null, 2);
  policyEditor.value = JSON.stringify(policyResult.policy_library, null, 2);
  renderValidation(ruleStatus, ruleResult, "规则库");
  renderValidation(policyStatus, policyResult, "策略库");
  status.textContent = `已加载配置快照 revision ${currentRevision}`;
}

function bindSave(button, editor, statusTarget, endpoint, field, label) {
  button.addEventListener("click", async () => {
    if (!Number.isInteger(currentRevision)) {
      statusTarget.textContent = "尚未加载当前配置，无法保存。";
      return;
    }
    let library;
    try {
      library = JSON.parse(editor.value);
    } catch (error) {
      statusTarget.textContent = `JSON 格式错误：${error instanceof Error ? error.message : String(error)}`;
      return;
    }
    button.disabled = true;
    try {
      const result = await bridge.apiPost(endpoint, {
        expected_revision: currentRevision,
        [field]: library,
      });
      if (!result.success) {
        statusTarget.textContent = result.detail || result.error || "保存失败。";
        return;
      }
      statusTarget.textContent = `${label}已发布为 revision ${result.revision}。`;
      await refresh();
    } catch (error) {
      statusTarget.textContent = `保存失败：${error instanceof Error ? error.message : String(error)}`;
    } finally {
      button.disabled = false;
    }
  });
}

bindSave(saveRuleLibrary, ruleEditor, ruleStatus, "save_rule_library", "rule_library", "规则库");
bindSave(savePolicyLibrary, policyEditor, policyStatus, "save_policy_library", "policy_library", "策略库");

try {
  await bridge.ready();
  await refresh();
} catch (error) {
  status.textContent = `无法读取 Guardrail 状态：${error instanceof Error ? error.message : String(error)}`;
}
