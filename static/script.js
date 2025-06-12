console.log("js ran")
function submit(){
    const textValue = document.getElementById('user_input').value;
    document.getElementById('user_input').value = '';
    document.getElementById('msghs').innerHTML += `<div class="msg"><div class="user">${textValue}</div></div><br><br>`;
    console.log("ran?")
    console.log(textValue)
    fetch('/ask', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: textValue })
    })
    .then(response => response.json())
    .then(data => {
        // Handle the response from the server
        document.getElementById('msghs').innerHTML += `<div class="msg"><div class="ai">${data.response || data.error}</div></div><br><br>`;
    })
    .catch(error => console.error('Error:', error));
}
