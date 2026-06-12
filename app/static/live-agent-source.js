import { Conversation } from "@elevenlabs/client";

let conversation = null;
let muted = false;
let integrationToken = "";
let activeBrowserSessionId = "";
let browserStarting = false;
let lastBrowserIntent = "";
let lastYouTubeIntent = "";
let lastReportIntent = "";
let lastMonitoringIntent = "";
let lastCalendarIntent = "";
let monitoringClock = null;
let demoSequenceTimer = null;
let remoteDirectorSocket = null;
let activeReport = null;
let activeYouTubeFrame = null;
let activeYouTubeVideos = [];
let activeYouTubeIndex = 0;

const demoScenes = {
  intro: { title: "Good evening, Mr. Biswajit.", caption: "I am Snapkey, your live business assistant. Tell me, how may I assist you?", agentPrompt: "Hindi mein warmly greet Mr. Biswajit, introduce yourself as Snapkey, and ask how you may assist him. Keep it under two sentences.", workspace: { type: "brief", title: "Snapkey is ready", summary: "Voice-first intelligence for your business.", details: ["Live business insights", "Calendar and operations", "Camera monitoring", "Always ready to assist"] } },
  sales: { title: "Yesterday's sales are ready.", caption: "Strong evening performance led overall revenue.", agentPrompt: "Hindi mein visible sales report explain karo. Total sales 1,84,620 rupees hain aur strongest period 6 se 9 PM tha. Concise raho.", workspace: { type: "report", title: "Yesterday's sales performance", summary: "M/S Mondal and Mondal FL ON Shop Off Counter", chart: "bar", total: 184620, rows: [{ label: "12 PM", value: 18400 }, { label: "2 PM", value: 22750 }, { label: "4 PM", value: 29120 }, { label: "6 PM", value: 38950 }, { label: "8 PM", value: 51700 }, { label: "10 PM", value: 23700 }] } },
  calendar: { title: "Today's calendar is open.", caption: "Your evening meeting at Prayag is highlighted.", agentPrompt: "Hindi mein today's visible calendar summarize karo. Important meeting Prayag mein 6:30 PM par hai. Concise raho.", workspace: { type: "calendar", title: "Today's calendar", summary: "Three scheduled items. Evening meeting highlighted.", today_events: ["9:30 AM · Operations review", "1:00 PM · Supplier follow-up", "6:30 PM · Meeting at Prayag"] } },
  camera1: { title: "Office camera one is live.", caption: "The retail floor is active and operating normally.", agentPrompt: "Hindi mein bolo ki office camera one open hai, retail floor active hai, customer service normal hai, aur koi attention item detect nahi hua.", workspace: { type: "monitoring", title: "Office camera 1 · Retail floor", summary: "Live operational view with activity detection.", selected_camera: 1, focus: "workers" } },
  camera2: { title: "Office camera two is live.", caption: "Stock verification is in progress.", agentPrompt: "Hindi mein bolo ki office camera two open hai, stock verification chal raha hai, assigned worker active hai, aur workspace normal hai.", workspace: { type: "monitoring", title: "Office camera 2 · Stock room", summary: "Live stock-room view with activity detection.", selected_camera: 2, focus: "workers" } },
  thankyou: { title: "Thank you, Mr. Biswajit.", caption: "Snapkey is ready whenever your business needs it.", agentPrompt: "Hindi mein Mr. Biswajit ko thank you bolo aur kaho ki Snapkey unke business ke liye hamesha ready hai. One sentence.", workspace: { type: "thankyou", title: "Built for the way you lead.", summary: "One conversation. Every business view. Ready when you are." } },
};

window.stopDemoNarration = function stopDemoNarration() {
  if (demoSequenceTimer) window.clearTimeout(demoSequenceTimer);
  demoSequenceTimer = null;
};
window.toggleDemoDirector = () => document.querySelector("#demo-director").classList.toggle("hidden");
window.runDemoScene = function runDemoScene(name) {
  const scene = demoScenes[name];
  if (!scene) return;
  setState("thinking", scene.title, scene.caption);
  renderLiveWorkspace(scene.workspace);
  if (conversation?.isOpen()) {
    conversation.sendUserMessage(scene.agentPrompt);
  }
};
window.runDemoSequence = function runDemoSequence() {
  window.stopDemoNarration();
  const sequence = ["intro", "sales", "calendar", "camera1", "camera2", "thankyou"];
  let index = 0;
  const advance = () => {
    window.runDemoScene(sequence[index++]);
    if (index < sequence.length) demoSequenceTimer = window.setTimeout(advance, 10000);
  };
  advance();
};
window.addEventListener("keydown", event => {
  if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() === "d") {
    event.preventDefault();
    window.toggleDemoDirector();
  }
  if (event.altKey && event.key.toLowerCase() === "l") {
    event.preventDefault();
    window.openLiveAgent?.();
  }
  if (event.ctrlKey && event.altKey && /^[1-6]$/.test(event.key)) {
    event.preventDefault();
    window.runDemoScene(["intro", "sales", "calendar", "camera1", "camera2", "thankyou"][Number(event.key) - 1]);
  }
});

