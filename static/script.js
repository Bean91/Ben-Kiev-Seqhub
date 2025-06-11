document.getElementById('submit').addEventListener('click', function() {
    const userInput = document.getElementById('user_input').value;

    fetch('http://your-ngrok-url/ask', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ prompt: userInput })
    })
    .then(response => response.json())
    .then(data => {
        console.log(data.response);
    })
    .catch(error => console.error('Error:', error));
});