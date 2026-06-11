import { Conversation } from "@elevenlabs/client";

let conversation = null;
let muted = false;

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
  window.SnapkeyUI.renderPresentation({ type, ...parameters }, []);
  return `${type} workspace displayed`;
}

const clientTools = {
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

window.startLiveConversation = async function startLiveConversation() {
  if (conversation) return;
  setState("connecting", "Joining the conversation…", "Please allow microphone access when your browser asks.");
  try {
    await navigator.mediaDevices.getUserMedia({ audio: true });
    const response = await window.SnapkeyUI.api("/voice/conversation-token", { method: "POST" });
    conversation = await Conversation.startSession({
      conversationToken: response.token,
      connectionType: "webrtc",
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
