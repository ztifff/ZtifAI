import streamlit as st
from openai import OpenAI
import os
import json
import uuid
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ══════════════════════════════════════════════
# 1. CONFIGURATION
# ══════════════════════════════════════════════
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") # Default or set in .env
# We are using a single model from .env now
MODEL_NAME = os.getenv("MODEL_NAME", "poolside/poolside-model-id-here")

# ══════════════════════════════════════════════
# 2. CONVERSATION MANAGEMENT
# ══════════════════════════════════════════════
def load_all_conversations():
    """Load all saved conversations from the current session, sorted newest first."""
    if "all_conversations" not in st.session_state:
        st.session_state.all_conversations = {}
    return dict(
        sorted(st.session_state.all_conversations.items(), key=lambda x: x[1].get("timestamp", ""), reverse=True)
    )


def save_conversation(chat_id, title, messages):
    """Save a conversation to the current session state."""
    if "all_conversations" not in st.session_state:
        st.session_state.all_conversations = {}
    
    st.session_state.all_conversations[chat_id] = {
        "id": chat_id,
        "title": title,
        "messages": messages,
        "timestamp": datetime.now().isoformat(),
    }


def delete_conversation(chat_id):
    """Delete a conversation from the session state."""
    if "all_conversations" in st.session_state and chat_id in st.session_state.all_conversations:
        del st.session_state.all_conversations[chat_id]


def auto_title(messages):
    """Generate a conversation title from the first user message."""
    for msg in messages:
        if msg["role"] == "user":
            text = msg["content"].strip().replace("\n", " ")
            return text[:40] + ("..." if len(text) > 40 else "")
    return "New Chat"


def save_current_chat():
    """Save the current conversation if it has messages."""
    if st.session_state.messages:
        save_conversation(
            st.session_state.current_chat_id,
            auto_title(st.session_state.messages),
            st.session_state.messages,
        )


# ══════════════════════════════════════════════
# 3. CALLBACKS (run before script re-executes)
# ══════════════════════════════════════════════
def cb_stop_generating():
    """Callback: stop the AI generation and save partial response."""
    st.session_state.processing = False
    partial = st.session_state.partial_response
    if partial:
        st.session_state.messages.append(
            {"role": "assistant", "content": partial + "\n\n*(generation stopped)*"}
        )
        save_current_chat()
    st.session_state.partial_response = ""
    st.session_state.pending_prompt = None


def cb_new_chat():
    """Callback: save current chat, then start a fresh one."""
    save_current_chat()
    st.session_state.messages = []
    st.session_state.current_chat_id = str(uuid.uuid4())
    st.session_state.processing = False
    st.session_state.partial_response = ""
    st.session_state.pending_prompt = None


def cb_load_chat(chat_id):
    """Callback: save current chat, then load a different one."""
    save_current_chat()
    conversations = load_all_conversations()
    if chat_id in conversations:
        st.session_state.messages = conversations[chat_id]["messages"]
        st.session_state.current_chat_id = chat_id
    st.session_state.processing = False
    st.session_state.partial_response = ""
    st.session_state.pending_prompt = None


def cb_delete_chat(chat_id):
    """Callback: delete a conversation."""
    delete_conversation(chat_id)
    if chat_id == st.session_state.current_chat_id:
        st.session_state.messages = []
        st.session_state.current_chat_id = str(uuid.uuid4())
    st.session_state.confirm_delete_id = None

def cb_init_delete(chat_id):
    st.session_state.confirm_delete_id = chat_id

def cb_cancel_delete():
    st.session_state.confirm_delete_id = None


# ══════════════════════════════════════════════
# 4. SESSION STATE DEFAULTS
# ══════════════════════════════════════════════
_defaults = {
    "all_conversations": {},
    "messages": [],
    "current_chat_id": str(uuid.uuid4()),
    "processing": False,
    "partial_response": "",
    "pending_prompt": None,
    "confirm_delete_id": None,
}
for _key, _val in _defaults.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ══════════════════════════════════════════════
# 5. PAGE CONFIG
# ══════════════════════════════════════════════
st.set_page_config(page_title="ZtifAI", page_icon="⚡", layout="centered")

