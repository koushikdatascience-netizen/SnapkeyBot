let token = localStorage.getItem("token");
let conciergeMode = false;
let conciergeReady = false;
let selectedAttachment = null;
let recorder = null;
let recordingChunks = [];
let maxUploadBytes = 15000000;
let voiceReady = false;
let liveAgentReady = false;
let responseMode = localStorage.getItem("responseMode") || "text";
let currentAudio = null;
let activityTimer = null;
let activeTaskPrompt = "";

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
    voiceReady = config.voice_ready;
    liveAgentReady = config.live_agent_ready;
    setConnectionStatus(conciergeReady ? "Concierge online" : "Setup required", conciergeReady);
    document.querySelector("#connection-warning").classList.toggle("hidden", conciergeReady);
    updateModeControls();
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
  document.querySelector("#google-connect").classList.remove("hidden");
  document.querySelector("#mode-switch").classList.remove("hidden");
  document.querySelector("#prompt").focus();
}

async function connectGoogle() {
  const button = document.querySelector("#google-connect");
  try {
    const status = await api("/integrations/google/status");
    if (status.connected) {
      button.textContent = "Google connected";
      return;
    }
    const result = await api("/integrations/google/connect");
    location.href = result.authorization_url;
  } catch (reason) {
    createMessage("assistant", reason.message);
  }
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
  if (role === "assistant" && !pending && text) {
    const actions = document.createElement("div");
    actions.className = "message-actions";
    const speak = document.createElement("button");
    speak.type = "button";
    speak.textContent = "Replay voice";
    speak.onclick = () => speakText(text, speak);
    speak.disabled = !voiceReady;
    actions.append(speak);
    bubble.append(actions);
  }
  row.append(avatar, bubble);
  messages.append(row);
  row.scrollIntoView({ behavior: "smooth", block: "end" });
  return row;
}

function createPending() {
  const row = createMessage("assistant", "Working on your request", true);
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
  activeTaskPrompt = text || attachment?.name || "your request";
  createMessage("user", text || `Shared ${attachment.name}`);
  if (attachment) addLocalAttachment(messages.lastElementChild.querySelector(".bubble"), attachment);
  textarea.value = "";
  resizeComposer();
  clearAttachment();
  const pending = createPending();
  showActivityStage(activeTaskPrompt);
  if (attachment) pending.querySelector("p").textContent = `Uploading ${attachment.name} securely`;
  const form = new FormData();
  form.append("prompt", text);
  if (attachment) form.append("attachment", attachment);
  try {
    const task = await api("/chat", { method: "POST", body: form });
    pollTask(task.id, pending, 0);
  } catch (reason) {
    clearActivityStage();
    pending.remove();
    createMessage("assistant", reason.message);
  }
}

