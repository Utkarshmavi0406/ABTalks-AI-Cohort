import ollama

history = []

print("Local chatbot — type 'quit' to exit")

while True:
    user = input("\nYou: ")

    # To record what we just typed into the running conversation.
    history.append({"role": "user", "content": user})

    # Sending the entire conversation to our local model, which is how it remembers context.
    reply = ollama.chat(model = "qwen3:8b", messages = history)
    
    # Pulling the actual text out of the Ollama response object.
    text = reply["message"]["content"]

    # Records the AI's own reply back into conversation history, so it can remember what it said next time.
    history.append({"role": "assistant", "content": text})
    print(f"\nAI: {text}")

    if user.lower() == "quit":
        break

