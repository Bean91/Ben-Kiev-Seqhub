console.log("js ran")
function getChatId() {
    let chatId = sessionStorage.getItem("chat_id");
    if (!chatId) {
        // Generate random ID (you can make this more secure if needed)
        chatId = crypto.randomUUID(); // or use a fallback generator
        sessionStorage.setItem("chat_id", chatId);
    }
    return chatId;
}
function submit(){
    const textValue = document.getElementById('user_input').value;
    document.getElementById('user_input').value = '';
    document.getElementById('msghs').innerHTML += `<div class="msg"><div class="user">${textValue}</div></div><br>`;
    console.log("ran?")
    console.log(textValue)
    fetch('/ask?chat_id=' + getChatId(), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: textValue })
    })
    .then(response => response.json())
    .then(data => {
        // Handle the response from the server
        document.getElementById('msghs').innerHTML += `<div class="msg"><div class="ai">${data.response || data.error}</div></div><br>`;
    })
    .catch(error => console.error('Error:', error));
}
