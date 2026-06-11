let token = localStorage.getItem("token");
let conciergeMode = false;
let conciergeReady = false;
let selectedAttachment = null;
let recorder = null;
let recordingChunks = [];
let maxUploadBytes = 15000000;

initialize();

async function initialize() {
  await loadConfig();
  if (token) showWorkspace();
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    const config = await response.json();
    conciergeMode = config.concierge_mode;
    conciergeReady = config.concierge_ready;
    maxUploadBytes = config.max_upload_bytes || maxUploadBytes;
    setConnectionStatus(conciergeReady ? "Concierge online" : "Setup required", conciergeReady);
    document.querySelector("#connection-warning").classList.toggle("hidden", conciergeReady);
  } catch {
    setConnectionStatus("Service unavailable", false);
  }
}

function setConnectionStatus(text, ready) {
  const status = document.querySelector("#connection-status");
  status.lastChild.textContent = ` ${text}`;
  status.classList.toggle("offline", !ready);
}

async function api(path, options = {}) {
  options.headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) options.headers["Content-Type"] = "application/json";
  if (token) options.headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, options);
  const body = await response.json().catch(() => ({}));
  if (response.status === 401 && token) {
    localStorage.removeItem("token");
    token = null;
    document.querySelector("#workspace").classList.add("hidden");
    document.querySelector("#logout-button").classList.add("hidden");
    document.querySelector("#auth").classList.remove("hidden");
    const error = document.querySelector("#auth-error");
    error.textContent = "Your session expired. Please log in again.";
    error.classList.remove("hidden");
  }
  if (!response.ok) throw new Error(body.detail || "Request failed");
  return body;
}

async function authenticate(action) {
  const error = document.querySelector("#auth-error");
  error.classList.add("hidden");
  try {
    const body = await api(`/auth/${action}`, {
      method: "POST",
      body: JSON.stringify({ email: email.value, password: password.value }),
    });
    token = body.access_token;
    localStorage.setItem("token", token);
    showWorkspace();
  } catch (reason) {
    error.textContent = reason.message;
    error.classList.remove("hidden");
  }
}

function showWorkspace() {
  document.querySelector("#auth").classList.add("hidden");
  document.querySelector("#workspace").classList.remove("hidden");
  document.querySelector("#logout-button").classList.remove("hidden");
  document.querySelector("#prompt").focus();
}

function logout() {
  localStorage.removeItem("token");
  location.reload();
}

function hideIntro() {
  document.querySelector("#intro").classList.add("compact-intro");
}

function createMessage(role, text, pending = false) {
  hideIntro();
  const row = document.createElement("article");
  row.className = `message ${role}${pending ? " pending" : ""}`;
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = role === "user" ? "You" : "S";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  const content = document.createElement("p");
  content.textContent = text;
  bubble.append(content);
  row.append(avatar, bubble);
  messages.append(row);
  row.scrollIntoView({ behavior: "smooth", block: "end" });
  return row;
}

function createPending() {
  const row = createMessage("assistant", "Connecting your request with the concierge", true);
  const dots = document.createElement("div");
  dots.className = "thinking";
  dots.append(document.createElement("i"), document.createElement("i"), document.createElement("i"));
  row.querySelector(".bubble").append(dots);
  return row;
}

function selectFile(event) {
  const file = event.target.files[0];
  if (file) setAttachment(file);
}

function setAttachment(file) {
  if (file.size > maxUploadBytes) {
    createMessage("assistant", `That file is ${formatBytes(file.size)}. The current demo limit is ${formatBytes(maxUploadBytes)}.`);
    clearAttachment();
    return;
  }
  selectedAttachment = file;
  const preview = document.querySelector("#attachment-preview");
  preview.replaceChildren();
  const detail = document.createElement("div");
  detail.innerHTML = `<strong></strong><span></span>`;
  detail.querySelector("strong").textContent = file.name;
  detail.querySelector("span").textContent = `${file.type || "file"} · ${formatBytes(file.size)}`;
  const remove = document.createElement("button");
  remove.type = "button";
  remove.textContent = "Remove";
  remove.onclick = clearAttachment;
  preview.append(detail, remove);
  preview.classList.remove("hidden");
}

