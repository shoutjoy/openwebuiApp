const state = {
  config: null,
  status: null,
  toastTimer: null,
  installCmdScript: "",
  installSteps: [],
  modelInstallCommand: "",
  modelInstallSteps: [],
  academicSearchToolContent: "",
  academicSearchToolSteps: [],
  academicFormattedResults: "",
  academicReviewPrompt: "",
};

const $ = (selector) => document.querySelector(selector);

function applyTheme(theme) {
  const cleanTheme = theme === "dark" ? "dark" : "light";
  document.documentElement.dataset.theme = cleanTheme;
  localStorage.setItem("openwebuiLauncherTheme", cleanTheme);
  const button = $("#themeToggleBtn");
  if (button) {
    button.title = cleanTheme === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환";
    button.setAttribute("aria-label", button.title);
  }
}

function initializeTheme() {
  const saved = localStorage.getItem("openwebuiLauncherTheme");
  const preferredDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches;
  applyTheme(saved || (preferredDark ? "dark" : "light"));
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  applyTheme(current === "dark" ? "light" : "dark");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || response.statusText);
  }
  return data;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message || "";
  el.classList.add("show");
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function fillConfig(config) {
  state.config = config;
  const form = $("#settingsForm");
  for (const [key, value] of Object.entries(config)) {
    const field = form.elements[key];
    if (!field) continue;
    if (field.type === "checkbox") {
      field.checked = Boolean(value);
    } else {
      field.value = value ?? "";
    }
  }
  $("#modelInput").value = config.selected_model || "llama3.1:8b";
  updateModelCommand();
}

function collectConfig() {
  const form = $("#settingsForm");
  return {
    command: form.elements.command.value,
    venv_command: form.elements.venv_command.value,
    python_path: form.elements.python_path?.value || "",
    open_webui_path: form.elements.open_webui_path?.value || "",
    host: form.elements.host.value,
    port: Number(form.elements.port.value),
    startup_timeout_seconds: Number(form.elements.startup_timeout_seconds.value),
    selected_model: form.elements.selected_model.value,
    auto_open_browser: form.elements.auto_open_browser.checked,
    auto_start_server: form.elements.auto_start_server.checked,
  };
}

function renderStatus(data) {
  state.status = data;
  const status = $("#serverStatus");
  status.textContent = data.status_text;
  status.classList.toggle("running", Boolean(data.running));
  status.classList.toggle("stopped", !data.running);
  $("#serverUrl").textContent = data.server_url;
  $("#lastEvent").textContent = data.last_event || "대기 중";
  $("#startLocalBtn").disabled = data.starting || !data.local_ready;
  $("#startVenvBtn").disabled = data.starting || !data.venv_ready;
  $("#startAutoBtn").disabled = data.starting;
  $("#stopBtn").disabled = data.starting;
  $("#contextMenuStatus").textContent = data.context_menu_registered ? "등록됨" : "등록 안 됨";
}

async function refreshStatus() {
  const data = await api("/api/status");
  renderStatus(data);
  return data;
}

async function loadConfig() {
  fillConfig(await api("/api/config"));
}

async function saveConfig() {
  const data = await api("/api/config", {
    method: "POST",
    body: JSON.stringify(collectConfig()),
  });
  fillConfig(data.config);
  toast(data.message);
  await refreshStatus();
}