async function pollTask(id, pending, attempts) {
  try {
    const task = await api(`/chat/tasks/${id}`);
    if (task.status === "succeeded") {
      pending.remove();
      clearActivityStage();
      const row = createMessage("assistant", task.result.message);
      for (const attachment of task.result.attachments || []) {
        await addRemoteAttachment(row.querySelector(".bubble"), attachment);
      }
      renderPresentation(task.result.presentation, task.result.attachments || []);
      if (responseMode === "voice" && voiceReady && task.result.message) {
        speakText(task.result.message, row.querySelector(".message-actions button"));
      }
    } else if (task.status === "failed") {
      pending.remove();
      clearActivityStage();
      createMessage("assistant", task.error);
    } else {
      if (attempts === 20) pending.querySelector("p").textContent = "Your concierge has the request and is preparing a response";
      if (attempts === 60) pending.querySelector("p").textContent = "Still working on it. You can keep this page open";
      setTimeout(() => pollTask(id, pending, attempts + 1), 1000);
    }
  } catch (reason) {
    if (attempts < 300) {
      pending.querySelector("p").textContent = "Reconnecting to the live workspace";
      setTimeout(() => pollTask(id, pending, attempts + 1), Math.min(1000 + attempts * 500, 4000));
      return;
    }
    pending.remove();
    clearActivityStage();
    createMessage("assistant", `${reason.message}. Please use retry or send the request again.`);
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
  } else if (type.startsWith("video/")) {
    const video = document.createElement("video");
    video.controls = true;
    video.playsInline = true;
    video.src = url;
    video.className = "message-video";
    container.append(video);
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

function updateModeControls() {
  document.querySelector("#text-mode").classList.toggle("active", responseMode === "text");
  const voiceButton = document.querySelector("#voice-mode");
  voiceButton.classList.remove("active");
  voiceButton.disabled = !liveAgentReady;
  voiceButton.title = liveAgentReady ? "Start a realtime voice conversation" : "Add ELEVENLABS_AGENT_ID to enable live conversation";
}

function openLiveAgent() {
  if (!liveAgentReady) {
    createMessage("assistant", "Live conversation is not configured yet. Add your ElevenLabs Agent ID.");
    return;
  }
  document.querySelector("#live-agent").classList.remove("hidden");
}

async function closeLiveAgent() {
  await window.endLiveConversation?.();
  document.querySelector("#live-agent").classList.add("hidden");
}

function setResponseMode(mode) {
  if (mode === "voice" && !voiceReady) {
    createMessage("assistant", "Voice mode is not configured yet.");
    return;
  }
  responseMode = mode;
  localStorage.setItem("responseMode", mode);
  updateModeControls();
  if (mode === "text" && currentAudio) {
    stopVoice();
  } else if (mode === "voice") {
    createMessage("assistant", "Live voice is on. New replies will speak automatically.");
  }
}

function setSpeaking(speaking) {
  document.querySelector("#assistant-aura")?.classList.toggle("speaking", speaking);
  document.querySelector("#stop-voice")?.classList.toggle("hidden", !speaking);
}

async function speakText(text, button) {
  if (!voiceReady || !text) return;
  stopVoice();
  button.disabled = true;
  button.textContent = "Loading voice...";
  setSpeaking(true);
  try {
    const response = await fetch("/api/voice/speech", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || "Voice is temporarily unavailable");
    }
    currentAudio = await streamAudioResponse(response);
    currentAudio.onended = () => {
      button.textContent = "Replay voice";
      button.disabled = false;
      setSpeaking(false);
    };
    currentAudio.onerror = currentAudio.onended;
  } catch (reason) {
    button.textContent = "Replay voice";
    button.disabled = false;
    setSpeaking(false);
    createMessage("assistant", `${reason.message}. The text reply is still available.`);
  }
}

function stopVoice() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  document.querySelector("#stop-voice").classList.add("hidden");
  setSpeaking(false);
}

function showActivityStage(prompt) {
  clearInterval(activityTimer);
  const stage = document.querySelector("#agent-stage");
  const kind = inferPresentationType(prompt);
  const labels = activityLabels(kind);
  stage.className = `agent-stage activity-stage ${kind}`;
  stage.innerHTML = `
    <div class="stage-heading"><span class="stage-orb"></span><div><small>SNAPKEY LIVE ACTIVITY</small><h3>${escapeHtml(stageTitle(kind))}</h3></div><strong>In progress</strong></div>
    <div class="activity-track">${labels.map((label, index) => `<div class="activity-step ${index === 0 ? "active" : ""}"><i></i><span>${escapeHtml(label)}</span></div>`).join("")}</div>
  `;
  let active = 0;
  activityTimer = setInterval(() => {
    const steps = stage.querySelectorAll(".activity-step");
    if (!steps.length) return;
    steps[active].classList.add("done");
    steps[active].classList.remove("active");
    active = Math.min(active + 1, steps.length - 1);
    steps[active].classList.add("active");
  }, 2600);
}

function clearActivityStage() {
  clearInterval(activityTimer);
  activityTimer = null;
  document.querySelector("#agent-stage").classList.add("hidden");
}

function inferPresentationType(prompt) {
  const value = prompt.toLowerCase();
  if (/(email|mail|inbox)/.test(value)) return "email";
  if (/(amazon|meesho|product|compare|price|shop)/.test(value)) return "products";
  if (/(video|footage|camera|office|cctv)/.test(value)) return "video";
  return "progress";
}

function stageTitle(kind) {
  return { email: "Reviewing communications", products: "Researching the market", video: "Connecting visual sources", progress: "Coordinating your request" }[kind];
}

function activityLabels(kind) {
  const common = {
    email: ["Understanding the email request", "Reviewing available messages", "Preparing a clear response", "Finalizing for your review"],
    products: ["Defining comparison criteria", "Reviewing product options", "Ranking useful results", "Preparing recommendations"],
    video: ["Understanding the visual request", "Preparing the secure viewer", "Checking media availability", "Opening the result"],
    progress: ["Understanding your request", "Selecting the right workspace", "Preparing the result", "Final review"],
  };
  return common[kind];
}

