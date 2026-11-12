const loginForm = document.getElementById("login-form");
const loginButton = loginForm.querySelector('button[type="submit"]');
let loginPending = false;

loginForm.addEventListener("submit", (event) => {
    // Un segundo envío puede usar el token anterior a la rotación del login.
    if (loginPending) {
        event.preventDefault();
        return;
    }

    loginPending = true;
    loginButton.disabled = true;
});

window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
        // Al volver con Atrás, pedir un formulario nuevo o el dashboard.
        window.location.reload();
        return;
    }

    loginPending = false;
    loginButton.disabled = false;
});
