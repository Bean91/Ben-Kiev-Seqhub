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

        // Create two divs: one for streaming text, one for final rendered markdown
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
    })
}
