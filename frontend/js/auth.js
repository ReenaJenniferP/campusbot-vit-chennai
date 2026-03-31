const loginBtn = document.getElementById("loginBtn");
const signupBtn = document.getElementById("signupBtn");
const dashboardName = document.getElementById("dashboardName");

if (loginBtn) {
  loginBtn.addEventListener("click", (e) => {
    e.preventDefault();
    const email = document.getElementById("loginEmail")?.value?.trim();
    const name = email ? email.split("@")[0] : "Student";
    localStorage.setItem("campusbot_user", name);
    window.location.href = "dashboard.html";
  });
}

if (signupBtn) {
  signupBtn.addEventListener("click", (e) => {
    e.preventDefault();

    const firstName = document.getElementById("firstName")?.value?.trim();
    const lastName = document.getElementById("lastName")?.value?.trim();
    const password = document.getElementById("newPassword")?.value || "";
    const confirmPassword = document.getElementById("confirmPassword")?.value || "";

    if (!firstName || !lastName) {
      alert("Please fill in your name.");
      return;
    }

    if (!password || !confirmPassword) {
      alert("Please enter and confirm your password.");
      return;
    }

    if (password !== confirmPassword) {
      alert("Passwords do not match.");
      return;
    }

    localStorage.setItem("campusbot_user", `${firstName} ${lastName}`);
    window.location.href = "dashboard.html";
  });
}

if (dashboardName) {
  const savedUser = localStorage.getItem("campusbot_user");
  if (savedUser) dashboardName.textContent = savedUser;
}