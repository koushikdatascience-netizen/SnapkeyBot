import { Conversation } from "@elevenlabs/client";

let conversation = null;
let muted = false;
let integrationToken = "";

function setState(state, title, caption) {
  const presence = document.querySelector("#live-agent-presence");
  presence.dataset.state = state;
  document.querySelector("#live-agent-title").textContent = title;
  if (caption) document.querySelector("#live-caption").textContent = caption;
  document.querySelector("#live-session-status").textContent = {
    idle: "Ready to connect",
    connecting: "Connecting securely",
    listening: "Listening",
    speaking: "Snapkey is speaking",
    thinking: "Thinking",
    error: "Connection issue",
  }[state] || state;
}

function setConnected(connected) {
  document.querySelector("#live-start").classList.toggle("hidden", connected);
  document.querySelector("#live-mute").classList.toggle("hidden", !connected);
  document.querySelector("#live-end").classList.toggle("hidden", !connected);
}

function showWorkspace(parameters = {}) {
  const type = parameters.type || "brief";
  renderLiveWorkspace({ type, ...parameters });
  return `${type} workspace displayed`;
}

const clientTools = {
  show_workspace: parameters => showWorkspace(parameters),
  request_confirmation: parameters => requestConfirmation(parameters),
  run_integration: parameters => runIntegration(parameters),
  start_browser: parameters => startBrowser(parameters),
  control_browser: parameters => controlBrowser(parameters),
  show_email_workspace: parameters => showWorkspace({ type: "email", ...parameters }),
  show_product_workspace: parameters => showWorkspace({ type: "products", ...parameters }),
  show_video_workspace: parameters => showWorkspace({ type: "video", ...parameters }),
  show_progress_workspace: parameters => showWorkspace({ type: "progress", ...parameters }),
  show_brief_workspace: parameters => showWorkspace({ type: "brief", ...parameters }),
  request_human_operator: parameters => {
    window.SnapkeyUI.prefillPrompt(parameters.request || "Please connect me with a human operator.");
    return "The request is prepared in the text workspace for the user to send.";
  },
};

function parsedArguments(value) {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    return JSON.parse(value);
  } catch {
    return {};
  }
}

async function integrationRequest(path, body) {
  const response = await fetch(`/api/integrations${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${integrationToken}`,
    },
    body: JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.detail || "Integration request failed");
  return result;
}

async function runIntegration(parameters = {}) {
  const tool = parameters.tool_name;
  const result = await integrationRequest(`/execute/${tool}`, {
    arguments: parsedArguments(parameters.arguments),
    confirmed: Boolean(parameters.confirmed),
  });
  if (tool === "youtube_search" && result.videos?.length) {
    renderLiveWorkspace({
      type: "youtube",
      title: result.videos[0].title,
      summary: `Playing from ${result.videos[0].channel}`,
      embed_url: result.videos[0].embed_url,
    });
  } else if (tool === "calendar_events") {
    renderLiveWorkspace({
      type: "calendar",
      title: "Your Google Calendar",
      summary: "Live events from your connected calendar.",
      events: (result.items || []).map(event => `${event.summary || "Untitled"} - ${event.start?.dateTime || event.start?.date || ""}`),
    });
  } else if (tool.startsWith("gmail_")) {
    renderLiveWorkspace({
      type: "gmail",
      title: tool === "gmail_send" ? "Email sent" : tool === "gmail_draft" ? "Draft saved" : "Gmail result",
      summary: tool === "gmail_send" ? "Google confirmed the message was sent." : "Live Gmail data is ready.",
      details: JSON.stringify(result),
    });
  } else {
    renderLiveWorkspace({ type: "brief", title: "Action complete", details: JSON.stringify(result) });
  }
  return JSON.stringify(result);
}

async function startBrowser(parameters = {}) {
  const result = await integrationRequest("/browser/session", {});
  renderLiveWorkspace({
    type: "browser",
    title: parameters.title || "Live browser",
    summary: "You can take manual control for logins, OTPs, and CAPTCHAs.",
    live_view_url: result.live_view_url,
  });
  return JSON.stringify(result);
}