# ══════════════════════════════════════════════
# 6. CSS — Pitch Black + Neon Glow Theme
# ══════════════════════════════════════════════
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg-primary: #000000;
        --bg-card: #0d0d0d;
        --bg-input: #111111;
        --glow-cyan: #00f0ff;
        --glow-purple: #a855f7;
        --glow-pink: #f472b6;
        --text-primary: #e4e4e7;
        --text-secondary: #a1a1aa;
        --text-muted: #52525b;
        --border: #1a1a1a;
    }

    .stApp { background-color: var(--bg-primary) !important; font-family: 'Inter', sans-serif !important; }
    #MainMenu, footer, .stDeployButton { display: none !important; }
    header[data-testid="stHeader"] {
        background-color: rgba(0,0,0,0.85) !important;
        backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--border);
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background-color: var(--bg-primary) !important;
        border-right: 1px solid var(--border) !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: var(--glow-cyan) !important;
        text-shadow: 0 0 7px rgba(0,240,255,0.4), 0 0 20px rgba(0,240,255,0.2);
        font-weight: 700 !important; letter-spacing: 1px;
    }
    section[data-testid="stSidebar"] hr { border-color: var(--border) !important; opacity: 0.5; }

    /* ── Sidebar new-chat button ── */
    section[data-testid="stSidebar"] .new-chat-btn button {
        width: 100% !important;
        background: linear-gradient(135deg, rgba(0,240,255,0.08), rgba(168,85,247,0.08)) !important;
        color: var(--glow-cyan) !important;
        border: 1px solid rgba(0,240,255,0.2) !important;
        border-radius: 10px !important; padding: 10px 20px !important;
        font-weight: 500 !important; letter-spacing: 0.5px;
        transition: all 0.3s ease !important;
    }
    section[data-testid="stSidebar"] .new-chat-btn button:hover {
        background: linear-gradient(135deg, rgba(0,240,255,0.18), rgba(168,85,247,0.18)) !important;
        border-color: var(--glow-cyan) !important;
        box-shadow: 0 0 15px rgba(0,240,255,0.2), 0 0 30px rgba(0,240,255,0.1) !important;
    }

    /* ── Sidebar conversation buttons ── */
    section[data-testid="stSidebar"] .conv-btn button {
        width: 100% !important;
        background: transparent !important;
        color: var(--text-secondary) !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        padding: 8px 12px !important;
        font-size: 0.82rem !important;
        text-align: left !important;
        transition: all 0.2s ease !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    section[data-testid="stSidebar"] .conv-btn button:hover {
        background: rgba(0,240,255,0.05) !important;
        border-color: rgba(0,240,255,0.15) !important;
        color: var(--text-primary) !important;
    }
    section[data-testid="stSidebar"] .conv-btn-active button {
        background: rgba(0,240,255,0.08) !important;
        border-color: rgba(0,240,255,0.2) !important;
        color: var(--glow-cyan) !important;
    }
    section[data-testid="stSidebar"] .del-btn button {
        background: transparent !important;
        color: var(--text-muted) !important;
        border: none !important;
        padding: 4px !important;
        font-size: 0.7rem !important;
        min-height: 0 !important;
        height: auto !important;
    }
    section[data-testid="stSidebar"] .del-btn button:hover {
        color: #ef4444 !important;
    }

    /* ── Text ── */
    h1, h2, h3, p, span, li, label, div { color: var(--text-primary) !important; }

    /* ── Glow title ── */
    .glow-title {
        font-size: 2.8rem !important; font-weight: 800 !important;
        background: linear-gradient(135deg, var(--glow-cyan), var(--glow-purple), var(--glow-pink));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        filter: drop-shadow(0 0 20px rgba(0,240,255,0.3));
        letter-spacing: -0.5px; margin-bottom: 0 !important;
        animation: titlePulse 3s ease-in-out infinite;
    }
    @keyframes titlePulse {
        0%, 100% { filter: drop-shadow(0 0 20px rgba(0,240,255,0.3)); }
        50% { filter: drop-shadow(0 0 35px rgba(0,240,255,0.5)); }
    }
    .subtitle {
        color: var(--text-muted) !important; font-size: 0.9rem !important;
        font-weight: 300 !important; letter-spacing: 2px; text-transform: uppercase; margin-top: 0 !important;
    }

    /* ── Chat messages ── */
    .stChatMessage {
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important; padding: 16px 20px !important;
        margin-bottom: 12px !important; transition: all 0.3s ease;
    }
    .stChatMessage:hover {
        border-color: rgba(0,240,255,0.15) !important;
        box-shadow: 0 0 20px rgba(0,240,255,0.05) !important;
    }
    .stChatMessage p, .stChatMessage span, .stChatMessage li {
        color: var(--text-primary) !important; font-size: 0.95rem !important; line-height: 1.7 !important;
    }
    .stChatMessage code {
        background-color: #1a1a2e !important; color: var(--glow-cyan) !important;
        padding: 2px 6px !important; border-radius: 4px !important;
        font-family: 'JetBrains Mono', monospace !important; font-size: 0.85rem !important;
    }
    .stChatMessage pre {
        background-color: #0a0a1a !important; border: 1px solid var(--border) !important;
        border-radius: 10px !important; padding: 16px !important;
    }

    /* ── Chat input ── */
    .stChatInput > div {
        background-color: var(--bg-input) !important;
        border: 1px solid var(--border) !important;
        border-radius: 28px !important; transition: all 0.3s ease !important;
    }
    .stChatInput > div:focus-within {
        border-color: rgba(0,240,255,0.4) !important;
        box-shadow: 0 0 15px rgba(0,240,255,0.1), 0 0 30px rgba(0,240,255,0.05),
                    inset 0 0 15px rgba(0,240,255,0.03) !important;
    }
    .stChatInput textarea {
        color: var(--text-primary) !important; font-family: 'Inter', sans-serif !important;
        caret-color: var(--glow-cyan) !important;
    }
    .stChatInput textarea::placeholder { color: var(--text-muted) !important; }
    .stChatInput button { color: var(--glow-cyan) !important; transition: all 0.3s ease !important; }
    .stChatInput button:hover { filter: drop-shadow(0 0 8px rgba(0,240,255,0.5)) !important; }

    /* ── Disabled input ── */
    .stChatInput textarea:disabled { opacity: 0.3 !important; }

    /* ── Stop button ── */
    .stop-btn button {
        background: rgba(239, 68, 68, 0.1) !important;
        color: #ef4444 !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        border-radius: 20px !important;
        padding: 6px 24px !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }
    .stop-btn button:hover {
        background: rgba(239, 68, 68, 0.2) !important;
        border-color: #ef4444 !important;
        box-shadow: 0 0 15px rgba(239, 68, 68, 0.2) !important;
    }

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: var(--glow-cyan) !important; }
    .stSpinner p { color: var(--glow-cyan) !important; text-shadow: 0 0 10px rgba(0,240,255,0.3); }

    /* ── API warning ── */
    .api-warning {
        background: linear-gradient(135deg, rgba(168,85,247,0.1), rgba(244,114,182,0.1));
        border: 1px solid rgba(168,85,247,0.3); padding: 24px; border-radius: 16px;
        text-align: center; margin: 30px 0; box-shadow: 0 0 30px rgba(168,85,247,0.1);
    }
    .api-warning p { color: #e4e4e7 !important; margin: 4px 0; }
    .api-warning strong { color: var(--glow-purple) !important; text-shadow: 0 0 10px rgba(168,85,247,0.4); }
    .api-warning code { color: var(--glow-cyan) !important; background: rgba(0,240,255,0.08); padding: 2px 8px; border-radius: 4px; }
    .api-warning a { color: var(--glow-cyan) !important; text-decoration: underline; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-primary); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0,240,255,0.3); }

    /* ── Ambient glow ── */
    .ambient-glow {
        position: fixed; top: -200px; left: 50%; transform: translateX(-50%);
        width: 600px; height: 400px;
        background: radial-gradient(ellipse, rgba(0,240,255,0.06) 0%, transparent 70%);
        pointer-events: none; z-index: 0;
        animation: ambientBreathe 5s ease-in-out infinite;
    }
    @keyframes ambientBreathe {
        0%, 100% { opacity: 0.5; transform: translateX(-50%) scale(1); }
        50% { opacity: 1; transform: translateX(-50%) scale(1.1); }
    }

    .powered-by { color: var(--text-muted) !important; font-size: 0.7rem !important; letter-spacing: 1px; text-transform: uppercase; }
    .powered-by span { color: var(--glow-cyan) !important; text-shadow: 0 0 6px rgba(0,240,255,0.3); }
    .section-label { color: var(--text-muted) !important; font-size: 0.7rem !important; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }

    /* ── Model selector dropdown ── */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        background-color: #0d0d0d !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
    }
    section[data-testid="stSidebar"] .stSelectbox > div > div:hover {
        border-color: rgba(0,240,255,0.3) !important;
    }
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] span {
        color: var(--glow-cyan) !important;
        font-size: 0.8rem !important;
    }
    /* ── Mobile Responsiveness ── */
    @media (max-width: 768px) {
        .stChatMessage { padding: 12px 14px !important; }
        .glow-title { font-size: 2rem !important; }
        
        /* Force Streamlit sidebar columns to not stack vertically */
        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 4px !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
            width: 70% !important;
            flex: 1 1 70% !important;
            min-width: 0 !important;
        }
        section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
            width: 30% !important;
            flex: 1 1 30% !important;
            min-width: 0 !important;
        }
        
        section[data-testid="stSidebar"] .conv-btn button,
        section[data-testid="stSidebar"] .conv-btn-active button {
            font-size: 0.9rem !important;
            padding: 10px !important;
        }
        section[data-testid="stSidebar"] .del-btn button {
            font-size: 1.1rem !important;
            padding: 10px !important;
        }
    }
    </style>
    <div class="ambient-glow"></div>
    """,
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════
# 7. SIDEBAR
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚡ ZtifAI")
    st.markdown("---")

    # New Chat button
    with st.container():
        st.markdown('<div class="new-chat-btn">', unsafe_allow_html=True)
        st.button("✦  New Chat", on_click=cb_new_chat, use_container_width=True, key="new_chat")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Conversation history
    conversations = load_all_conversations()
    if conversations:
        st.markdown('<p class="section-label">Recent Chats</p>', unsafe_allow_html=True)
        for chat_id, conv in conversations.items():
            is_current = chat_id == st.session_state.current_chat_id
            css_class = "conv-btn-active" if is_current else "conv-btn"

            if st.session_state.confirm_delete_id == chat_id:
                # Show confirmation UI
                st.markdown(f"<div style='color: #ef4444; font-size: 0.8rem; margin-bottom: 4px;'>Delete {conv['title'][:15]}...?</div>", unsafe_allow_html=True)
                col_y, col_n = st.columns(2)
                with col_y:
                    st.button("✓ Yes", key=f"yes_{chat_id}", on_click=cb_delete_chat, args=(chat_id,), use_container_width=True)
                with col_n:
                    st.button("✗ No", key=f"no_{chat_id}", on_click=cb_cancel_delete, use_container_width=True)
                st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
            else:
                # Changed from [6, 1] to [5, 2] so the delete button isn't squished on small screens
                col1, col2 = st.columns([5, 2])
                with col1:
                    st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
                    st.button(
                        f"💬 {conv['title']}",
                        key=f"load_{chat_id}",
                        on_click=cb_load_chat,
                        args=(chat_id,),
                        use_container_width=True,
                        disabled=is_current,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown('<div class="del-btn">', unsafe_allow_html=True)
                    st.button(
                        "🗑",
                        key=f"del_{chat_id}",
                        on_click=cb_init_delete,
                        args=(chat_id,),
                        use_container_width=True,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        '<p class="powered-by">Powered by <span>OpenRouter</span></p>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════
# 8. API KEY GUARD
# ══════════════════════════════════════════════
if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
    st.markdown('<h1 class="glow-title">⚡ ZtifAI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Your personal AI assistant</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="api-warning">
            <p><strong>⚠️ API Key not configured</strong></p>
            <p>Open the <code>.env</code> file and paste your Opencode (or OpenAI) API key.</p>
            <p><small><code>OPENAI_API_KEY=oc_sk_...</code></small></p>
            <p><small>Optionally add <code>OPENAI_BASE_URL</code> and <code>MODEL_NAME</code>.</small></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ══════════════════════════════════════════════
# 9. CONFIGURE OPENAI CLIENT
# ══════════════════════════════════════════════
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL if BASE_URL else None,
    default_headers={
        "HTTP-Referer": "http://localhost:8509",
        "X-Title": "ZtifAI",
    }
)

SYSTEM_INSTRUCTION = (
    "You are ZtifAI, a helpful, friendly, and concise AI assistant created by Fitz. "
    "You answer questions clearly and accurately. When you don't know something, "
    "you say so honestly. You can use markdown formatting in your responses."
)


# ══════════════════════════════════════════════
# 10. MAIN HEADER (only when chat is empty)
# ══════════════════════════════════════════════
if not st.session_state.messages and not st.session_state.processing:
    st.markdown('<h1 class="glow-title">⚡ ZtifAI</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Your personal AI assistant</p>', unsafe_allow_html=True
    )

# ══════════════════════════════════════════════
# 11. DISPLAY CHAT MESSAGES
# ══════════════════════════════════════════════
for msg in st.session_state.messages:
    avatar = "👤" if msg["role"] == "user" else "⚡"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# ══════════════════════════════════════════════
# 12. STOP BUTTON (visible only while processing)
# ══════════════════════════════════════════════
if st.session_state.processing:
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        st.markdown('<div class="stop-btn">', unsafe_allow_html=True)
        st.button(
            "⏹ Stop generating",
            on_click=cb_stop_generating,
            use_container_width=True,
            key="stop_btn",
        )
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# 13. AI RESPONSE GENERATION (streaming)
# ══════════════════════════════════════════════
if st.session_state.processing and st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt

    with st.chat_message("assistant", avatar="⚡"):
        placeholder = st.empty()
        placeholder.markdown("▌")

        max_retries = 4
        base_delay = 2

        for attempt in range(max_retries + 1):
            try:
                # Build history: system prompt + previous messages + new prompt
                messages_for_api = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
                messages_for_api.extend(st.session_state.messages)

                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages_for_api,
                    stream=True
                )

                full_response = ""
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        st.session_state.partial_response = full_response
                        placeholder.markdown(full_response + "▌")

                placeholder.markdown(full_response)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )
                break  # Success! Exit the retry loop.

            except Exception as e:
                error_str = str(e)
                # Retry silently on rate limits (429), BYOK provider errors (403), or bad gateway (502/503)
                is_retriable = any(code in error_str for code in ["429", "403", "502", "503", "rate-limited"])
                
                if is_retriable and attempt < max_retries:
                    # Exponential backoff: 2s, 4s, 8s, 16s...
                    time.sleep(base_delay * (2 ** attempt))
                    placeholder.markdown("▌")  # Reset to just the thinking cursor
                    continue
                else:
                    error_msg = f"⚠️ Something went wrong: `{e}`"
                    placeholder.markdown(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    break

    # Done processing
    st.session_state.processing = False
    st.session_state.pending_prompt = None
    st.session_state.partial_response = ""
    save_current_chat()
    st.rerun()

# ══════════════════════════════════════════════
# 14. CHAT INPUT (disabled while processing)
# ══════════════════════════════════════════════
if prompt := st.chat_input(
    "Message ZtifAI...", disabled=st.session_state.processing
):
    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Save to session & trigger processing
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.processing = True
    st.session_state.pending_prompt = prompt
    save_current_chat()  # Save so it appears in sidebar immediately
    st.rerun()
