document.addEventListener("DOMContentLoaded", () => {
    fetch("/static/navbar.html")
        .then(response => response.text())
        .then(data => {
            document.body.insertAdjacentHTML("afterbegin", data);
            attachNavbarEvents(); // Attach event listeners after navbar loads
        });

    fetch("/static/cookie.html")
        .then(response => response.text())
        .then(data => {
            document.body.insertAdjacentHTML("beforeend", data);
            if (getCookie("cookiesAccepted") === "true") {
                const cookieConsent = document.getElementById("cookie-consent");
                if (cookieConsent) cookieConsent.style.display = "none";
            }
        });
});

function attachNavbarEvents() {
    const menuIcon = document.querySelector('.menuIcon');
    const nav = document.querySelector('.overlay-menu');

    // Update navbar UI based on Stack Auth session
    function updateNavbar() {
        if(getCookie("session_token")) {
            signinLink = document.getElementById('signin-link');
            dashboardLink = document.getElementById('dashboard-link');
            if (signinLink) {
                signinLink.style.display = 'none';
            }
            if (dashboardLink) {
                dashboardLink.style.display = 'inline-block';
            }
        }
    }

    updateNavbar();

    // Menu icon toggle to open overlay menu
    if (menuIcon && nav) {
        menuIcon.addEventListener('click', () => {
            if (nav.style.transform !== 'translateX(0%)') {
                nav.style.transform = 'translateX(0%)';
                nav.style.transition = 'transform 0.2s ease-out';
                updateNavbar();
            } else {
                nav.style.transform = 'translateX(-100%)';
                nav.style.transition = 'transform 0.2s ease-out';
            }
            // Toggle the menu icon class
            if (!menuIcon.classList.contains('toggle')) {
                menuIcon.classList.add('toggle');
                signinLink = document.getElementById('over-signin');
                dashboardLink = document.getElementById('over-dash');
                if(getCookie("session_token")) {
                    if (signinLink) {
                        signinLink.style.display = 'none';
                    }
                    if (dashboardLink) {
                        dashboardLink.style.display = 'inline-block';
                    }
                } else {
                    if (signinLink) {
                        signinLink.style.display = 'inline-block';
                    }
                    if (dashboardLink) {
                        dashboardLink.style.display = 'none';
                    }
                }
            } else {
                menuIcon.classList.remove('toggle');
            }
        });
    }
}

// Cookie helpers (unchanged)
function setCookie(name, value, days) {
    const d = new Date();
    d.setTime(d.getTime() + (days*24*60*60*1000));
    document.cookie = name + "=" + value + ";expires=" + d.toUTCString() + ";path=/";
}

function getCookie(name) {
    const cookies = document.cookie.split(';');
    for(let cookie of cookies) {
        if (cookie.trim().startsWith(name + "=")) {
            return cookie.trim().substring((name + "=").length);
        }
    }
    return null;
}

function acceptCookies() {
    setCookie("cookiesAccepted", "true", 365);
    const cookieConsent = document.getElementById("cookie-consent");
    if (cookieConsent) cookieConsent.style.display = "none";
}

function denyCookies() {
    alert("You denied cookies. This page will now close.");
    window.location.href = "https://www.google.com";
}