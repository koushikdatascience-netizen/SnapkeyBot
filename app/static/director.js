let directorSocket = null;

function updatePresenterLink() {
  const session = document.querySelector("#director-session").value.trim() || "meeting1";
  document.querySelector("#presenter-link").textContent = `${window.location.origin}/?demo_session=${encodeURIComponent(session)}`;
}

window.connectDirector = function connectDirector() {
  directorSocket?.close();
  const session = document.querySelector("#director-session").value.trim() || "meeting1";
  const key = document.querySelector("#director-key").value;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const status = document.querySelector("#director-status");
  status.textContent = "Connecting";
  status.className = "director-status offline";
  directorSocket = new WebSocket(`${protocol}//${window.location.host}/api/operator/demo/${encodeURIComponent(session)}?role=operator&key=${encodeURIComponent(key)}`);
  directorSocket.onmessage = event => {
    const message = JSON.parse(event.data);
    const count = message.presenters || 0;
    status.textContent = count ? `${count} presenter online` : "Waiting for presenter";
    status.className = `director-status ${count ? "online" : "offline"}`;
    if (message.type === "delivered") {
      document.querySelector("#director-message").textContent = `${message.scene} scene delivered to ${count} presenter screen${count === 1 ? "" : "s"}.`;
    }
  };
  directorSocket.onclose = event => {
    status.textContent = event.code === 1008 ? "Invalid secret" : "Disconnected";
    status.className = "director-status offline";
  };
  updatePresenterLink();
};

window.sendScene = function sendScene(scene) {
  if (!directorSocket || directorSocket.readyState !== WebSocket.OPEN) {
    document.querySelector("#director-message").textContent = "Connect the director first.";
    return;
  }
  directorSocket.send(JSON.stringify({ type: "scene", scene }));
};

document.querySelector("#director-session").addEventListener("input", updatePresenterLink);
updatePresenterLink();