function renderPresentation(presentation, attachments) {
  if (!presentation) return;
  const stage = document.querySelector("#agent-stage");
  stage.className = `agent-stage result-stage ${presentation.type || "brief"}`;
  stage.replaceChildren();
  const heading = document.createElement("div");
  heading.className = "stage-heading";
  heading.innerHTML = `<span class="stage-orb"></span><div><small>SNAPKEY WORKSPACE</small><h3></h3></div><strong>Ready</strong>`;
  heading.querySelector("h3").textContent = presentation.title || presentation.subject || "Your result";
  stage.append(heading);
  if (presentation.type === "email") renderEmailStage(stage, presentation);
  else if (presentation.type === "products") renderProductsStage(stage, presentation);
  else if (presentation.type === "video") renderVideoStage(stage, presentation, attachments);
  else renderBriefStage(stage, presentation);
}

function renderEmailStage(stage, data) {
  const card = document.createElement("div");
  card.className = "email-panel";
  card.innerHTML = `<div class="email-meta"><span>From <b></b></span><span>To <b></b></span></div><h4></h4><p></p><div class="stage-actions"><span>Summary ready</span><span>Available for review</span></div>`;
  card.querySelector(".email-meta span:first-child b").textContent = data.from || "Your inbox";
  card.querySelector(".email-meta span:last-child b").textContent = data.to || "You";
  card.querySelector("h4").textContent = data.subject || data.title || "Email summary";
  card.querySelector("p").textContent = data.body || data.summary || "The requested email information is ready.";
  stage.append(card);
}

function renderProductsStage(stage, data) {
  const grid = document.createElement("div");
  grid.className = "product-grid";
  const items = data.items?.length ? data.items : [{ name: data.title || "Research result", note: data.body || data.summary || "Ready for review" }];
  items.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "product-card";
    card.innerHTML = `<span class="rank"></span><div class="product-visual"></div><h4></h4><p></p><div><b></b><small></small></div>`;
    card.querySelector(".rank").textContent = `#${index + 1}`;
    card.querySelector("h4").textContent = item.name;
    card.querySelector("p").textContent = item.note || "Compared for relevance and value";
    card.querySelector("b").textContent = item.price || "Recommended";
    card.querySelector("small").textContent = item.rating || "";
    grid.append(card);
  });
  stage.append(grid);
}

function renderVideoStage(stage, data, attachments) {
  const panel = document.createElement("div");
  panel.className = "video-panel";
  const videoAttachment = attachments.find(item => item.content_type?.startsWith("video/"));
  panel.innerHTML = `<div class="video-placeholder"><span class="live-dot"></span><strong></strong><p></p></div>`;
  panel.querySelector("strong").textContent = data.status || "Visual source ready";
  panel.querySelector("p").textContent = data.body || data.summary || "The requested media is available in the response below.";
  if (videoAttachment) panel.querySelector("p").textContent = "Secure video delivered. Use the player in the response below.";
  stage.append(panel);
}

function renderBriefStage(stage, data) {
  const panel = document.createElement("div");
  panel.className = "brief-panel";
  const steps = data.steps?.length ? data.steps : ["Request understood", "Result prepared", "Ready to review"];
  panel.innerHTML = `<p></p><div class="metric-row">${steps.map(step => `<span>${escapeHtml(step)}</span>`).join("")}</div>`;
  panel.querySelector("p").textContent = data.body || data.summary || data.subtitle || "Your requested result is ready.";
  stage.append(panel);
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

function prefillPrompt(value) {
  closeLiveAgent();
  const prompt = document.querySelector("#prompt");
  prompt.value = value;
  resizeComposer();
  prompt.focus();
}

window.SnapkeyUI = { api, renderPresentation, prefillPrompt };

async function streamAudioResponse(response) {
  if (!window.MediaSource || !MediaSource.isTypeSupported("audio/mpeg")) {
    const audio = new Audio(URL.createObjectURL(await response.blob()));
    await audio.play();
    return audio;
  }
  const mediaSource = new MediaSource();
  const audio = new Audio(URL.createObjectURL(mediaSource));
  const reader = response.body.getReader();
  mediaSource.addEventListener("sourceopen", async () => {
    const source = mediaSource.addSourceBuffer("audio/mpeg");
    const append = chunk => new Promise(resolve => {
      source.addEventListener("updateend", resolve, { once: true });
      source.appendBuffer(chunk);
    });
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      await append(value);
    }
    if (mediaSource.readyState === "open") mediaSource.endOfStream();
  }, { once: true });
  await audio.play();
  return audio;
}