async function controlBrowser(parameters = {}) {
  const sessionId = parameters.session_id;
  const confirmed = Boolean(parameters.confirmed);
  const result = await integrationRequest(`/browser/${sessionId}/action?confirmed=${confirmed}`, {
    action: parameters.action,
    url: parameters.url || null,
    selector: parameters.selector || null,
    text: parameters.text || null,
  });
  return JSON.stringify(result);
}

function parseDetails(value) {
  if (Array.isArray(value)) return value.map(String);
  if (!value) return [];
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      if (Array.isArray(parsed)) {
        return parsed.map(item => typeof item === "string" ? item : JSON.stringify(item));
      }
      if (parsed && typeof parsed === "object") {
        return Object.entries(parsed).map(([key, item]) => `${key}: ${item}`);
      }
    } catch {
      return value.split(/\n|;/).map(item => item.trim()).filter(Boolean);
    }
  }
  return [];
}

function renderLiveWorkspace(data) {
  const workspace = document.querySelector("#live-workspace");
  workspace.className = `live-workspace ${data.type || "brief"}`;
  workspace.replaceChildren();

  const header = document.createElement("div");
  header.className = "live-workspace-header";
  const label = document.createElement("small");
  label.textContent = `${(data.type || "brief").toUpperCase()} WORKSPACE`;
  const title = document.createElement("h3");
  title.textContent = data.title || liveWorkspaceTitle(data.type);
  const summary = document.createElement("p");
  summary.textContent = data.summary || data.body || "Ready while we continue talking.";
  header.append(label, title, summary);
  workspace.append(header);

  if (data.type === "calendar") renderCalendar(workspace, data);
  else if (data.type === "email" || data.type === "gmail") renderLiveEmail(workspace, data);
  else if (data.type === "youtube") renderYouTube(workspace, data);
  else if (data.type === "browser") renderBrowser(workspace, data);
  else if (["retail", "bar", "inventory"].includes(data.type)) renderRetail(workspace, data);
  else renderDetailList(workspace, parseDetails(data.details || data.items || data.steps));
}

function renderYouTube(workspace, data) {
  const url = data.embed_url || data.url;
  if (!url) return renderDetailList(workspace, parseDetails(data.details));
  const frame = document.createElement("iframe");
  frame.className = "live-embed";
  frame.src = url;
  frame.allow = "autoplay; encrypted-media; picture-in-picture";
  frame.allowFullscreen = true;
  workspace.append(frame);
}

function renderBrowser(workspace, data) {
  const url = data.live_view_url || data.url;
  if (!url) return renderDetailList(workspace, parseDetails(data.details));
  const frame = document.createElement("iframe");
  frame.className = "live-embed browser-live-view";
  frame.src = url;
  frame.allow = "clipboard-read; clipboard-write";
  workspace.append(frame);
}

function liveWorkspaceTitle(type) {
  return {
    calendar: "Calendar and meetings",
    email: "Gmail workspace",
    gmail: "Gmail workspace",
    retail: "Madhushala operations",
    bar: "Madhushala operations",
    inventory: "Inventory overview",
  }[type] || "Live workspace";
}

function renderCalendar(workspace, data) {
  const panel = document.createElement("div");
  panel.className = "live-calendar";
  const events = parseDetails(data.events || data.details);
  ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach((day, index) => {
    const card = document.createElement("article");
    card.innerHTML = `<small>${day}</small><strong>${index + 12}</strong><span></span>`;
    card.querySelector("span").textContent = events[index] || (index === 2 ? "Available" : "No events");
    panel.append(card);
  });
  workspace.append(panel);
}

function renderLiveEmail(workspace, data) {
  const panel = document.createElement("div");
  panel.className = "live-email";
  panel.innerHTML = "<span></span><h4></h4><p></p><small></small>";
  panel.querySelector("span").textContent = data.from || "Gmail";
  panel.querySelector("h4").textContent = data.subject || data.title || "Email workspace";
  panel.querySelector("p").textContent = data.body || data.summary || "Ready to search, summarize, or prepare a draft.";
  panel.querySelector("small").textContent = data.status || "External actions require confirmation";
  workspace.append(panel);
}

