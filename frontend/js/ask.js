const input = document.getElementById("q");
const answerBox = document.getElementById("answer");
const askBtn = document.getElementById("askBtn");
const clearBtn = document.getElementById("clearBtn");
const sourcesWrap = document.getElementById("sources");
const sourcesTitle = document.getElementById("sourcesTitle");

const API_URL = "https://arab-payments-light-main.trycloudflare.com/ask";

function clearOutput() {
  answerBox.textContent = "Ask a question to see the answer here.";
  sourcesWrap.innerHTML = "";
  sourcesTitle.style.display = "none";
}

async function ask() {
  const question = input.value.trim();
  if (!question) return;

  answerBox.textContent = "Searching campus data and preparing answer...";
  sourcesWrap.innerHTML = "";
  sourcesTitle.style.display = "none";
  askBtn.disabled = true;

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question })
    });

    if (!res.ok) {
      answerBox.textContent = "Server error: " + res.status;
      askBtn.disabled = false;
      return;
    }

    const data = await res.json();
    answerBox.textContent = data.answer ?? "(No answer returned)";

    const srcs = data.sources || [];
    if (srcs.length) {
      sourcesTitle.style.display = "block";
      sourcesWrap.innerHTML = srcs.slice(0, 8).map(s => {
        const title = (s.title || "Source").toString();
        const url = (s.url || "").toString();
        const score = (typeof s.score === "number") ? s.score.toFixed(3) : "";
        return `
          <div class="src">
            <span class="pill">score ${score}</span>
            <a href="${url}" target="_blank" rel="noopener noreferrer">${title}</a>
            <div class="url">${url}</div>
          </div>
        `;
      }).join("");
    }
  } catch (e) {
    answerBox.textContent = "Backend not running. Start server.py then refresh.\n\nError: " + e;
  }

  askBtn.disabled = false;
}

if (askBtn) {
  askBtn.addEventListener("click", ask);
}

if (clearBtn) {
  clearBtn.addEventListener("click", () => {
    input.value = "";
    clearOutput();
    input.focus();
  });
}

if (input) {
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") ask();
  });
  input.focus();
}