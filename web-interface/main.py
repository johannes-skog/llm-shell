import gradio as gr
from ollama import OllamaWrapper

# CSS for dynamically sized text boxes
css = """
.gradio-content .interface-textbox textarea {
    resize: none; /* Prevent manual resizing */
    height: auto; /* Enable auto-height */
    overflow-y: hidden; /* Hide vertical scrollbar */
    padding-bottom: 1rem;
    padding-top: 1rem;
    box-sizing: border-box;
}
.gradio-content .interface-textbox textarea:focus {
    overflow-y: auto; /* Show scrollbar when focused, if necessary */
}
"""

# Initialize Ollama
ollama = OllamaWrapper("http://server:11434")
available_models = [x["name"] for x in ollama.list_local_models()["models"]]


# Define the chat session function
def chat_session(system_prompt, history, model_name):

    messages = [{"role": "system", "content": system_prompt}]

    for entry in history:

        messages.append({"role": "user", "content": entry[0]})
        messages.append({"role": "assistant", "content": entry[1]})

    responses = ollama.generate_chat_completion(
        model=model_name,
        messages=messages,
    )

    for r in responses:
        yield r["message"]["content"]


def user(user_message, history):
    return "", history + [[user_message, None]]


# Gradio interface
with gr.Blocks(css=css) as chat_interface:
    chatbot = gr.Chatbot()
    msg = gr.Textbox(label="User Message")
    system_prompt = gr.Textbox(
        label="System Prompt",
        value="You are an helpfull assistant that always want to help",
    )
    model_dropdown = gr.Dropdown(
        choices=available_models, label="Select Model", value="llama2:latest"
    )
    clear = gr.ClearButton([msg, chatbot])

    def respond(message, history, system_prompt_text, model_name):
        bot_messages = chat_session(system_prompt_text, history, model_name)
        history[-1][1] = ""
        for bot_message in bot_messages:
            history[-1][1] += bot_message
            yield history

    msg.submit(user, [msg, chatbot], [msg, chatbot], queue=False).then(
        respond, [msg, chatbot, system_prompt, model_dropdown], chatbot
    )

chat_interface.launch()
