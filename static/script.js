console.log("js ran")
let messages = 0;
function getChatId() {
    const params = new URLSearchParams(window.location.search);
    let chatId = params.get("chat_id");
    if (chatId === null) {
        let number = 0;
        chatId = "";
        for (let i = 0; i < 32; i++) {
            number = Math.random()*36;
            number = Math.floor(number);
            number = number.toString(36);
            chatId += number;
        }
        location.href = "/?chat_id="+chatId;
    }
    return chatId;
}
function submit(){
    const textValue = document.getElementById('user_input').value;
    document.getElementById('user_input').value = '';
    document.getElementById('msghs').innerHTML += `<div class="msg"><div class="user">${textValue}</div></div><br>`;
    let thinking = document.getElementById('thinking')
    thinking.style = "distplay:block;"
    let submitarea = document.getElementById("submitarea")
    submitarea.style = "display:none;"
    console.log("ran?")
    console.log(textValue)
    const type = document.getElementById("type").value;
    fetch('/ask?chat_id=' + getChatId() + "&type_selector=" + type, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: textValue })
    })
    .then(response => response.json())
    .then(data => {
        const msghs = document.getElementById('msghs');

        const msgDiv = document.createElement('div');
        msgDiv.className = 'msg';
 
        const aiDivRaw = document.createElement('div');
        aiDivRaw.className = 'ai markdown-body';
        aiDivRaw.id = `ai-raw-${messages}`;
        aiDivRaw.style.display = 'none'

        const aiDivRender = document.createElement('div');
        aiDivRender.className = 'ai markdown-body';
        aiDivRender.id = `ai-render-${messages}`;

        msgDiv.appendChild(aiDivRaw);
        msgDiv.appendChild(aiDivRender);
        msghs.appendChild(msgDiv);
        msghs.appendChild(document.createElement('br'));

        if (data.error) {
            aiDivRaw.innerText = data.error;
            thinking.style.display = "none";
            return;
        }

        function addCopyButtons(container) {
            container.querySelectorAll('pre').forEach(pre => {
                const button = document.createElement('button');
                button.className = 'copy-btn';
                button.innerText = 'Copied!';
                button.innerHTML = '<i class="fa fa-copy"></i> Copy';
                button.onclick = () => {
                    const code = pre.querySelector('code');
                    navigator.clipboard.writeText(code.innerText).then(() => {
                        button.innerText = 'Copied!';
                        setTimeout(() => button.innerHTML = '<i class="fa fa-copy"></i> Copy', 1500);
                    });
                };
                pre.style.position = 'relative';
                button.style.position = 'absolute';
                button.style.top = '8px';
                button.style.right = '8px';
                button.style.fontSize = '12px';
                button.style.padding = '4px 8px';
                button.style.backgroundColor = '#24292e';
                button.style.color = '#fff';
                button.style.border = 'none';
                button.style.borderRadius = '4px';
                button.style.cursor = 'pointer';
                pre.appendChild(button);
            });
        }

        let rawMd = "";
        let index = 0;
        let tick = 0;
        function streamText() {
            if (index < data.response.length) {
                rawMd += data.response.charAt(index);
                aiDivRaw.textContent = rawMd;
                index++;
                tick++
                if (tick % 3 == 0) {
                    const html = DOMPurify.sanitize(marked.parse(rawMd));
                    aiDivRender.innerHTML = html;
                    aiDivRender.querySelectorAll('pre code').forEach(hljs.highlightElement);
                }
                setTimeout(streamText, 15);
            }
            const html = DOMPurify.sanitize(marked.parse(rawMd));
            aiDivRender.innerHTML = html;
            aiDivRender.querySelectorAll('pre code').forEach(hljs.highlightElement);
            addCopyButtons(aiDivRender);
        }

        streamText();
        thinking.style.display = "none";
        submitarea.style = "display:block;"
        messages++;
        loadHistory();
    });
}

function loadHistory() {
    let historylist = document.getElementById("historylist")
    chat_id = getChatId()
    fetch("/loadhistory", {
        method: "POST"
    }).then(response => response.json())
    .then(data => {
        console.log(data.history)
        console.log(data.error)
        if (data.history) {
            historylist.innerHTML = "";
            data.history.forEach(chat => {
                historylist.innerHTML += `<div class="chat-history-item"><a href="/?chat_id=${chat[1]}">${chat[0]}</a></div>`;
            })
        }
    });
}

function loadChat() {
    chat_id = getChatId();
    fetch("/get_chat_history?chat_id="+ chat_id, {
        method: "POST"
    }).then(response => response.json())
    .then(data => {
        console.log(data);
        data.forEach(message => {
            console.log(message);
            if (message[1]) {
                document.getElementById('msghs').innerHTML += `<div class="msg"><div class="ai markdown-body">${message[0]}</div></div><br>`;
            } else {
                document.getElementById('msghs').innerHTML += `<div class="msg"><div class="user">${message[0]}</div></div><br>`;
            }
        });
    });

}

window.onload = function() {
    loadHistory();
    loadChat();
}