function connectRemoteDirector() {
  const sessionId = new URLSearchParams(window.location.search).get("demo_session");
  if (!sessionId) return;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  remoteDirectorSocket = new WebSocket(`${protocol}//${window.location.host}/api/operator/demo/${encodeURIComponent(sessionId)}?role=presenter`);
  remoteDirectorSocket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.type === "scene") {
      document.querySelector("#live-agent").classList.remove("hidden");
      window.runDemoScene(message.scene);
    }
  };
  remoteDirectorSocket.onclose = () => window.setTimeout(connectRemoteDirector, 1500);
}

connectRemoteDirector();

function updateAgentContext(message) {
  if (conversation?.isOpen()) conversation.sendContextualUpdate(message);
}

window.askLiveAgent = function askLiveAgent(prompt) {
  if (conversation?.isOpen()) {
    conversation.sendUserMessage(prompt);
    setState("thinking", "Working on it.", prompt);
    return;
  }
  setState("idle", "Start the conversation first.", "Then ask by voice or use these quick actions.");
};

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

function setWorkspaceVisible(visible) {
  const body = document.querySelector(".live-agent-body");
  const workspace = document.querySelector("#live-workspace");
  const toggle = document.querySelector("#live-workspace-toggle");
  workspace.classList.toggle("hidden", !visible);
  toggle.classList.toggle("hidden", !visible);
  body.classList.toggle("has-workspace", visible);
  if (visible && window.matchMedia("(max-width: 620px)").matches) body.classList.add("mobile-workspace-open");
  if (!visible) body.classList.remove("mobile-workspace-open");
}

window.toggleLiveWorkspace = function toggleLiveWorkspace() {
  document.querySelector(".live-agent-body").classList.toggle("mobile-workspace-open");
};

