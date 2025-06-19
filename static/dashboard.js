function deleteCookie(name) {
  document.cookie = `${name}=; Max-Age=0; path=/`;
}

function signOut() {
    deleteCookie("session_token");
    window.location.href = "/static/signin.html";
}

function deleteAccount() {
    if (confirm("Are you sure you want to delete your account? This action cannot be undone.")) {
        fetch('/delete_account', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: getCookie("session_token") })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("Account deleted successfully.");
                signOut();
            } else {
                alert("Error deleting account: " + data.error);
            }
        })
        .catch(error => console.error('Error:', error));
    }
}

window.onload = function() {
    fetch('/user_info', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ token: getCookie("session_token") })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(data);
            document.getElementById("currentemail").innerText = data.user_info[1];
            document.getElementById("currentfirstname").innerText = data.user_info[2];
            document.getElementById("currentlastname").innerText = data.user_info[3];
            document.getElementById("currentusername").innerText = data.user_info[0];
        } else {
            alert("Error fetching user info: " + data.error);
        }
    })
    .catch(error => console.error('Error:', error));
}