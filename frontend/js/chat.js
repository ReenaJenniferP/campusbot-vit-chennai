const BACKEND_BASE = "https://impact-das-suites-set.trycloudflare.com";

const chatWindow = document.getElementById("chatWindow");
const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");
const promptChips = document.querySelectorAll(".prompt-chip");
const statusPill = document.getElementById("statusPill");
const statusText = document.getElementById("statusText");

function scrollChatToBottom() {
  if (chatWindow) {
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }
}

function addMessage(text, type, extraClass = "") {
  if (!chatWindow) return null;

  const row = document.createElement("div");
  row.className = "message-row " + (type === "user" ? "user-row" : "bot-row");

  const message = document.createElement("div");
  message.className =
    "message " +
    (type === "user" ? "user-message" : "bot-message") +
    (extraClass ? ` ${extraClass}` : "");

  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = type === "user" ? "You" : "CampusBot";

  const content = document.createElement("div");
  content.textContent = text;

  message.appendChild(meta);
  message.appendChild(content);
  row.appendChild(message);
  chatWindow.appendChild(row);
  scrollChatToBottom();

  return row;
}

async function checkServerStatus() {
  if (!statusPill || !statusText) return;

  try {
    const response = await fetch(`${BACKEND_BASE}/health`, { method: "GET" });
    if (!response.ok) throw new Error("Health check failed");

    statusPill.classList.remove("offline");
    statusPill.classList.add("online");
    statusText.textContent = "Online";
  } catch {
    statusPill.classList.remove("online");
    statusPill.classList.add("offline");
    statusText.textContent = "Offline";
  }
}

async function sendMessage() {
  if (!chatInput) return;

  const text = chatInput.value.trim();
  if (!text) return;

  addMessage(text, "user");
  chatInput.value = "";

  const thinkingRow = addMessage("Thinking...", "bot", "thinking-message");

  try {
    const response = await fetch(`${BACKEND_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text })
    });

    if (!response.ok) throw new Error("Backend request failed");

    const data = await response.json();

    if (thinkingRow) thinkingRow.remove();
    addMessage(data.answer || "No response received.", "bot");
    checkServerStatus();
  } catch {
    if (thinkingRow) thinkingRow.remove();
    addMessage("I’m finding an answer, but I couldn’t connect to the backend right now. Please make sure the FastAPI server is running.", "bot");
    checkServerStatus();
  }
}

if (sendChatBtn) {
  sendChatBtn.addEventListener("click", sendMessage);
}

if (chatInput) {
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendMessage();
    }
  });
}

promptChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    const prompt = chip.dataset.prompt || chip.textContent.trim();
    if (chatInput) {
      chatInput.value = prompt;
      sendMessage();
    }
  });
});

if (chatWindow) {
  addMessage("Hi! Ask me anything about VIT Chennai.", "bot");
  // checkServerStatus();
  // setInterval(checkServerStatus, 15000);
}