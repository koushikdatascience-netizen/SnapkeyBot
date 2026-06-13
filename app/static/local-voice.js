let localSession = null;
let localMuted = false;
let activeAudio = null;
let processing = false;
let speechStartedAt = 0;
let silenceStartedAt = 0;
let speechSamples = [];
let preRoll = [];

const originalStart = window.startLiveConversation;
const originalEnd = window.endLiveConversation;
const originalMute = window.toggleLiveMute;

function localConfigured() {
  return Boolean(window.SnapkeyConfig?.local_voice_ready && !window.SnapkeyConfig?.live_agent_ready);
}

function liveUI() {
  return window.SnapkeyLive;
}

function stopActiveSpeech() {
  if (!activeAudio) return;
  activeAudio.pause();
  activeAudio.src = "";
  activeAudio = null;
}

function addPurchaseUploadButton() {
  const workspace = document.querySelector("#live-workspace");
  if (!workspace || workspace.querySelector(".local-purchase-upload")) return;
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".csv,.pdf,text/csv,application/pdf";
  input.className = "hidden";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "local-purchase-upload";
  button.textContent = "Upload purchase PDF or CSV";
  button.onclick = () => input.click();
  input.onchange = async () => {
    const file = input.files?.[0];
    if (!file) return;
    button.disabled = true;
    button.textContent = "Validating invoice…";
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await window.SnapkeyUI.api("/local-voice/purchase-preview", { method: "POST", body: form });
      liveUI()?.renderLiveWorkspace(result.workspace);
      liveUI()?.setState("speaking", result.reply, "Nothing has been written to Madhushala.");
    } catch (error) {
      liveUI()?.setState("error", "Invoice preview failed.", error?.message || "Check the CSV columns.");
    }
  };
  workspace.append(input, button);
}

async function speakLocalReply(text) {
  if (!text) return;
  stopActiveSpeech();
  try {
    const response = await fetch("/api/local-voice/speech", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) return;
    activeAudio = new Audio(URL.createObjectURL(await response.blob()));
    activeAudio.onended = () => {
      activeAudio = null;
      liveUI()?.setState("listening", "I’m listening.", "Speak naturally or type another request.");
    };
    await activeAudio.play();
  } catch {
    // The visible response remains available when local speech is not configured.
  }
}

