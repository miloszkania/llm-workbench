from typing import Callable

import streamlit as st


def system_prompt_label(system_prompt: str | None) -> str:
    system_prompt_length = len(system_prompt or "")
    status = f"{system_prompt_length} chars" if system_prompt_length else "empty"
    return f"System prompt ({status})"


def system_prompt_input(
        key: str,
        value: str | None = None,
        on_change: Callable[[], None] | None = None,
        height: int | str | None = None,
) -> str:
    # collapsed by default, but the label shows whether a system prompt will be sent
    current_value = st.session_state.get(key, value)

    with st.expander(system_prompt_label(current_value), key=f"{key}_expander"):
        return st.text_area(
            "System prompt",
            value=value,
            key=key,
            on_change=on_change,
            height=height,
            label_visibility="collapsed",
        )


def system_prompt_view(system_prompt: str | None, key: str, parse_markdown: bool = True) -> None:
    if not system_prompt:
        return

    with st.expander(system_prompt_label(system_prompt), key=f"{key}_expander"):
        if parse_markdown:
            st.markdown(system_prompt)
        else:
            st.text_area(
                "System prompt",
                value=system_prompt,
                height="content",
                key=key,
                label_visibility="collapsed",
            )
