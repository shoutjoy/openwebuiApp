const state = {
  config: null,
  status: null,
  toastTimer: null,
};

const $ = (selector) => document.querySelector(selector);

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
  $("#installCommand").textContent = data.command || "";
  toast(data.message);
}

async function pipUpgrade() {
  const data = await api("/api/install/pip-upgrade", { method: "POST" });
  toast(data.message);
}

async function showInstallCommand() {
  const data = await api("/api/install/command");
  $("#installCommand").textContent = data.command;
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
  $("#modelCommand").textContent = data.command || data.message || "";
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

async function installModel() {
  const model = $("#modelInput").value;
  const data = await api("/api/models/install", {
    method: "POST",
    body: JSON.stringify({ model }),
  });
  toast(data.message);
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

async function registerContextMenu() {
  const data = await api("/api/context-menu/register", { method: "POST" });
  toast(data.message);
  await refreshStatus();
}

async function unregisterContextMenu() {
  const data = await api("/api/context-menu/unregister", { method: "POST" });
  toast(data.message);
  await refreshStatus();
}

function bindEvents() {
  $("#refreshBtn").addEventListener("click", refreshStatus);
  $("#saveConfigBtn").addEventListener("click", saveConfig);
  $("#startAutoBtn").addEventListener("click", () => startServer("auto"));
  $("#startLocalBtn").addEventListener("click", () => startServer("local"));
  $("#startVenvBtn").addEventListener("click", () => startServer("venv"));
  $("#openChatBtn").addEventListener("click", openChat);
  $("#stopBtn").addEventListener("click", stopServer);
  $("#checkVenvBtn").addEventListener("click", checkVenv);
  $("#installOpenWebuiBtn").addEventListener("click", installOpenWebui);
  $("#pipUpgradeBtn").addEventListener("click", pipUpgrade);
  $("#copyInstallCommandBtn").addEventListener("click", showInstallCommand);
  $("#refreshModelsBtn").addEventListener("click", refreshModels);
  $("#modelInput").addEventListener("input", updateModelCommand);
  $("#saveModelBtn").addEventListener("click", saveModel);
  $("#installModelBtn").addEventListener("click", installModel);
  $("#sendChatBtn").addEventListener("click", sendChat);
  $("#registerContextBtn").addEventListener("click", registerContextMenu);
  $("#unregisterContextBtn").addEventListener("click", unregisterContextMenu);
}

async function boot() {
  bindEvents();
  await loadConfig();
  await Promise.all([refreshStatus(), checkVenv(), refreshModels(), loadIntegrations()]);
  setInterval(refreshStatus, 5000);
}

boot().catch((error) => {
  console.error(error);
  toast(error.message);
});