function clearAttachment() {
  selectedAttachment = null;
  document.querySelector("#file-input").value = "";
  document.querySelector("#attachment-preview").classList.add("hidden");
}

async function toggleRecording() {
  const button = document.querySelector("#mic-button");
  if (recorder?.state === "recording") {
    recorder.stop();
    button.classList.remove("recording");
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordingChunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = event => recordingChunks.push(event.data);
    recorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop());
      const blob = new Blob(recordingChunks, { type: recorder.mimeType || "audio/webm" });
      setAttachment(new File([blob], `snapkey-voice-${Date.now()}.webm`, { type: blob.type }));
    };
    recorder.start();
    button.classList.add("recording");
  } catch {
    createMessage("assistant", "Microphone access was not available. You can attach an audio file instead.");
  }
}

async function sendPrompt(event) {
  event.preventDefault();
  const textarea = document.querySelector("#prompt");
  const text = textarea.value.trim();
  if (!text && !selectedAttachment) return;
  const attachment = selectedAttachment;
  createMessage("user", text || `Shared ${attachment.name}`);
  if (attachment) addLocalAttachment(messages.lastElementChild.querySelector(".bubble"), attachment);
  textarea.value = "";
  resizeComposer();
  clearAttachment();
  const pending = createPending();
  if (attachment) pending.querySelector("p").textContent = `Uploading ${attachment.name} securely`;
  const form = new FormData();
  form.append("prompt", text);
  if (attachment) form.append("attachment", attachment);
  try {
    const task = await api("/chat", { method: "POST", body: form });
    pollTask(task.id, pending, 0);
  } catch (reason) {
    pending.remove();
    createMessage("assistant", reason.message);
  }
}

async function pollTask(id, pending, attempts) {
  try {
    const task = await api(`/chat/tasks/${id}`);
    if (task.status === "succeeded") {
      pending.remove();
      const row = createMessage("assistant", task.result.message);
      for (const attachment of task.result.attachments || []) {
        await addRemoteAttachment(row.querySelector(".bubble"), attachment);
      }
    } else if (task.status === "failed") {
      pending.remove();
      createMessage("assistant", task.error);
    } else {
      if (attempts === 20) pending.querySelector("p").textContent = "Your concierge has the request and is preparing a response";
      if (attempts === 60) pending.querySelector("p").textContent = "Still working on it. You can keep this page open";
      setTimeout(() => pollTask(id, pending, attempts + 1), 1000);
    }
  } catch (reason) {
    pending.remove();
    createMessage("assistant", reason.message);
  }
}

function addLocalAttachment(container, file) {
  const url = URL.createObjectURL(file);
  renderAttachment(container, file.name, file.type, url);
}

async function addRemoteAttachment(container, attachment) {
  const response = await fetch(attachment.url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) return;
  const url = URL.createObjectURL(await response.blob());
  renderAttachment(container, attachment.name, attachment.content_type, url);
}

function renderAttachment(container, name, type, url) {
  if (type.startsWith("image/")) {
    const image = document.createElement("img");
    image.className = "message-image";
    image.src = url;
    image.alt = name;
    container.append(image);
  } else if (type.startsWith("audio/")) {
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = url;
    container.append(audio);
  } else {
    const link = document.createElement("a");
    link.className = "file-card";
    link.href = url;
    link.download = name;
    link.textContent = name;
    container.append(link);
  }
}

function handleComposerKey(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    document.querySelector("#composer").requestSubmit();
  }
}

function resizeComposer() {
  const textarea = document.querySelector("#prompt");
  textarea.style.height = "auto";
  textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}
