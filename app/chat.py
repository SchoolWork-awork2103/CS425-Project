"""Launch locally with `python -m app.chat --device cuda` (or cpu)."""
import argparse
import warnings
from .pipeline import Pipeline


def create_app(pipeline):
    import gradio as gr
    # Gradio 5.50's show_progress has no "spinner without timer" option: "full" is the
    # only value that renders the loading spinner, but it also renders the corner
    # "processing | Xs" runtime display (not configurable from Python). Keep the
    # default "full" and hide that timer text with CSS; the spinner stays.
    with gr.Blocks(title="AABB roast bot", analytics_enabled=False,
                   css=".meta-text { display: none; } footer { display: none !important; }") as demo:
        gr.Markdown("# AABB roast bot\nTell me traits you're proud of, then ask for another roast or change the intensity.")
        state = gr.State(pipeline.manager.initial_state())
        generator = gr.Dropdown(["A", "D"], value=pipeline.system, label="Poem generator")
        # Gradio 5.50 emits this warning even when False is explicitly supplied.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning,
                                    message=r"The default value of 'allow_tags' in gr\.Chatbot will be changed.*")
            chat = gr.Chatbot(type="messages", label="Roast conversation", allow_tags=False)
        message = gr.Textbox(label="Message", placeholder="Roast me, I'm confident and musical")
        with gr.Row():
            send = gr.Button("Send", variant="primary")
            reset = gr.Button("Reset conversation")

        def respond(text, history, session, system):
            reply, session = pipeline.respond(text, session, system)
            return "", [*(history or []), {"role": "user", "content": text}, {"role": "assistant", "content": reply}], session

        for event in (message.submit, send.click):
            event(respond, [message, chat, state, generator], [message, chat, state], concurrency_limit=1,
                  concurrency_id="shared-model")
        reset.click(lambda: ("", [], pipeline.manager.initial_state()), outputs=[message, chat, state],
                    concurrency_limit=1, concurrency_id="shared-model")
    return demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--system", choices=["A", "D"], default="D")
    parser.add_argument("--backend", choices=["qwen", "nlu"], default=None)
    args = parser.parse_args()
    from utils import load_config
    cfg = load_config()
    if args.backend:
        cfg["dialogue"]["backend"] = args.backend
    try:
        pipeline = Pipeline(cfg, args.system, args.device)
    except RuntimeError as exc:
        parser.error(str(exc))
    create_app(pipeline).queue().launch()


if __name__ == "__main__":
    main()