async function startServer(mode) {
  const data = await api("/api/server/start", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
  toast(data.message);
  await refreshStatus();
}

async function stopServer() {
  const data = await api("/api/server/stop", { method: "POST" });
  toast(data.message);
  await refreshStatus();
}

async function openChat() {
  const data = await api("/api/server/open", { method: "POST" });
  toast(data.message || data.url);
}

async function checkVenv() {
  const data = await api("/api/install/venv");
  const container = $("#venvChecks");
  container.innerHTML = "";
  for (const item of data.checks) {
    const row = document.createElement("div");
    row.className = "check-item";
    row.innerHTML = `
      <span class="badge ${item.exists ? "ok" : "no"}">${item.exists ? "OK" : "NO"}</span>
      <strong>${item.label}</strong>
      <span class="path">${item.path}</span>
    `;
    container.appendChild(row);
  }
  toast(data.ready ? "가상환경 설치를 확인했습니다." : "누락된 가상환경 항목이 있습니다.");
  await refreshStatus();
}

async function installOpenWebui() {
  const data = await api("/api/install/openwebui", { method: "POST" });
  renderInstallCommand(data, true);
  toast(data.message);
}

async function pipUpgrade() {
  const data = await api("/api/install/pip-upgrade", { method: "POST" });
  toast(data.message);
}

async function showInstallCommand() {
  if (!$("#installGuide").hidden) {
    $("#installGuide").hidden = true;
    $("#copyInstallCommandBtn").textContent = "단계적 설치하기";
    toast("단계별 설치 설명을 접었습니다.");
    return;
  }
  const data = await api("/api/install/command");
  renderInstallCommand(data, true);
  toast("단계별 설치 설명과 CMD 명령을 펼쳤습니다.");
}

function renderInstallCommand(data, expandGuide = false) {
  state.installCmdScript = data.cmd_script || data.command || "";
  state.installSteps = data.steps || [];
  $("#installGuide").hidden = !expandGuide;
  $("#copyInstallCommandBtn").textContent = expandGuide ? "접어두기" : "단계적 설치하기";
  $("#installCommand").value = state.installCmdScript;

  const list = $("#installSteps");
  list.innerHTML = "";
  state.installSteps.forEach((step, index) => {
    const item = document.createElement("article");
    item.className = "install-step";
    const title = `${index + 1}. ${step.title || "설치 단계"}`;
    const description = step.description || "";
    const code = step.code || "";
    item.innerHTML = `
      <div class="install-step-head">
        <div>
          <h4>${escapeHtml(title)}</h4>
          <p>${escapeHtml(description)}</p>
        </div>
        <div class="step-actions">
          <button type="button" data-copy-description="${index}">설명 복사</button>
          <button type="button" data-copy-code="${index}">코드 복사</button>
        </div>
      </div>
      <textarea class="step-code" rows="${Math.max(2, code.split(/\r?\n/).length + 1)}" readonly>${escapeHtml(code)}</textarea>
    `;
    item.querySelector("[data-copy-description]").addEventListener("click", () => copyStepDescription(index));
    item.querySelector("[data-copy-code]").addEventListener("click", () => copyStepCode(index, item.querySelector(".step-code")));
    list.appendChild(item);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function copyStepDescription(index) {
  const step = state.installSteps[index];
  if (!step) return;
  const text = `${index + 1}. ${step.title}\n${step.description}`;
  await copyText(text);
  toast("단계 설명을 복사했습니다.");
}

async function copyStepCode(index, fallbackField) {
  const step = state.installSteps[index];
  if (!step) return;
  await copyText(step.code || "", fallbackField);
  toast("단계 CMD 코드를 복사했습니다.");
}

async function copyInstallCommand() {
  if (!state.installCmdScript) {
    const data = await api("/api/install/command");
    renderInstallCommand(data, true);
  }
  await copyText(state.installCmdScript, $("#installCommand"));
  toast("전체 CMD 붙여넣기용 명령을 복사했습니다.");
}

async function copyText(text, fallbackField = null) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const field = fallbackField || document.createElement("textarea");
  if (!fallbackField) {
    field.value = text;
    field.style.position = "fixed";
    field.style.left = "-9999px";
    document.body.appendChild(field);
  }
  field.focus();
  field.select();
  document.execCommand("copy");
  if (!fallbackField) {
    field.remove();
  }
}

function renderModels(data) {
  const list = $("#modelList");
  list.innerHTML = "";
  const models = data.models.length ? data.models : data.popular_models;
  $("#modelStatus").textContent = data.message || "";
  for (const model of models) {
    const button = document.createElement("button");
    button.className = "model-item";
    button.textContent = model;
    button.addEventListener("click", () => {
      $("#modelInput").value = model;
      $("#settingsForm").elements.selected_model.value = model;
      updateModelCommand();
    });
    list.appendChild(button);
  }
  if (data.selected_model) {
    $("#modelInput").value = data.selected_model;
  }
  updateModelCommand();
}

async function refreshModels() {
  const data = await api("/api/models");
  renderModels(data);
  if (!data.ok) toast(data.message);
}

async function updateModelCommand() {
  const model = $("#modelInput").value;
  const data = await api(`/api/models/command?model=${encodeURIComponent(model)}`);
  state.modelInstallCommand = data.command || "";
  state.modelInstallSteps = data.steps || [];
  $("#modelCommand").value = data.command || data.message || "";
  updateModelLinks(model, data);
  if (!$("#modelGuide").hidden) {
    renderModelGuide();
  }
}

function updateModelLinks(model, data = {}) {
  const cleanModel = String(model || "").trim();
  const modelBase = cleanModel.split(":")[0] || "llama3.1";
  const libraryUrl = data.library_url || "https://ollama.com/library";
  const modelUrl = data.model_url || `${libraryUrl}/${encodeURIComponent(modelBase)}`;
  $("#ollamaLibraryLink").href = libraryUrl;
  $("#selectedModelLink").href = modelUrl;
  $("#selectedModelLink").textContent = cleanModel ? `${modelBase} 모델 페이지` : "선택 모델 페이지";
}

async function saveModel() {
  const model = $("#modelInput").value;
  const data = await api("/api/models/save", {
    method: "POST",
    body: JSON.stringify({ model }),
  });
  $("#settingsForm").elements.selected_model.value = data.model;
  toast(data.message);
  await loadConfig();
}

async function copyModelCommand() {
  if (!state.modelInstallCommand) {
    await updateModelCommand();
  }
  await copyText(state.modelInstallCommand, $("#modelCommand"));
  toast("선택 모델 설치 CMD 명령을 복사했습니다. CMD 창에 붙여넣어 실행하십시오.");
}

async function toggleModelGuide() {
  if (!$("#modelGuide").hidden) {
    $("#modelGuide").hidden = true;
    $("#toggleModelGuideBtn").textContent = "모델 설치 과정 보기";
    toast("Ollama 모델 설치 과정을 접었습니다.");
    return;
  }
  if (!state.modelInstallSteps.length) {
    await updateModelCommand();
  }
  $("#modelGuide").hidden = false;
  $("#toggleModelGuideBtn").textContent = "모델 설치 과정 접기";
  renderModelGuide();
  toast("Ollama 모델 설치 과정을 펼쳤습니다.");
}

function renderModelGuide() {
  const list = $("#modelInstallSteps");
  list.innerHTML = "";
  state.modelInstallSteps.forEach((step, index) => {
    const item = document.createElement("article");
    item.className = "install-step model-install-step";
    const title = `${index + 1}. ${step.title || "모델 설치 단계"}`;
    const description = step.description || "";
    const code = step.code || "";
    item.innerHTML = `
      <div class="install-step-head">
        <div>
          <h4>${escapeHtml(title)}</h4>
          <p>${escapeHtml(description)}</p>
        </div>
        <div class="step-actions">
          <button type="button" data-copy-model-description="${index}">설명 복사</button>
          <button type="button" data-copy-model-code="${index}">코드 복사</button>
        </div>
      </div>
      <textarea class="step-code" rows="${Math.max(2, code.split(/\r?\n/).length + 1)}" readonly>${escapeHtml(code)}</textarea>
    `;
    item.querySelector("[data-copy-model-description]").addEventListener("click", () => copyModelStepDescription(index));
    item.querySelector("[data-copy-model-code]").addEventListener("click", () => copyModelStepCode(index, item.querySelector(".step-code")));
    list.appendChild(item);
  });
}

async function copyModelStepDescription(index) {
  const step = state.modelInstallSteps[index];
  if (!step) return;
  await copyText(`${index + 1}. ${step.title}\n${step.description}`);
  toast("모델 설치 단계 설명을 복사했습니다.");
}

async function copyModelStepCode(index, fallbackField) {
  const step = state.modelInstallSteps[index];
  if (!step) return;
  await copyText(step.code || "", fallbackField);
  toast("모델 설치 단계 CMD 코드를 복사했습니다.");
}

async function loadIntegrations() {
  const data = await api("/api/integrations");
  const container = $("#integrations");
  container.innerHTML = "";
  for (const item of data.integrations) {
    const card = document.createElement("div");
    card.className = "integration-card";
    card.innerHTML = `
      <h3>${item.name}</h3>
      <p>${item.description}</p>
      <button data-id="${item.id}">열기</button>
    `;
    card.querySelector("button").addEventListener("click", () => openIntegration(item.id));
    container.appendChild(card);
  }
  const downloadCard = document.createElement("div");
  downloadCard.className = "integration-card download-integration-card";
  downloadCard.innerHTML = `
    <h3>Windows EXE</h3>
    <p>Windows PC에서 로컬 Open WebUI를 직접 실행할 때 사용합니다.</p>
    <a class="button-link compact-link" href="/downloads/OpenWebUI-Local-AI-Launcher-Tabbed-v6.exe" download>EXE 다운로드</a>
  `;
  container.appendChild(downloadCard);
}

async function loadAcademicSearchTool() {
  if (!$("#academicSearchToolGuide").hidden) {
    $("#academicSearchToolGuide").hidden = true;
    $("#loadAcademicSearchToolBtn").textContent = "Tool 보기";
    toast("학술 검색 Tool 안내를 접었습니다.");
    return;
  }
  const data = await api("/api/academic-search/tool");
  state.academicSearchToolContent = data.content || "";
  state.academicSearchToolSteps = data.steps || [];
  $("#academicSearchToolTitle").textContent = data.name || "Academic Verified Search";
  $("#academicSearchToolPath").textContent = data.path || "";
  $("#academicSearchToolCode").value = state.academicSearchToolContent;
  renderAcademicSearchToolSteps();
  $("#academicSearchToolGuide").hidden = false;
  $("#loadAcademicSearchToolBtn").textContent = "접어두기";
  toast("Open WebUI 채팅용 학술 검색 Tool 코드를 펼쳤습니다.");
}

function renderAcademicSearchToolSteps() {
  const list = $("#academicSearchToolSteps");
  list.innerHTML = "";
  state.academicSearchToolSteps.forEach((step, index) => {
    const item = document.createElement("article");
    item.className = "citation-step";
    item.innerHTML = `
      <h4>${index + 1}. ${escapeHtml(step.title || "설치 단계")}</h4>
      <p>${escapeHtml(step.description || "")}</p>
    `;
    list.appendChild(item);
  });
}

async function copyAcademicSearchToolCode() {
  if (!state.academicSearchToolContent) {
    const data = await api("/api/academic-search/tool");
    state.academicSearchToolContent = data.content || "";
    $("#academicSearchToolCode").value = state.academicSearchToolContent;
  }
  await copyText(state.academicSearchToolContent, $("#academicSearchToolCode"));
  toast("Academic Verified Search Tool 코드를 복사했습니다.");
}

async function ensureAcademicSearchToolContent() {
  if (state.academicSearchToolContent) {
    return state.academicSearchToolContent;
  }
  const data = await api("/api/academic-search/tool");
  state.academicSearchToolContent = data.content || "";
  state.academicSearchToolSteps = data.steps || [];
  const topCode = $("#academicSearchToolCode");
  if (topCode) topCode.value = state.academicSearchToolContent;
  const topTitle = $("#academicSearchToolTitle");
  if (topTitle) topTitle.textContent = data.name || "Academic Verified Search";
  const topPath = $("#academicSearchToolPath");
  if (topPath) topPath.textContent = data.path || "";
  const bottomPath = $("#bottomAcademicToolPath");
  if (bottomPath) bottomPath.textContent = data.path || "openwebui_tools/academic_verified_search_tool.py";
  return state.academicSearchToolContent;
}

async function toggleBottomAcademicToolCode() {
  const wrap = $("#bottomAcademicToolCodeWrap");
  const button = $("#toggleBottomAcademicToolBtn");
  if (!wrap || !button) return;
  if (!wrap.hidden) {
    wrap.hidden = true;
    button.textContent = "전체 코드 펼치기";
    toast("전체 Tool 코드를 접었습니다.");
    return;
  }
  const content = await ensureAcademicSearchToolContent();
  $("#bottomAcademicToolCode").value = content;
  wrap.hidden = false;
  button.textContent = "전체 코드 접기";
  toast("전체 Tool 코드를 펼쳤습니다.");
}

async function copyBottomAcademicToolCode() {
  const content = await ensureAcademicSearchToolContent();
  const field = $("#bottomAcademicToolCode");
  if (field) field.value = content;
  await copyText(content, field);
  toast("하단 전체 Tool 코드를 복사했습니다.");
}

function toggleAcademicRagPanel() {
  const body = $("#academicRagPanelBody");
  const button = $("#toggleAcademicRagPanelBtn");
  if (!body || !button) return;
  const opening = body.hidden;
  body.hidden = !opening;
  button.textContent = opening ? "접어두기" : "펼치기";
  toast(opening ? "학술 검색 결과 복사 영역을 펼쳤습니다." : "학술 검색 결과 복사 영역을 접었습니다.");
}

async function sendAcademicRag() {
  const question = ($("#academicRagQuestion")?.value || "").trim();
  const maxResults = Number($("#academicRagMaxResults")?.value || 8);
  if (!question) {
    toast("학술 질문을 입력하십시오.");
    return;
  }
  $("#academicRagAnswer").textContent = "학술 DB 검색 후 모델에 전달하는 중...";
  $("#academicRagSources").innerHTML = "";
  const data = await api("/api/academic-rag/answer", {
    method: "POST",
    body: JSON.stringify({ question, max_results: maxResults }),
  });
  if (!data.ok) {
    $("#academicRagAnswer").textContent = data.message || "학술 RAG 처리에 실패했습니다.";
    toast(data.message || "학술 RAG 처리에 실패했습니다.");
    return;
  }
  $("#academicRagAnswer").textContent = data.answer || "";
  renderAcademicSources(data.sources || []);
  toast(`검증 후보 ${data.sources?.length || 0}개로 답변을 생성했습니다.`);
}

async function searchAcademicSources() {
  const query = ($("#academicRagQuestion")?.value || "").trim();
  const maxResults = Number($("#academicRagMaxResults")?.value || 10);
  if (!query) {
    toast("검색어 또는 연구 질문을 입력하십시오.");
    return;
  }
  $("#academicSearchResults").value = "외부 학술 DB 검색 중...";
  $("#academicReviewPrompt").value = "";
  $("#academicRagAnswer").textContent = "";
  $("#academicRagSources").innerHTML = "";
  const data = await api("/api/academic-rag/search", {
    method: "POST",
    body: JSON.stringify({ query, max_results: maxResults }),
  });
  if (!data.ok) {
    $("#academicSearchResults").value = data.message || "학술 검색 결과 생성에 실패했습니다.";
    toast(data.message || "학술 검색 결과 생성에 실패했습니다.");
    return;
  }
  state.academicFormattedResults = data.formatted_results || "";
  state.academicReviewPrompt = data.copy_prompt || "";
  $("#academicSearchResults").value = state.academicFormattedResults;
  $("#academicReviewPrompt").value = state.academicReviewPrompt;
  renderAcademicSources(data.sources || []);
  toast(`APA+초록 검색 결과 ${data.count || 0}건을 만들었습니다.`);
}

async function copyAcademicResults() {
  if (!state.academicFormattedResults) {
    state.academicFormattedResults = $("#academicSearchResults")?.value || "";
  }
  if (!state.academicFormattedResults) {
    await searchAcademicSources();
  }
  await copyText(state.academicFormattedResults, $("#academicSearchResults"));
  toast("APA+초록 학술검색 결과를 복사했습니다.");
}

async function copyAcademicPrompt() {
  if (!state.academicReviewPrompt) {
    state.academicReviewPrompt = $("#academicReviewPrompt")?.value || "";
  }
  if (!state.academicReviewPrompt) {
    await searchAcademicSources();
  }
  await copyText(state.academicReviewPrompt, $("#academicReviewPrompt"));
  toast("Open WebUI에 붙여넣을 AI 정리 프롬프트를 복사했습니다.");
}

function renderAcademicSources(sources) {
  const container = $("#academicRagSources");
  if (!container) return;
  container.innerHTML = "";
  sources.forEach((source) => {
    const card = document.createElement("article");
    card.className = "academic-source-card";
    const doiOrUrl = source.doi
      ? `https://doi.org/${source.doi}`
      : source.url || "";
    card.innerHTML = `
      <div class="academic-source-head">
        <strong>${escapeHtml(source.id || "")}</strong>
        <span>${escapeHtml(source.source || "")}</span>
      </div>
      <h3>${escapeHtml(source.title || "")}</h3>
      <p>${escapeHtml(source.authors || "저자 정보 없음")}</p>
      <p>${escapeHtml([source.year, source.venue].filter(Boolean).join(" · "))}</p>
      <textarea rows="4" readonly>${escapeHtml(source.citation || "")}</textarea>
      ${doiOrUrl ? `<a href="${escapeHtml(doiOrUrl)}" target="_blank" rel="noopener noreferrer">원문/메타데이터 열기</a>` : ""}
    `;
    container.appendChild(card);
  });
}

async function openIntegration(id) {
  const data = await api("/api/integrations/open", {
    method: "POST",
    body: JSON.stringify({ id }),
  });
  toast(data.message);
}

async function sendChat() {
  const message = $("#chatMessage").value;
  $("#chatReply").textContent = "요청 중...";
  const data = await api("/api/openwebui/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  $("#chatReply").textContent = data.ok ? formatReply(data.reply) : data.message;
}

function formatReply(reply) {
  if (typeof reply === "string") return reply;
  return JSON.stringify(reply, null, 2);
}

function bindIfPresent(selector, eventName, handler) {
  const element = $(selector);
  if (!element) return;
  element.addEventListener(eventName, handler);
}

async function registerContextMenu() {
  const data = await api("/api/context-menu/register", { method: "POST" });
  toast(data.message);
  await refreshStatus();
}

async function detectRuntime() {
  const data = await api("/api/runtime/detect", { method: "POST" });
  fillConfig(data.config);
  toast(data.message);
  await refreshStatus();
}

async function unregisterContextMenu() {
  const data = await api("/api/context-menu/unregister", { method: "POST" });
  toast(data.message);
  await refreshStatus();
}

function bindEvents() {
  bindIfPresent("#refreshBtn", "click", refreshStatus);
  bindIfPresent("#themeToggleBtn", "click", toggleTheme);
  bindIfPresent("#saveConfigBtn", "click", saveConfig);
  bindIfPresent("#detectRuntimeBtn", "click", detectRuntime);
  bindIfPresent("#startAutoBtn", "click", () => startServer("auto"));
  bindIfPresent("#startLocalBtn", "click", () => startServer("local"));
  bindIfPresent("#startVenvBtn", "click", () => startServer("venv"));
  bindIfPresent("#openChatBtn", "click", openChat);
  bindIfPresent("#stopBtn", "click", stopServer);
  bindIfPresent("#loadAcademicSearchToolBtn", "click", loadAcademicSearchTool);
  bindIfPresent("#copyAcademicSearchToolBtn", "click", copyAcademicSearchToolCode);
  bindIfPresent("#toggleBottomAcademicToolBtn", "click", toggleBottomAcademicToolCode);
  bindIfPresent("#copyBottomAcademicToolBtn", "click", copyBottomAcademicToolCode);
  bindIfPresent("#toggleAcademicRagPanelBtn", "click", toggleAcademicRagPanel);
  bindIfPresent("#searchAcademicSourcesBtn", "click", searchAcademicSources);
  bindIfPresent("#copyAcademicResultsBtn", "click", copyAcademicResults);
  bindIfPresent("#copyAcademicPromptBtn", "click", copyAcademicPrompt);
  bindIfPresent("#sendAcademicRagBtn", "click", sendAcademicRag);
  bindIfPresent("#checkVenvBtn", "click", checkVenv);
  bindIfPresent("#installOpenWebuiBtn", "click", installOpenWebui);
  bindIfPresent("#pipUpgradeBtn", "click", pipUpgrade);
  bindIfPresent("#copyInstallCommandBtn", "click", showInstallCommand);
  bindIfPresent("#copyInstallCmdBtn", "click", copyInstallCommand);
  bindIfPresent("#refreshModelsBtn", "click", refreshModels);
  bindIfPresent("#modelInput", "input", updateModelCommand);
  bindIfPresent("#saveModelBtn", "click", saveModel);
  bindIfPresent("#copyModelCommandBtn", "click", copyModelCommand);
  bindIfPresent("#toggleModelGuideBtn", "click", toggleModelGuide);
  bindIfPresent("#sendChatBtn", "click", sendChat);
  bindIfPresent("#registerContextBtn", "click", registerContextMenu);
  bindIfPresent("#unregisterContextBtn", "click", unregisterContextMenu);
}

async function boot() {
  initializeTheme();
  bindEvents();
  await loadConfig();
  await Promise.all([refreshStatus(), checkVenv(), refreshModels(), loadIntegrations()]);
  setInterval(refreshStatus, 5000);
}

boot().catch((error) => {
  console.error(error);
  toast(error.message);
});
