import streamlit.components.v1 as components


def render_copy_button(text: str, icon_color: str, border_color: str, accent_color: str) -> None:
    escaped = (text.replace("\\", "\\\\")
               .replace("`", "\\`")
               .replace("\n", "\\n")
               .replace("\r", "")
               .replace("</", "<\\/")
               .replace('"', '\\"'))
    components.html(
        f"""
        <button
          onclick="navigator.clipboard.writeText(`{escaped}`).then(() => {{
            this.innerText = 'Copied';
            this.style.borderColor = '{accent_color}';
            this.style.color = '{accent_color}';
            setTimeout(() => {{
              this.innerText = 'Copy to Clipboard';
              this.style.borderColor = '{border_color}';
              this.style.color = '{icon_color}';
            }}, 1600);
          }})"
          style="
            background:transparent;
            border:1px solid {border_color};
            color:{icon_color};
            border-radius:8px;
            padding:6px 14px;
            font-size:12px;
            font-family:Inter,-apple-system,sans-serif;
            cursor:pointer;
            transition:all .2s;
            margin-bottom:8px;
          "
        >
          Copy to Clipboard
        </button>
        """,
        height=44,
    )