async function executeLocalCommand(prompt, { speak = true } = {}) {
  const response = await window.SnapkeyUI.api("/local-voice/command", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
  if (response.workspace) liveUI()?.renderLiveWorkspace(response.workspace);
  if (response.workspace?.title === "Purchase import") addPurchaseUploadButton();
  if (response.desktop_action?.requires_confirmation) {
    const appTitle = (response.desktop_action.app || "application").replace(/(^|[-_])\w/g, value => value.replace(/[-_]/, " ").toUpperCase());
    const decision = await liveUI()?.requestConfirmation({
      title: `Close ${appTitle}?`,
      summary: "Save any active work before closing the application.",
    });
    if (decision?.includes("confirmed")) {
      await window.SnapkeyUI.api("/local-voice/desktop-action", {
        method: "POST",
        body: JSON.stringify({ app: response.desktop_action.app, action: response.desktop_action.action, confirmed: true }),
      });
      response.reply = `${appTitle} received a safe close request.`;
    } else {
      response.reply = `Okay. I kept ${appTitle} open.`;
    }
  }
  liveUI()?.setState(speak ? "speaking" : "listening", response.reply || "Done.", "The requested workspace is visible.");
  if (speak) await speakLocalReply(response.reply);
  return response;
}

window.SnapkeyLocal = { executeCommand: executeLocalCommand, speak: speakLocalReply };

function mergeSamples(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  chunks.forEach(chunk => {
    result.set(chunk, offset);
    offset += chunk.length;
  });
  return result;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const write = (offset, value) => [...value].forEach((character, index) => view.setUint8(offset + index, character.charCodeAt(0)));
  write(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  write(8, "WAVE");
  write(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  write(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, index) => {
    const bounded = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + index * 2, bounded < 0 ? bounded * 0x8000 : bounded * 0x7fff, true);
  });
  return new Blob([buffer], { type: "audio/wav" });
}

function rms(samples) {
  let sum = 0;
  for (let index = 0; index < samples.length; index += 1) sum += samples[index] * samples[index];
  return Math.sqrt(sum / samples.length);
}

async function submitUtterance(chunks, sampleRate) {
  if (processing || !chunks.length) return;
  processing = true;
  const ui = liveUI();
  ui?.setState("thinking", "Working locally…", "Understanding your request and opening the right workspace.");
  try {
    const form = new FormData();
    form.append("audio", encodeWav(mergeSamples(chunks), sampleRate), "utterance.wav");
    const response = await window.SnapkeyUI.api("/local-voice/turn", { method: "POST", body: form });
    if (!response.transcript) {
      ui?.setState("listening", "I’m listening.", "Please speak naturally.");
      return;
    }
    document.querySelector("#live-caption").textContent = response.transcript;
    if (response.workspace) ui?.renderLiveWorkspace(response.workspace);
    if (response.workspace?.title === "Purchase import") addPurchaseUploadButton();
    if (response.desktop_action?.requires_confirmation) {
      await executeLocalCommand(response.transcript);
      processing = false;
      return;
    }
    if (response.audio_base64) {
      const audio = new Audio(`data:${response.audio_content_type || "audio/wav"};base64,${response.audio_base64}`);
      activeAudio = audio;
      audio.onplay = () => ui?.setState("speaking", response.reply, "You can interrupt me at any time.");
      audio.onended = () => {
        activeAudio = null;
        ui?.setState("listening", "I’m listening.", "Speak naturally. Everything is running locally.");
      };
      audio.onerror = audio.onended;
      await audio.play();
    } else {
      ui?.setState("listening", response.reply || "I’m listening.");
    }
  } catch (error) {
    ui?.setState("error", "Local voice needs attention.", error?.message || "The local voice turn failed.");
  } finally {
    processing = false;
  }
}

function handleAudio(event) {
  if (!localSession || localMuted) return;
  const samples = new Float32Array(event.inputBuffer.getChannelData(0));
  const now = performance.now();
  const threshold = 0.025;
  const speaking = rms(samples) >= threshold;
  const minSpeech = Number(window.SnapkeyConfig?.local_voice_min_speech_ms || 350);
  const silenceLimit = Number(window.SnapkeyConfig?.local_voice_silence_ms || 650);

  preRoll.push(samples);
  if (preRoll.length > 8) preRoll.shift();

  if (speaking) {
    if (!speechStartedAt) {
      stopActiveSpeech();
      speechStartedAt = now;
      speechSamples = [...preRoll];
      liveUI()?.setState("listening", "I’m listening.", "Speak naturally. You can interrupt at any time.");
    }
    silenceStartedAt = 0;
    speechSamples.push(samples);
    return;
  }

  if (!speechStartedAt) return;
  speechSamples.push(samples);
  if (!silenceStartedAt) silenceStartedAt = now;
  if (now - silenceStartedAt < silenceLimit) return;

  const duration = now - speechStartedAt;
  const utterance = speechSamples;
  speechStartedAt = 0;
  silenceStartedAt = 0;
  speechSamples = [];
  preRoll = [];
  if (duration >= minSpeech) submitUtterance(utterance, localSession.audioContext.sampleRate);
}

async function startLocalConversation() {
  if (localSession) return;
  if (!window.SnapkeyUI.isAuthenticated()) {
    liveUI()?.setState("idle", "Sign in to start.", "The local assistant uses your account to select the correct shop.");
    window.showAccount();
    return;
  }
  liveUI()?.setConnected(true);
  liveUI()?.setState("connecting", "Starting local voice…", "Loading the microphone and local models.");
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const audioContext = new AudioContext({ latencyHint: "interactive" });
  await audioContext.resume();
  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(2048, 1, 1);
  const silentGain = audioContext.createGain();
  silentGain.gain.value = 0;
  processor.onaudioprocess = handleAudio;
  source.connect(processor);
  processor.connect(silentGain);
  silentGain.connect(audioContext.destination);
  localSession = { stream, audioContext, source, processor, silentGain };
  document.querySelector("#live-privacy").textContent = "Microphone audio stays on this computer and is processed by the local Snapkey runtime.";
  liveUI()?.setState("listening", "I’m listening.", "Local voice is ready. Speak naturally.");
}

async function endLocalConversation() {
  stopActiveSpeech();
  if (localSession) {
    localSession.processor.disconnect();
    localSession.source.disconnect();
    localSession.silentGain.disconnect();
    localSession.stream.getTracks().forEach(track => track.stop());
    await localSession.audioContext.close();
  }
  localSession = null;
  speechSamples = [];
  preRoll = [];
  processing = false;
  liveUI()?.setConnected(false);
  liveUI()?.setState("idle", "Conversation ended.", "Start again whenever you’re ready.");
}

window.startLiveConversation = async function startLiveConversation() {
  if (!localConfigured()) return originalStart?.();
  try {
    await startLocalConversation();
  } catch (error) {
    liveUI()?.setConnected(false);
    liveUI()?.setState("error", "Local voice could not start.", error?.message || "Check microphone permission and local models.");
  }
};

window.endLiveConversation = async function endLiveConversation() {
  if (!localConfigured()) return originalEnd?.();
  return endLocalConversation();
};

window.toggleLiveMute = async function toggleLiveMute() {
  if (!localConfigured()) return originalMute?.();
  localMuted = !localMuted;
  document.querySelector("#live-mute").textContent = localMuted ? "Unmute" : "Mute";
  liveUI()?.setState(localMuted ? "thinking" : "listening", localMuted ? "Microphone muted." : "I’m listening.");
};
