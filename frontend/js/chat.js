const chatInput = document.getElementById("chatInput");
const sendChatBtn = document.getElementById("sendChatBtn");
const chatWindow = document.getElementById("chatWindow");
const promptButtons = document.querySelectorAll(".prompt-chip");

function addMessage(text, type) {
  if (!chatWindow || !text.trim()) return;

  const div = document.createElement("div");
  div.className = `message ${type === "user" ? "user-message" : "bot-message"}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function sendMessage() {
  if (!chatInput) return;

  const text = chatInput.value.trim();
  if (!text) return;

  addMessage(text, "user");
  chatInput.value = "";

  setTimeout(() => {
    addMessage("This is a front-end demo response for the redesigned CampusBot interface.", "bot");
  }, 500);
}

if (sendChatBtn) {
  sendChatBtn.addEventListener("click", sendMessage);
}

if (chatInput) {
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendMessage();
  });
}

promptButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (chatInput) {
      chatInput.value = btn.textContent;
      sendMessage();
    }
  });
});