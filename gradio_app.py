import gradio as gr
import random
import time

css = """
#mainchatcol {
    margin-left: 10%;
    margin-right: 10%;
    margin-top: 20px;
}

#configcol {
    margin-top: 70px
}

"""



with gr.Blocks(theme=gr.themes.Base(), css = css) as demo:
    with gr.Row():

        # define an expandable column of size 25%
        with gr.Column(scale = 1, elem_id = "configcol"):
            with gr.Column(variant="panel"):
                gr.Markdown("### Configuration")
                gr.Dropdown(["Monarch Assistant (GPT-4)", "Monarch Assistant"], 
                            value = "Monarch Assistant (GPT-4)", 
                            interactive = True, 
                            label = "Assistant")
                gr.Button("Clear current chat")
                box = gr.Checkbox(label = "🛠️ Show calls to external tools")


            with gr.Column(variant = "panel"):
                gr.Textbox("", label = "Set Custom API Key", elem_classes=["noborder"], type = "password",
                           info = "If you have a custom API key, you can enter it here to use it instead of the default key.")

        with gr.Column(scale = 5, elem_id = "mainchatcol",):
            gr.Markdown("# Monarch Assistant (GPT-4)")
            chatbot = gr.Chatbot(
                                 value = [(None, "I am bot?"), (None, "I am alive?")],
                                 container = False,
                                 bubble_full_width = True,
                                 avatar_images = ("X", "https://avatars.githubusercontent.com/u/5161984?s=200&v=4"))
            msg = gr.Textbox()

            def respond(message, chat_history):
                bot_message = random.choice(["Hello", "Hi there", "Howdy"])
                chat_history.append((message, bot_message))
                chat_history.append(("Yes, U R bot", None))
                chat_history.append(("No, U R not alive (yetsss)", None))
                return "", chat_history
            
            msg.submit(respond, [msg, chatbot], [msg, chatbot])


# Launch the interface
demo.queue().launch()
