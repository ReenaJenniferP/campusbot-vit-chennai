const loginBtn = document.getElementById("loginBtn");
const togglePass = document.getElementById("togglePass");
const passInput = document.getElementById("pass");
const signupBtn = document.getElementById("signupBtn");

if (togglePass && passInput) {
  togglePass.addEventListener("click", () => {
    const isPassword = passInput.type === "password";
    passInput.type = isPassword ? "text" : "password";
    togglePass.textContent = isPassword ? "Hide" : "Show";
  });
}

if (loginBtn) {
  loginBtn.addEventListener("click", () => {
    const user = document.getElementById("user")?.value?.trim() || "Student";
    localStorage.setItem("campusbot_user", user);
    window.location.href = "dashboard.html";
  });
}

if (signupBtn) {
  signupBtn.addEventListener("click", () => {
    const fullName = document.getElementById("fullName")?.value?.trim();
    const email = document.getElementById("email")?.value?.trim();
    const regNo = document.getElementById("regNo")?.value?.trim();
    const newPass = document.getElementById("newPass")?.value || "";
    const confirmPass = document.getElementById("confirmPass")?.value || "";

    if (!fullName || !email || !regNo || !newPass || !confirmPass) {
      alert("Please fill in all fields.");
      return;
    }

    if (newPass !== confirmPass) {
      alert("Passwords do not match.");
      return;
    }

    localStorage.setItem("campusbot_user", fullName);
    window.location.href = "dashboard.html";
  });
}