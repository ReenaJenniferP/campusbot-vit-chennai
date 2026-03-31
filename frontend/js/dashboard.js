const dashboardName = document.getElementById("dashboardName");
const savedUser = localStorage.getItem("campusbot_user");

if (dashboardName && savedUser) {
  dashboardName.textContent = savedUser;
}