function renderRetail(workspace, data) {
  const metrics = parseDetails(data.metrics || data.details);
  const panel = document.createElement("div");
  panel.className = "live-retail";
  const defaults = ["Today's sales: Ready", "Low stock: Review", "Open orders: Ready", "Supplier tasks: Ready"];
  (metrics.length ? metrics : defaults).slice(0, 6).forEach((metric, index) => {
    const card = document.createElement("article");
    const [name, value = "Ready"] = metric.split(":");
    card.innerHTML = "<small></small><strong></strong><i></i>";
    card.querySelector("small").textContent = name;
    card.querySelector("strong").textContent = value.trim();
    card.querySelector("i").style.setProperty("--bar", `${55 + (index % 4) * 12}%`);
    panel.append(card);
  });
  workspace.append(panel);
}

function renderDetailList(workspace, details) {
  const panel = document.createElement("div");
  panel.className = "live-detail-list";
  (details.length ? details : ["Workspace ready"]).slice(0, 8).forEach(detail => {
    const item = document.createElement("span");
    item.textContent = detail;
    panel.append(item);
  });
  workspace.append(panel);
}

function requestConfirmation(parameters = {}) {
  return new Promise(resolve => {
    const workspace = document.querySelector("#live-workspace");
    workspace.className = "live-workspace confirmation";
    workspace.replaceChildren();
    const panel = document.createElement("div");
    panel.className = "live-confirmation";
    panel.innerHTML = "<small>CONFIRM BEFORE ACTION</small><h3></h3><p></p><div><button class='approve'>Confirm</button><button>Cancel</button></div>";
    panel.querySelector("h3").textContent = parameters.title || parameters.action || "Approve this action?";
    panel.querySelector("p").textContent = parameters.summary || "Snapkey will continue only after your approval.";
    const buttons = panel.querySelectorAll("button");
    buttons[0].onclick = () => {
      buttons.forEach(button => button.disabled = true);
      buttons[0].textContent = "Confirmed";
      resolve("The user confirmed the action.");
    };
    buttons[1].onclick = () => {
      buttons.forEach(button => button.disabled = true);
      buttons[1].textContent = "Cancelled";
      resolve("The user cancelled the action.");
    };
    workspace.append(panel);
  });
}

window.startLiveConversation = async function startLiveConversation() {
  if (conversation) return;
  setState("connecting", "Joining the conversation…", "Please allow microphone access when your browser asks.");
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
    const response = await window.SnapkeyUI.api("/voice/conversation-token", { method: "POST" });
    integrationToken = response.tool_token;
    conversation = await Conversation.startSession({
      conversationToken: response.token,
      connectionType: "webrtc",
      dynamicVariables: { snapkey_tool_token: response.tool_token },
      clientTools,
      onConnect: () => {
        setConnected(true);
        setState("listening", "I’m listening.", "Speak naturally. You can interrupt me at any time.");
      },
      onDisconnect: () => {
        conversation = null;
        setConnected(false);
        setState("idle", "Conversation ended.", "Start again whenever you’re ready.");
      },
      onMessage: message => {
        const text = message.message || message.text;
        if (text) document.querySelector("#live-caption").textContent = text;
      },
      onModeChange: mode => {
        const value = typeof mode === "string" ? mode : mode.mode;
        if (value === "speaking") setState("speaking", "Here’s what I found.");
        else setState("listening", "I’m listening.");
      },
      onStatusChange: status => {
        const value = typeof status === "string" ? status : status.status;
        if (value === "connecting") setState("connecting", "Joining the conversation…");
      },
      onError: error => {
        setState("error", "Let’s reconnect.", typeof error === "string" ? error : "The live session was interrupted.");
      },
    });
  } catch (error) {
    conversation = null;
    setConnected(false);
    setState("error", "Microphone connection failed.", error?.message || "Check browser microphone permission and try again.");
  }
};

window.endLiveConversation = async function endLiveConversation() {
  if (conversation) await conversation.endSession();
  conversation = null;
  setConnected(false);
  setState("idle", "Conversation ended.", "Start again whenever you’re ready.");
};

window.toggleLiveMute = async function toggleLiveMute() {
  if (!conversation) return;
  muted = !muted;
  await conversation.setMicMuted(muted);
  document.querySelector("#live-mute").textContent = muted ? "Unmute" : "Mute";
  setState(muted ? "thinking" : "listening", muted ? "Microphone muted." : "I’m listening.");
};

window.addEventListener("beforeunload", () => conversation?.endSession());
document.documentElement.dataset.liveAgentModule = "ready";
