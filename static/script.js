console.log("js ran")
let messages = 0;
function getChatId() {
    let chatId = sessionStorage.getItem("chat_id");
    if (!chatId) {
        let number = 0;
        for (let i = 0; i < 32; i++) {
            number = Math.random()*36;
            number = Math.floor(number);
            number = number.toString(36);
            chatId += number;
        }
        sessionStorage.setItem("chat_id", chatId);
    }
    return chatId;
}
function submit(){
    const textValue = document.getElementById('user_input').value;
    document.getElementById('user_input').value = '';
    document.getElementById('msghs').innerHTML += `<div class="msg"><div class="user">${textValue}</div></div><br>`;
    let thinking = document.getElementById('thinking')
    thinking.style = "distplay:block;"
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
        const msghs = document.getElementById('msghs');

        // Create container divs
        const msgDiv = document.createElement('div');
        msgDiv.className = 'msg';

        const aiDiv = document.createElement('div');
        aiDiv.className = 'ai';
        aiDiv.id = `ai${messages}`;

        msgDiv.appendChild(aiDiv);
        msghs.appendChild(msgDiv);
        msghs.appendChild(document.createElement('br'));

        if (data.error){
            aiDiv.innerText = data.error;
            thinking.style.display = "none";
            return;
        }

        let index = 0;
        function streamText() {
            if (index < data.response.length) {
                aiDiv.textContent += data.response.charAt(index);
                index++;
                setTimeout(streamText, 15);
            }
        }
        streamText();

        thinking.style.display = "none";
        messages++;
    })
}
