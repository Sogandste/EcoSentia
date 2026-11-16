import streamlit as st
from typing import Dict, Any
from UI.Model.Theme import ThemeDict
from .notebox import render_note_box
from .supportbar import render_support_bar_html
from ..render import html_safe
from ..converter import coerce_bias_list
from .copyButton import render_copy_button


def render_prompt_results(prompts: Dict[str, Any], theme: ThemeDict) -> None:
    level = str(prompts.get("support_level", "none")).lower()
    evidence_note = str(prompts.get("evidence_note", ""))

    render_note_box(f"Support: {level.title()}", evidence_note)

    st.markdown(
        render_support_bar_html(level, theme["text"], theme["border"], theme["accent"]),
        unsafe_allow_html=True,
    )

    biases = coerce_bias_list(prompts.get("detected_biases"))
    if biases:
        st.markdown("#### Detected Translation Risk Patterns")
        for bias in biases:
            name = bias.get("bias", "") if isinstance(bias, dict) else str(bias)
            explanation = bias.get("explanation", "") if isinstance(bias, dict) else ""
            st.markdown(
                f"""
                <div class="risk-panel">
                    <span class="risk-title">{html_safe(name)}</span>
                    {html_safe(explanation)}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        render_note_box("Risk Review", "No translation risk patterns detected.")

    st.markdown("#### Evaluation Prompts")

    prompt_meta = [
        ("Master Prompt", "master_prompt", True, "Primary evaluation prompt for direct LLM use."),
        ("Counter Prompt", "counter_prompt", False, "Challenges the validity of the design claim."),
        ("Uncertainty Mapping", "uncertainty_prompt", False, "Maps uncertainty and evidence gaps."),
        ("Redesign Prompt", "redesign_prompt", False, "Suggests evidence-grounded redesign directions."),
    ]

    for title, key, expanded, description in prompt_meta:
        with st.expander(title, expanded=expanded):
            st.caption(description)
            value = str(prompts.get(key, "") or "")
            if value:
                render_copy_button(value, theme["accent"], theme["border"], theme["accent"])
                st.code(value, language="text")
    look_for = prompts.get("look_for") if isinstance(prompts.get("look_for"), list) else []
    if look_for:
        checklist_items = "".join(f"<li>{html_safe(item)}</li>" for item in look_for)
        st.markdown(
            f"""
            <div class="checklist-box">
              <div class="checklist-title">Checklist for AI Response</div>
              <ul>{checklist_items}</ul>
            </div>
            """,
            unsafe_allow_html=True,
        )