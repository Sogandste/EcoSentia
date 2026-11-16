
import streamlit as st

GUIDE_STEPS = [
    {
        "title": "Welcome to EcoSentia",
        "description": "Discover how EcoSentia helps you analyze translation risks.",
        "gif": "step1.gif",
    },
    {
        "title": "Enter Your Prompt",
        "description": "Enter your text and configure the analysis settings.",
        "gif": "step2-3-4.gif",
    },
]


def onboarding(state: st.session_state):

    if "guide_step" not in state:
        state.guide_step = 0

    step = state.guide_step
    total_steps = len(GUIDE_STEPS)

    current = GUIDE_STEPS[step]

    st.progress((step + 1) / total_steps)

    st.markdown(
        f"<h2>{current['title']}</h2>",
        unsafe_allow_html=True
    )

    st.write(current["description"])

    st.image(current["gif"], width='stretch')

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if step > 0:
            if st.button("← Previous"):
                state.guide_step -= 1
                st.rerun()

    with col2:
        if st.button("Skip Guide"):
            state.guide_completed = True
            st.rerun()

    with col3:
        if step < total_steps - 1:
            if st.button("Next →"):
                state.guide_step += 1
                st.rerun()
        else:
            if st.button("Get Started"):
                state.guide_completed = True
                st.rerun()
