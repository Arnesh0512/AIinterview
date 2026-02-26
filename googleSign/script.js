function handleGoogleLogin(response, role) {
  const googleIdToken = response.credential;
  console.log("Role:", role, "Token:", googleIdToken);

  fetch(`http://localhost:8000/auth/${role}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: googleIdToken })
  })
  .then(res => {
    if (!res.ok) throw new Error("Authentication failed");
    return res.json();
  })
  .then(data => {
    console.log(role + " logged in:", data);
    localStorage.setItem(`${role}_access_token`, data.access_token);
    window.location.href = "home.html";
    alert(role + " login successful!");
  })
  .catch(err => {
    console.error(role + " login failed", err);
    alert(role + " sign-in failed");
  });
}



function renderGoogleButtons() {
  const roles = ["user", "admin", "superadmin"];
  const containers = ["user-signin", "admin-signin", "superadmin-signin"];
  const clientId = "239161451898-ilpruu0evotd6li2t21gnsphc8uqplsh.apps.googleusercontent.com";

  roles.forEach((role, idx) => {
    google.accounts.id.initialize({
      client_id: clientId,
      callback: (response) => handleGoogleLogin(response, role)
    });
    google.accounts.id.renderButton(
      document.getElementById(containers[idx]),
      { theme: "outline", size: "large", text: "signin_with", type: "standard" }
    );
  });
}

window.onload = renderGoogleButtons;
