window.closeLiveWorkspace = function closeLiveWorkspace() {
  stopMonitoringClock();
  setWorkspaceVisible(false);
};

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
  show_monitoring_workspace: parameters => showWorkspace({ type: "monitoring", ...parameters }),
  control_media: parameters => controlMedia(parameters),
  control_report: parameters => controlReport(parameters),
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
    activeYouTubeVideos = result.videos;
    activeYouTubeIndex = 0;
    const video = result.videos[0];
    renderLiveWorkspace({
      type: "youtube",
      title: video.title,
      summary: `Playing from ${video.channel}`,
      embed_url: video.embed_url,
      watch_url: `https://www.youtube.com/watch?v=${video.id}`,
      videos: result.videos,
    });
  } else if (tool === "retail_report") {
    renderLiveWorkspace({
      type: "report",
      title: result.title,
      summary: `${result.period.start} to ${result.period.end}. Limited to ${result.limits.points} chart points.`,
      chart: result.chart,
      rows: result.rows,
      total: result.total,
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
  if (activeBrowserSessionId) {
    if (parameters.url) {
      const navigation = await navigateActiveBrowser(parameters.url);
      updateAgentContext(
        `Snapkey's live browser navigated successfully to ${navigation.title || navigation.url}. ` +
        "A live interactive browser is visible beside you. Acknowledge this and continue helping the user."
      );
    } else {
      updateAgentContext(
        "Snapkey's live interactive browser is already open and visible beside you. " +
        "You can tell the user it is ready."
      );
    }
    return JSON.stringify({ session_id: activeBrowserSessionId, reused: true });
  }
  const result = await integrationRequest("/browser/session", {});
  activeBrowserSessionId = result.session_id;
  renderLiveWorkspace({
    type: "browser",
    title: parameters.title || "Live browser",
    summary: "You can take manual control for logins, OTPs, and CAPTCHAs.",
    live_view_url: result.live_view_url,
  });
  if (parameters.url) {
    const navigation = await navigateActiveBrowser(parameters.url);
    updateAgentContext(
      `Snapkey opened a live interactive browser and navigated successfully to ` +
      `${navigation.title || navigation.url}. The browser is visible beside you. ` +
      "Do not say browsing is unavailable; acknowledge the result and continue naturally."
    );
  } else {
    updateAgentContext(
      "Snapkey opened a live interactive browser successfully. It is visible beside you and ready for commands."
    );
  }
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
  updateAgentContext(
    `The live browser completed the ${parameters.action} action successfully. ` +
    `Current page: ${result.title || result.url || "browser ready"}.`
  );
  return JSON.stringify(result);
}

async function navigateActiveBrowser(url) {
  if (!activeBrowserSessionId) await startBrowser();
  return integrationRequest(`/browser/${activeBrowserSessionId}/action?confirmed=false`, {
    action: "navigate",
    url,
    selector: null,
    text: null,
  });
}

function retailReportIntent(text) {
  const value = text.toLowerCase();
  if (!/\b(report|sales|stock|products|category|categories|inventory|payment|cash|card|upi|hourly|rush|average bill|purchase|customer|visits)\b/.test(value)) return null;
  let reportName = "sales_summary";
  if (/\b(low stock|reorder|inventory)\b/.test(value)) reportName = "low_stock";
  else if (/\b(top|best|selling).*(product|item)|\bproduct.*(top|best|selling)\b/.test(value)) reportName = "top_products";
  else if (/\b(payment|cash|card|upi)\b/.test(value)) reportName = "payment_mix";
  else if (/\b(hourly|rush|busy hour|peak hour)\b/.test(value)) reportName = "hourly_sales";
  else if (/\baverage bill|avg bill|bill value\b/.test(value)) reportName = "average_bill";
  else if (/\bpurchase/.test(value)) reportName = "purchase_trend";
  else if (/\b(customer|visits)\b/.test(value)) reportName = "customer_visits";
  else if (/\bstock.*categor|categor.*stock\b/.test(value)) reportName = "stock_by_category";
  else if (/\bcategor/.test(value)) reportName = "category_sales";
  const explicitDays = value.match(/\b(?:last|past|previous)\s+(\d{1,3})\s+days?\b/);
  const days = explicitDays ? Number(explicitDays[1])
    : /\btoday\b/.test(value) ? 1
    : /\byesterday\b/.test(value) ? 2
    : /\bweek\b/.test(value) ? 7
    : /\bmonth\b/.test(value) ? 30
    : /\bquarter\b/.test(value) ? 90
    : 7;
  const limitMatch = value.match(/\b(?:top|show|first)\s+(\d{1,2})\b/);
  const chart = /\b(donut|pie)\b/.test(value) ? "donut"
    : /\b(line|trend)\b/.test(value) ? "line"
    : /\b(table|list)\b/.test(value) ? "table"
    : /\b(bar|chart|graph)\b/.test(value) ? "bar"
    : "";
  return {
    report_name: reportName,
    days,
    limit: limitMatch ? Number(limitMatch[1]) : 20,
    chart,
  };
}

async function handleAutomaticRetailReport(text) {
  const intent = retailReportIntent(text);
  if (!intent) return false;
  const intentKey = JSON.stringify(intent);
  if (intentKey === lastReportIntent) return false;
  lastReportIntent = intentKey;
  renderLiveWorkspace({
    type: "progress",
    title: "Preparing live report",
    summary: "Querying a short, aggregated dataset so the result stays fast.",
    steps: ["Applying date limits", "Aggregating approved report data", "Rendering the chart"],
  });
  try {
    const result = await runIntegration({ tool_name: "retail_report", arguments: intent });
    updateAgentContext(
      `Snapkey displayed the ${intent.report_name} report successfully using a bounded ${intent.days}-day query. ` +
      "Summarize the visible report briefly."
    );
    return result;
  } catch (error) {
    renderLiveWorkspace({
      type: "brief",
      title: "Report connection issue",
      summary: error?.message || "The report could not be loaded.",
      details: "Check REPORT_DATABASE_URL and the read-only Snapkey reporting views.",
    });
    updateAgentContext(`The retail report failed because: ${error?.message || "report connection failed"}.`);
    return false;
  }
}

function reportChartIntent(text) {
  const value = text.toLowerCase();
  if (/\b(donut|pie)\b/.test(value)) return "donut";
  if (/\b(line|trend)\b/.test(value)) return "line";
  if (/\b(table|list)\b/.test(value)) return "table";
  if (/\b(bar|graph)\b/.test(value)) return "bar";
  return "";
}

function controlReport(parameters = {}) {
  const chart = parameters.chart || "";
  if (!activeReport || !["bar", "line", "donut", "table"].includes(chart)) {
    return "No active report or unsupported chart type";
  }
  renderLiveWorkspace({ ...activeReport, chart });
  return `Active report changed to ${chart}`;
}

function handleAutomaticReportDisplay(text) {
  if (!activeReport) return false;
  const chart = reportChartIntent(text);
  if (!chart || !/\b(change|switch|show|make|convert|view|chart|graph|table|list|donut|pie|line|bar)\b/i.test(text)) return false;
  controlReport({ chart });
  updateAgentContext(`The visible report was changed to a ${chart} view.`);
  return true;
}

function monitoringIntent(text) {
  const value = text.toLowerCase();
  if (!/\b(cam|camera|cctv|worker|staff|employee|screen share|monitor|monitoring|sleeping|idle)\b/.test(value)) {
    return null;
  }
  const cameraMatch = value.match(/\b(?:cam|camera)\s*(?:number\s*)?([123])\b/);
  return {
    camera: cameraMatch ? Number(cameraMatch[1]) : 0,
    focus: /\b(worker|staff|employee|sleeping|idle)\b/.test(value) ? "workers" : "cameras",
  };
}

function handleAutomaticMonitoringIntent(text) {
  const intent = monitoringIntent(text);
  if (!intent) return false;
  const intentKey = JSON.stringify(intent);
  if (intentKey === lastMonitoringIntent) return false;
  lastMonitoringIntent = intentKey;
  renderLiveWorkspace({
    type: "monitoring",
    title: intent.camera ? `Camera ${intent.camera} live view` : "Operations monitoring",
    summary: "Simulated camera analytics and worker activity for demonstration only.",
    selected_camera: intent.camera,
    focus: intent.focus,
  });
  updateAgentContext(
    `Snapkey opened the simulated monitoring demo${intent.camera ? ` on camera ${intent.camera}` : ""}. ` +
    "Clearly describe it as simulated demo data, then summarize the visible worker statuses."
  );
  return true;
}

function browserIntentUrl(text) {
  const value = text.toLowerCase().trim();
  if (!/(open|browse|visit|search|google|youtube|website|web)/.test(value)) return "";
  if (/\b(youtube|play)\b/.test(value)) return "";
  const explicitUrl = text.match(/https?:\/\/\S+/i)?.[0];
  if (explicitUrl) return explicitUrl;
  const domain = text.match(/\b(?:www\.)?[a-z0-9-]+\.(?:com|in|org|net|io|ai)\b/i)?.[0];
  if (domain) return `https://${domain}`;
  const searchQuery = text
    .replace(/^(please\s+)?(open|browse|visit|go to|google|search(?: for)?|look up)\s+/i, "")
    .trim();
  if (searchQuery && !/^google$/i.test(searchQuery)) {
    return `https://www.google.com/search?q=${encodeURIComponent(searchQuery)}`;
  }
  return "https://www.google.com";
}

function youtubeIntentQuery(text) {
  if (!/\b(youtube|play|video)\b/i.test(text)) return "";
  if (mediaControlIntent(text)) return "";
  return text
    .replace(/^(please\s+)?(open|search|find|show|play|watch)\s+/i, "")
    .replace(/\s+(on|in)\s+youtube\s*$/i, "")
    .replace(/^youtube\s+/i, "")
    .trim();
}

function mediaControlIntent(text) {
  const value = text.toLowerCase();
  if (!/\b(video|youtube|music|song|media|playback|pause|resume|next|previous|mute|unmute|stop)\b/.test(value)) return "";
  if (/\b(pause|hold)\b/.test(value)) return "pause";
  if (/\b(resume|continue)\b/.test(value)) return "play";
  if (/\b(next|forward)\b/.test(value)) return "next";
  if (/\b(previous|back|last video)\b/.test(value)) return "previous";
  if (/\bunmute\b/.test(value)) return "unmute";
  if (/\bmute\b/.test(value)) return "mute";
  if (/\bstop\b/.test(value)) return "stop";
  return "";
}

function youtubeCommand(command) {
  activeYouTubeFrame?.contentWindow?.postMessage(JSON.stringify({
    event: "command",
    func: command,
    args: [],
  }), "*");
}

function showYouTubeAt(index) {
  if (!activeYouTubeVideos.length) return false;
  activeYouTubeIndex = (index + activeYouTubeVideos.length) % activeYouTubeVideos.length;
  const video = activeYouTubeVideos[activeYouTubeIndex];
  renderLiveWorkspace({
    type: "youtube",
    title: video.title,
    summary: `Playing from ${video.channel}`,
    embed_url: video.embed_url,
    watch_url: `https://www.youtube.com/watch?v=${video.id}`,
    videos: activeYouTubeVideos,
  });
  return true;
}

function controlMedia(parameters = {}) {
  const action = parameters.action || "";
  if (action === "next") showYouTubeAt(activeYouTubeIndex + 1);
  else if (action === "previous") showYouTubeAt(activeYouTubeIndex - 1);
  else youtubeCommand({
    play: "playVideo",
    pause: "pauseVideo",
    stop: "stopVideo",
    mute: "mute",
    unmute: "unMute",
  }[action]);
  return `Media ${action || "control"} completed`;
}

function handleAutomaticMediaControl(text) {
  const action = mediaControlIntent(text);
  if (!action) return false;
  controlMedia({ action });
  updateAgentContext(`The visible media player completed the ${action} command.`);
  return true;
}

async function handleAutomaticCalendarIntent(text) {
  const value = text.toLowerCase();
  if (!/\b(calendar|schedule|appointments?|meetings?)\b/.test(value) || /\b(create|add|book|fix|schedule a)\b/.test(value)) return false;
  const key = value.replace(/\s+/g, " ").trim();
  if (key === lastCalendarIntent) return false;
  lastCalendarIntent = key;
  try {
    await runIntegration({ tool_name: "calendar_events", arguments: { max_results: 20 } });
    updateAgentContext("The user's live Google Calendar is visible. Summarize the most relevant events.");
    return true;
  } catch (error) {
    renderLiveWorkspace({
      type: "brief",
      title: "Calendar connection issue",
      summary: error?.message || "Connect Google Calendar to continue.",
    });
    return false;
  }
}

async function handleAutomaticYouTubeIntent(text) {
  const query = youtubeIntentQuery(text);
  if (!query || query === lastYouTubeIntent) return false;
  lastYouTubeIntent = query;
  renderLiveWorkspace({
    type: "progress",
    title: "Searching YouTube",
    summary: `Finding the best result for “${query}”…`,
    steps: ["Connecting to YouTube", "Checking playable videos", "Preparing the player"],
  });
  try {
    const result = await runIntegration({
      tool_name: "youtube_search",
      arguments: { query, max_results: 5 },
    });
    updateAgentContext(
      `Snapkey searched YouTube successfully and displayed the top playable result for "${query}". ` +
      "Tell the user the video is ready beside you."
    );
    return result;
  } catch (error) {
    const searchUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
    renderLiveWorkspace({
      type: "youtube",
      title: "Open YouTube results",
      summary: error?.message || "YouTube search needs attention.",
      watch_url: searchUrl,
      details: "Use the button below while the YouTube API key is checked.",
    });
    updateAgentContext(
      `YouTube search could not complete because: ${error?.message || "the integration failed"}. ` +
      "A direct YouTube search button is visible. Explain that briefly."
    );
    return false;
  }
}

async function handleAutomaticBrowserIntent(text) {
  if (youtubeIntentQuery(text) || monitoringIntent(text)) return;
  const url = browserIntentUrl(text);
  const intentKey = `${text}|${url}`;
  if (!url || intentKey === lastBrowserIntent || browserStarting) return;
  lastBrowserIntent = intentKey;
  browserStarting = true;
  try {
    await startBrowser({ title: "Live browser", url });
  } catch (error) {
    updateAgentContext(
      `Snapkey could not complete the live browser request. Reason: ${error?.message || "browser connection failed"}. ` +
      "Explain the issue briefly without claiming that browsing is unavailable in general."
    );
    renderLiveWorkspace({
      type: "brief",
      title: "Browser connection issue",
      summary: error?.message || "Unable to start the live browser.",
      details: "Check Browserbase variables and Railway deployment logs.",
    });
  } finally {
    browserStarting = false;
  }
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
  stopMonitoringClock();
  const workspace = document.querySelector("#live-workspace");
  workspace.className = `live-workspace ${data.type || "brief"}`;
  workspace.replaceChildren();
  setWorkspaceVisible(true);

  const header = document.createElement("div");
  header.className = "live-workspace-header";
  const label = document.createElement("small");
  label.textContent = `${(data.type || "brief").toUpperCase()} WORKSPACE`;
  const title = document.createElement("h3");
  title.textContent = data.title || liveWorkspaceTitle(data.type);
  const summary = document.createElement("p");
  summary.textContent = data.summary || data.body || "Ready while we continue talking.";
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Close workspace";
  close.onclick = window.closeLiveWorkspace;
  header.append(label, close, title, summary);
  workspace.append(header);

  if (data.type === "calendar") renderCalendar(workspace, data);
  else if (data.type === "email" || data.type === "gmail") renderLiveEmail(workspace, data);
  else if (data.type === "youtube") renderYouTube(workspace, data);
  else if (data.type === "browser") renderBrowser(workspace, data);
  else if (data.type === "report") renderReport(workspace, data);
  else if (data.type === "monitoring") renderMonitoring(workspace, data);
  else if (data.type === "thankyou") renderThankYou(workspace, data);
  else if (["retail", "bar", "inventory"].includes(data.type)) renderRetail(workspace, data);
  else renderDetailList(workspace, parseDetails(data.details || data.items || data.steps));
}

function renderThankYou(workspace, data) {
  const panel = document.createElement("div");
  panel.className = "live-thankyou";
  panel.innerHTML = "<div><span>S</span></div><small>SNAPKEY</small><h3></h3><p></p>";
  panel.querySelector("h3").textContent = data.title || "Thank you.";
  panel.querySelector("p").textContent = data.summary || "Ready whenever you are.";
  workspace.append(panel);
}

const simulatedCameras = [
  { id: 1, name: "Retail floor", person: "Anita S.", activity: "Serving customer", status: "active", zone: "Counter A" },
  { id: 2, name: "Stock room", person: "Rahul K.", activity: "Stock counting", status: "active", zone: "Rack 4" },
  { id: 3, name: "Back office", person: "Vikram P.", activity: "Idle", status: "idle", zone: "Desk 2" },
];

function renderMonitoring(workspace, data) {
  const notice = document.createElement("div");
  notice.className = "monitoring-demo-notice";
  notice.textContent = "SIMULATED DEMO · No real cameras or employee analytics are connected";
  workspace.append(notice);

  const metrics = document.createElement("div");
  metrics.className = "monitoring-metrics";
  [
    ["People detected", "5"],
    ["Active", "4"],
    ["Idle review", "1"],
    ["Cameras online", "3 / 3"],
  ].forEach(([label, value]) => {
    const item = document.createElement("span");
    item.innerHTML = "<small></small><strong></strong>";
    item.querySelector("small").textContent = label;
    item.querySelector("strong").textContent = value;
    metrics.append(item);
  });
  workspace.append(metrics);

  const grid = document.createElement("div");
  grid.className = `monitoring-grid${data.selected_camera ? " focused" : ""}`;
  simulatedCameras.forEach((camera, index) => {
    const tile = document.createElement("button");
    const feedUrl = window.SnapkeyConfig?.monitoring_camera_urls?.[index] || "";
    tile.type = "button";
    tile.className = `camera-tile camera-${camera.id} ${camera.status}`;
    if (data.selected_camera && data.selected_camera !== camera.id) tile.classList.add("camera-hidden");
    tile.onclick = () => renderLiveWorkspace({ ...data, selected_camera: data.selected_camera === camera.id ? 0 : camera.id });
    tile.innerHTML = `
      <div class="camera-scene">
        ${feedUrl ? "<video muted autoplay loop playsinline preload='metadata'></video><span class='camera-feed-state'>Loading video feed...</span>" : ""}
        <span class="camera-grid-lines"></span>
        <span class="camera-person person-${index + 1}"></span>
        <span class="detection-box"><b></b></span>
        <span class="camera-live-dot"></span>
        <time data-monitor-clock></time>
      </div>
      <div class="camera-meta">
        <span><small></small><strong></strong></span>
        <span><small></small><strong></strong></span>
      </div>`;
    if (feedUrl) {
      const video = tile.querySelector("video");
      const state = tile.querySelector(".camera-feed-state");
      video.src = feedUrl;
      video.onplaying = () => state.classList.add("hidden");
      video.onerror = () => {
        state.textContent = "Video unavailable - showing fallback";
        window.setTimeout(() => state.classList.add("hidden"), 2500);
      };
      video.play().catch(() => {
        state.textContent = "Tap camera to start video";
      });
    }
    tile.querySelector(".camera-meta span:first-child small").textContent = `CAM ${camera.id} · ${camera.name}`;
    tile.querySelector(".camera-meta span:first-child strong").textContent = camera.person;
    tile.querySelector(".camera-meta span:last-child small").textContent = camera.zone;
    tile.querySelector(".camera-meta span:last-child strong").textContent = camera.activity;
    tile.querySelector(".detection-box b").textContent = `${camera.person} · ${camera.status === "idle" ? "IDLE" : "WORKING"} · ${96 - index * 3}%`;
    grid.append(tile);
  });
  workspace.append(grid);

  const workers = document.createElement("div");
  workers.className = "worker-status-list";
  [
    ["Anita S.", "Serving customers", "Active now", "active"],
    ["Rahul K.", "Stock verification", "Active now", "active"],
    ["Priya M.", "Billing terminal", "Screen shared", "shared"],
    ["Vikram P.", "No activity detected", "Idle for 08:14", "idle"],
  ].forEach(([name, task, timing, status]) => {
    const row = document.createElement("article");
    row.className = status;
    row.innerHTML = "<i></i><span><strong></strong><small></small></span><b></b>";
    row.querySelector("strong").textContent = name;
    row.querySelector("small").textContent = task;
    row.querySelector("b").textContent = timing;
    workers.append(row);
  });
  workspace.append(workers);

  const screen = document.createElement("div");
  screen.className = "simulated-screen-share";
  screen.innerHTML = `
    <div><span></span><small>PRIYA M. · POS SCREEN SHARE · SIMULATED</small></div>
    <section><aside></aside><main><span></span><span></span><span></span><span></span></main></section>`;
  const screenUrl = window.SnapkeyConfig?.monitoring_screen_url || "";
  if (screenUrl) {
    screen.querySelector("section").classList.add("hidden");
    const video = document.createElement("video");
    const state = document.createElement("span");
    video.muted = true;
    video.autoplay = true;
    video.loop = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.src = screenUrl;
    state.className = "screen-feed-state";
    state.textContent = "Loading screen demo...";
    video.onplaying = () => state.classList.add("hidden");
    video.onerror = () => {
      state.textContent = "Screen video unavailable";
    };
    video.play().catch(() => {
      state.textContent = "Tap to start screen video";
    });
    screen.append(video, state);
  }
  workspace.append(screen);
  updateMonitoringClocks();
  monitoringClock = window.setInterval(updateMonitoringClocks, 1000);
}

function updateMonitoringClocks() {
  const time = new Intl.DateTimeFormat("en-IN", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(new Date());
  document.querySelectorAll("[data-monitor-clock]").forEach(clock => {
    clock.textContent = time;
  });
}

function stopMonitoringClock() {
  if (monitoringClock) window.clearInterval(monitoringClock);
  monitoringClock = null;
}

function renderReport(workspace, data) {
  const rows = Array.isArray(data.rows) ? data.rows.slice(0, 50) : [];
  if (!rows.length) return renderDetailList(workspace, ["No matching report data was found."]);
  activeReport = { ...data, rows };
  const controls = document.createElement("div");
  controls.className = "live-report-controls";
  ["bar", "line", "donut", "table"].forEach(chart => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = chart;
    button.classList.toggle("active", (data.chart || "bar") === chart);
    button.onclick = () => renderLiveWorkspace({ ...activeReport, chart });
    controls.append(button);
  });
  workspace.append(controls);
  const panel = document.createElement("div");
  panel.className = `live-report-chart ${data.chart || "bar"}`;
  const maximum = Math.max(...rows.map(row => Number(row.value) || 0), 1);
  if (data.chart === "donut") {
    const total = Math.max(rows.reduce((sum, row) => sum + (Number(row.value) || 0), 0), 1);
    let position = 0;
    const colors = ["#8268ff", "#4bc8ed", "#5fd29a", "#f6c945", "#ff7696", "#5b63d3"];
    const stops = rows.map((row, index) => {
      const start = position;
      position += (Number(row.value) || 0) / total * 100;
      return `${colors[index % colors.length]} ${start}% ${position}%`;
    });
    panel.style.setProperty("--donut", `conic-gradient(${stops.join(",")})`);
  }
  rows.forEach(row => {
    const item = document.createElement("div");
    item.className = "live-report-item";
    item.tabIndex = 0;
    item.title = `${row.label}: ${formatReportValue(row.value)}`;
    const label = document.createElement("span");
    label.textContent = row.label;
    const bar = document.createElement("i");
    bar.style.setProperty("--value", `${Math.max(3, (Number(row.value) || 0) / maximum * 100)}%`);
    const value = document.createElement("strong");
    value.textContent = formatReportValue(row.value);
    item.append(label, bar, value);
    panel.append(item);
  });
  workspace.append(panel);
  const footer = document.createElement("div");
  footer.className = "live-report-footer";
  footer.textContent = `${rows.length} aggregated points shown · total ${formatReportValue(data.total)}`;
  workspace.append(footer);
}

function formatReportValue(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(number)
    : String(value ?? "");
}

function renderYouTube(workspace, data) {
  const url = data.embed_url || data.url;
  const watchUrl = data.watch_url || url;
  if (!url) return renderMediaFallback(workspace, data, watchUrl, "Open YouTube");
  const panel = document.createElement("div");
  panel.className = "live-media-panel";
  const state = document.createElement("div");
  state.className = "live-media-state";
  state.textContent = "Loading the video…";
  const frame = document.createElement("iframe");
  frame.className = "live-embed";
  frame.src = url.includes("enablejsapi=1") ? url : `${url}${url.includes("?") ? "&" : "?"}enablejsapi=1`;
  frame.allow = "autoplay; encrypted-media; picture-in-picture";
  frame.allowFullscreen = true;
  frame.onload = () => {
    activeYouTubeFrame = frame;
    state.classList.add("hidden");
  };
  frame.onerror = () => {
    state.textContent = "The embedded player could not load. Open it directly instead.";
  };
  panel.append(state, frame);
  workspace.append(panel);
  const controls = document.createElement("div");
  controls.className = "live-media-controls";
  [["previous", "Previous"], ["play", "Play"], ["pause", "Pause"], ["next", "Next"], ["mute", "Mute"]].forEach(([action, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.onclick = () => controlMedia({ action });
    controls.append(button);
  });
  workspace.append(controls);
  if (watchUrl) appendExternalLink(workspace, watchUrl, "Open on YouTube");
}

function renderBrowser(workspace, data) {
  const url = data.live_view_url || data.url;
  if (!url) return renderDetailList(workspace, parseDetails(data.details));
  const panel = document.createElement("div");
  panel.className = "live-media-panel";
  const state = document.createElement("div");
  state.className = "live-media-state";
  state.textContent = "Connecting to the live browser…";
  const frame = document.createElement("iframe");
  frame.className = "live-embed browser-live-view";
  frame.src = url;
  frame.allow = "clipboard-read; clipboard-write";
  frame.onload = () => state.classList.add("hidden");
  frame.onerror = () => {
    state.textContent = "The live browser preview could not load here. Open it in a new tab.";
  };
  panel.append(state, frame);
  workspace.append(panel);
  appendExternalLink(workspace, url, "Open live browser");
}

function appendExternalLink(workspace, url, label) {
  const link = document.createElement("a");
  link.className = "live-media-link";
  link.href = url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = label;
  workspace.append(link);
}

function renderMediaFallback(workspace, data, url, label) {
  renderDetailList(workspace, parseDetails(data.details || data.summary));
  if (url) appendExternalLink(workspace, url, label);
}

function liveWorkspaceTitle(type) {
  return {
    calendar: "Calendar and meetings",
    email: "Gmail workspace",
    gmail: "Gmail workspace",
    retail: "Madhushala operations",
    bar: "Madhushala operations",
    inventory: "Inventory overview",
    monitoring: "Operations monitoring",
  }[type] || "Live workspace";
}

function renderCalendar(workspace, data) {
  const panel = document.createElement("div");
  panel.className = "live-calendar";
  const events = parseDetails(data.events || data.details);
  const todayIndex = (new Date().getDay() + 6) % 7;
  const monday = new Date();
  monday.setDate(monday.getDate() - todayIndex);
  ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach((day, index) => {
    const card = document.createElement("article");
    const date = new Date(monday);
    date.setDate(monday.getDate() + index);
    if (index === todayIndex) card.classList.add("today");
    card.innerHTML = `<small>${day}</small><strong>${date.getDate()}</strong><span></span>`;
    card.querySelector("span").textContent = index === todayIndex && data.today_events
      ? parseDetails(data.today_events).join(" · ")
      : events[index] || "Available";
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
    setWorkspaceVisible(true);
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
  if (!window.SnapkeyUI.isAuthenticated()) {
    setState("idle", "Sign in to start.", "Your account securely connects your business tools and reports.");
    window.showAccount();
    return;
  }
  setConnected(true);
  setState("connecting", "Joining the conversation…", "Please allow microphone access when your browser asks.");
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
    const response = await window.SnapkeyUI.api("/voice/conversation-token", { method: "POST" });
    integrationToken = response.tool_token;
    conversation = await Conversation.startSession({
      conversationToken: response.token,
      connectionType: "webrtc",
      dynamicVariables: { snapkey_tool_token: response.tool_token },
      overrides: {
        agent: { language: response.language || "hi" },
        tts: response.voice_id ? { voiceId: response.voice_id } : undefined,
      },
      clientTools,
      onConnect: () => {
        setConnected(true);
        updateAgentContext(
          "Snapkey live workspace is connected. You can use run_integration for retail_report, calendar_events, " +
          "calendar_create, gmail_search, gmail_read, gmail_draft, gmail_send, and youtube_search. " +
          "Use show_monitoring_workspace for configured camera feeds, start_browser/control_browser for web tasks, " +
          "and control_media for play, pause, stop, next, previous, mute, or unmute. " +
          "Explain successful visible workspaces briefly. Require confirmation before sending email, creating events, " +
          "or performing consequential browser actions."
        );
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
        if (text && message.source === "user") {
          handleAutomaticMediaControl(text);
          handleAutomaticMonitoringIntent(text);
          handleAutomaticReportDisplay(text);
          handleAutomaticRetailReport(text);
          handleAutomaticCalendarIntent(text);
          handleAutomaticYouTubeIntent(text);
          handleAutomaticBrowserIntent(text);
        }
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
    console.error("Unable to start ElevenLabs live conversation", error);
    conversation = null;
    setConnected(false);
    const detail = error?.message || "Check microphone permission and ElevenLabs configuration.";
    setState("error", "Live voice could not connect.", `${detail} The visual demo remains available.`);
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
