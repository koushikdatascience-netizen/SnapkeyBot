let token = localStorage.getItem("token");
let conciergeMode = false;
initialize();

async function initialize() {
  await loadConfig();
  if (token) showWorkspace();
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const config = await response.json();
  conciergeMode = config.concierge_mode;
  if (conciergeMode) {
    document.querySelector("#preview-badge").classList.remove("hidden");
    document.querySelector("#welcome-message").textContent = "This preview is supported by a human concierge. Ask anything about the product.";
  }
}

function addMessage(label, text, className = "") {
  const item = document.createElement("p");
  item.className = className;
  const heading = document.createElement("strong");
  heading.textContent = `${label}: `;
  item.append(heading, document.createTextNode(text));
  messages.append(item);
  messages.scrollTop = messages.scrollHeight;
  return item;
}

async function api(path, options = {}) {
  options.headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) options.headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
}

async function authenticate(action) {
  try {
    const body = await api(`/auth/${action}`, { method: "POST", body: JSON.stringify({ email: email.value, password: password.value }) });
    token = body.access_token;
    localStorage.setItem("token", token);
    showWorkspace();
  } catch (error) { alert(error.message); }
}

function showWorkspace() {
  document.querySelector("#auth").classList.add("hidden");
  document.querySelector("#workspace").classList.remove("hidden");
  if (conciergeMode) {
    tools.closest(".panel").classList.add("concierge");
  } else {
    loadTools();
  }
}

async function loadTools() {
  const items = await api("/tools");
  tools.innerHTML = items.map(tool => `<article class="tool"><strong>${tool.name}</strong><p>${tool.description}</p><small>${tool.risk} risk | ${tool.required_permission}</small><button class="${tool.connected ? "quiet" : ""}" onclick='connectTool(${JSON.stringify(tool.name)}, ${JSON.stringify(tool.credential_fields)})'>${tool.connected ? "Reconnect" : "Connect"}</button></article>`).join("");
}

async function connectTool(name, credentialFields = []) {
  const credentials = {};
  for (const field of credentialFields) {
    const value = window.prompt(`Enter ${field} for ${name}. It will be encrypted before storage.`);
    if (!value) return;
    credentials[field] = value;
  }
  await api(`/tools/${name}`, { method: "PUT", body: JSON.stringify({ credentials, permissions: [] }) });
  await loadTools();
}

async function sendPrompt() {
  const text = prompt.value.trim();
  if (!text) return;
  addMessage("You", text);
  prompt.value = "";
  try {
    const task = await api("/chat", { method: "POST", body: JSON.stringify({ prompt: text }) });
    const pending = addMessage("Snapkey", conciergeMode ? "Your concierge is reviewing this now..." : "Working...", "pending");
    pollTask(task.id, pending);
  } catch (error) { addMessage("Error", error.message); }
}

async function pollTask(id, pending) {
  try {
    const task = await api(`/chat/tasks/${id}`);
    if (task.status === "succeeded") {
      pending?.remove();
      addMessage("Snapkey", task.result.message);
    } else if (task.status === "failed") {
      pending?.remove();
      addMessage("Failed", task.error);
    } else {
      setTimeout(() => pollTask(id, pending), 1000);
    }
  } catch (error) {
    pending?.remove();
    addMessage("Error", error.message);
  }
}
