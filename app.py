import streamlit as st
from openai import OpenAI
import os
import uuid
import time
from datetime import datetime
from dotenv import load_dotenv

# ══════════════════════════════════════════════
# 1. CONFIGURATION
# ══════════════════════════════════════════════
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "poolside/poolside-model-id-here")

# Starter prompts shown on an empty chat: (button label, prompt sent)
STARTERS = [
    (":material/lightbulb: Brainstorm ideas", "Help me brainstorm ideas for a weekend project."),
    (":material/code: Debug some code", "Help me debug some code. I'll paste it in my next message."),
    (":material/school: Explain a concept", "Explain a complicated concept to me in simple terms."),
    (":material/edit_note: Draft a message", "Help me draft a short, friendly message."),
]

# ══════════════════════════════════════════════
# 2. CONVERSATION MANAGEMENT
# ══════════════════════════════════════════════
def load_all_conversations():
    """Load all saved conversations from the current session, newest first."""
    if "all_conversations" not in st.session_state:
        st.session_state.all_conversations = {}
    return dict(
        sorted(
            st.session_state.all_conversations.items(),
            key=lambda x: x[1].get("timestamp", ""),
            reverse=True,
        )
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
    trigger_save()


def delete_conversation(chat_id):
    """Delete a conversation from the session state."""
    if "all_conversations" in st.session_state and chat_id in st.session_state.all_conversations:
        del st.session_state.all_conversations[chat_id]
        trigger_save()


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
    """Stop the AI generation and save the partial response."""
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
    """Save the current chat, then start a fresh one."""
    save_current_chat()
    st.session_state.messages = []
    st.session_state.current_chat_id = str(uuid.uuid4())
    st.session_state.processing = False
    st.session_state.partial_response = ""
    st.session_state.pending_prompt = None


def cb_load_chat(chat_id):
    """Save the current chat, then load a different one."""
    save_current_chat()
    conversations = load_all_conversations()
    if chat_id in conversations:
        st.session_state.messages = conversations[chat_id]["messages"]
        st.session_state.current_chat_id = chat_id
    st.session_state.processing = False
    st.session_state.partial_response = ""
    st.session_state.pending_prompt = None


def cb_delete_chat(chat_id):
    """Delete a conversation."""
    delete_conversation(chat_id)
    if chat_id == st.session_state.current_chat_id:
        st.session_state.messages = []
        st.session_state.current_chat_id = str(uuid.uuid4())
    st.session_state.confirm_delete_id = None


def cb_init_delete(chat_id):
    st.session_state.confirm_delete_id = chat_id


def cb_cancel_delete():
    st.session_state.confirm_delete_id = None


def cb_starter(text):
    """Send a starter prompt as the first message of a chat."""
    st.session_state.messages.append({"role": "user", "content": text})
    st.session_state.processing = True
    st.session_state.pending_prompt = text
    save_current_chat()


# ══════════════════════════════════════════════
# 4. SESSION STATE DEFAULTS
# ══════════════════════════════════════════════
_defaults = {
    "messages": [],
    "current_chat_id": str(uuid.uuid4()),
    "processing": False,
    "partial_response": "",
    "pending_prompt": None,
    "confirm_delete_id": None,
    "needs_save": False,
}
for _key, _val in _defaults.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ══════════════════════════════════════════════
# 5. PAGE CONFIG & LOCAL STORAGE (PERSISTENCE)
# ══════════════════════════════════════════════
st.set_page_config(page_title="ZtifAI", page_icon="⚡", layout="centered")

import streamlit_javascript as st_js
import json
import streamlit.components.v1 as components

# Fetch from local storage. Returns 0 on the first render, triggering a rerun when JS returns the string.
chats_json = st_js.st_javascript("localStorage.getItem('ztifai_chats') || '{}';")
if chats_json == 0:
    st.stop()  # Wait for the frontend to return the data

if "storage_loaded" not in st.session_state:
    try:
        st.session_state.all_conversations = json.loads(chats_json)
    except:
        st.session_state.all_conversations = {}
    st.session_state.storage_loaded = True

def trigger_save():
    st.session_state.needs_save = True

# Process any pending saves to local storage
if st.session_state.get("needs_save", False):
    data_str = json.dumps(st.session_state.all_conversations)
    data_str = data_str.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')
    js = f"""
    <script>
        try {{
            window.parent.localStorage.setItem('ztifai_chats', '{data_str}');
        }} catch (e) {{
            console.error("Failed to save to localStorage:", e);
        }}
    </script>
    """
    components.html(js, height=0)
    st.session_state.needs_save = False

# ══════════════════════════════════════════════
# 6. CSS: Deep navy + neon blue
# ══════════════════════════════════════════════
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --bg: #01030b;
        --surface: #050a17;
        --surface-2: #08112a;
        --neon: #1ab4ff;
        --neon-bright: #66d9ff;
        --electric: #3366ff;
        --text: #dce8ff;
        --text-soft: #93a7cf;
        --text-muted: #5a6d96;
        --border: rgba(26, 180, 255, 0.14);
        --border-strong: rgba(26, 180, 255, 0.40);
        --danger: #ff5c7a;
    }

    /* ── Base ── */
    .stApp {
        background:
            radial-gradient(ellipse 70% 40% at 50% -10%, rgba(26,180,255,0.14), transparent 70%),
            radial-gradient(ellipse 50% 30% at 100% 100%, rgba(51,102,255,0.10), transparent 70%),
            var(--bg) !important;
        font-family: 'DM Sans', sans-serif !important;
    }
    #MainMenu, footer,
    [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], .stDeployButton { display: none !important; }
    header[data-testid="stHeader"] { background: transparent !important; }

    .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h4, label { color: var(--text) !important; }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #030816 0%, var(--bg) 100%) !important;
        border-right: 1px solid var(--border) !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        font-family: 'Sora', sans-serif !important;
        color: var(--neon-bright) !important;
        text-shadow: 0 0 8px rgba(26,180,255,0.65), 0 0 24px rgba(26,180,255,0.35);
        font-weight: 700 !important;
        letter-spacing: 0.5px;
    }
    section[data-testid="stSidebar"] hr { border-color: var(--border) !important; opacity: 1; }

    /* Make button text follow the button color (beats the global p rule) */
    [class*="st-key-"] button p { color: inherit !important; }

    /* ── New chat button ── */
    .st-key-new_chat button {
        background: linear-gradient(135deg, rgba(26,180,255,0.16), rgba(51,102,255,0.16)) !important;
        color: var(--neon-bright) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 12px !important;
        padding: 10px 16px !important;
        font-weight: 600 !important;
        transition: box-shadow 0.2s ease, border-color 0.2s ease !important;
    }
    .st-key-new_chat button:hover {
        border-color: var(--neon) !important;
        box-shadow: 0 0 18px rgba(26,180,255,0.35), inset 0 0 12px rgba(26,180,255,0.10) !important;
    }

    /* ── Sidebar chat rows ── */
    section[data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        width: 100% !important;
        gap: 0.4rem !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stColumn"],
    section[data-testid="stSidebar"] div[data-testid="column"] {
        min-width: 0 !important;
        flex: 1 1 0 !important;
        width: auto !important;
    }
    /* The column holding the delete button is a fixed 44px */
    section[data-testid="stSidebar"] div[data-testid="stColumn"]:has([class*="st-key-del_"]),
    section[data-testid="stSidebar"] div[data-testid="column"]:has([class*="st-key-del_"]) {
        flex: 0 0 44px !important;
        width: 44px !important;
    }

    /* Chat title buttons: truncate instead of widening the sidebar */
    section[data-testid="stSidebar"] button div p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        max-width: 100% !important;
    }
    [class*="st-key-load_"] button {
        background: transparent !important;
        color: var(--text-soft) !important;
        border: 1px solid transparent !important;
        border-radius: 10px !important;
        padding: 8px 12px !important;
        font-size: 0.85rem !important;
        justify-content: flex-start !important;
        transition: background 0.2s ease, border-color 0.2s ease !important;
    }
    [class*="st-key-load_"] button p { text-align: left !important; }
    [class*="st-key-load_"] button:hover:not(:disabled) {
        background: rgba(26,180,255,0.07) !important;
        border-color: var(--border) !important;
        color: var(--text) !important;
    }
    /* The open chat is the disabled one, so style :disabled as "active" */
    [class*="st-key-load_"] button:disabled {
        opacity: 1 !important;
        background: rgba(26,180,255,0.10) !important;
        border-color: var(--border-strong) !important;
        color: var(--neon-bright) !important;
        box-shadow: inset 3px 0 0 var(--neon);
    }

    /* Delete + confirm buttons */
    [class*="st-key-del_"] button {
        background: transparent !important;
        border: 1px solid transparent !important;
        color: var(--text-muted) !important;
        padding: 8px 0 !important;
        min-height: 0 !important;
        border-radius: 10px !important;
    }
    [class*="st-key-del_"] button:hover {
        color: var(--danger) !important;
        border-color: rgba(255,92,122,0.35) !important;
        background: rgba(255,92,122,0.07) !important;
    }
    [class*="st-key-yes_"] button, [class*="st-key-no_"] button {
        background: transparent !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }
    [class*="st-key-yes_"] button {
        color: var(--danger) !important;
        border: 1px solid rgba(255,92,122,0.4) !important;
    }
    [class*="st-key-yes_"] button:hover { background: rgba(255,92,122,0.12) !important; }
    [class*="st-key-no_"] button {
        color: var(--text-soft) !important;
        border: 1px solid var(--border) !important;
    }
    [class*="st-key-no_"] button:hover { border-color: var(--border-strong) !important; }

    /* ── Hero ── */
    .glow-title {
        font-family: 'Sora', sans-serif !important;
        font-size: 3.2rem !important; font-weight: 800 !important;
        letter-spacing: -1px; margin: 3rem 0 0 0 !important; padding: 0 !important;
        text-align: center;
        background: linear-gradient(120deg, #8fe6ff 0%, var(--neon) 45%, var(--electric) 100%);
        -webkit-background-clip: text; background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 18px rgba(26,180,255,0.45));
        animation: titlePulse 4s ease-in-out infinite;
    }
    @keyframes titlePulse {
        0%, 100% { filter: drop-shadow(0 0 16px rgba(26,180,255,0.35)); }
        50%      { filter: drop-shadow(0 0 30px rgba(26,180,255,0.65)); }
    }
    .subtitle {
        color: var(--text-soft) !important; text-align: center;
        font-size: 1rem !important; margin: 0.4rem 0 2.2rem 0 !important;
    }

    /* Starter prompt buttons */
    [class*="st-key-sug_"] button {
        background: var(--surface) !important;
        color: var(--text-soft) !important;
        border: 1px solid var(--border) !important;
        border-radius: 14px !important;
        padding: 16px 18px !important;
        justify-content: flex-start !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease !important;
    }
    [class*="st-key-sug_"] button:hover {
        color: var(--neon-bright) !important;
        border-color: var(--border-strong) !important;
        box-shadow: 0 0 20px rgba(26,180,255,0.18) !important;
    }

    /* ── Chat messages ── */
    [data-testid="stChatMessage"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 16px !important;
        padding: 16px 20px !important;
        margin-bottom: 12px !important;
    }
    /* Your messages get a brighter edge */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]),
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: var(--surface-2) !important;
        border-color: var(--border-strong) !important;
        box-shadow: inset 3px 0 0 var(--neon);
    }
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] li {
        color: var(--text) !important; font-size: 0.97rem !important; line-height: 1.7 !important;
    }
    [data-testid="stChatMessage"] code {
        background: rgba(26,180,255,0.10) !important; color: var(--neon-bright) !important;
        padding: 2px 6px !important; border-radius: 5px !important;
        font-family: 'JetBrains Mono', monospace !important; font-size: 0.85rem !important;
    }
    [data-testid="stChatMessage"] pre {
        background: #020612 !important; border: 1px solid var(--border) !important;
        border-radius: 12px !important; padding: 16px !important;
    }
    [data-testid="stChatMessage"] pre code { background: transparent !important; padding: 0 !important; }

    /* ── Chat input ── */
    [data-testid="stBottom"], [data-testid="stBottom"] > div {
        background: transparent !important;
    }
    [data-testid="stBottom"] {
        background: linear-gradient(to top, var(--bg) 55%, transparent) !important;
    }
    .stChatInput > div, [data-testid="stChatInput"] > div {
        background: var(--surface) !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 28px !important;
        box-shadow: 0 0 14px rgba(26,180,255,0.12) !important;
        transition: box-shadow 0.25s ease, border-color 0.25s ease !important;
    }
    .stChatInput > div:focus-within, [data-testid="stChatInput"] > div:focus-within {
        border-color: var(--neon) !important;
        box-shadow: 0 0 22px rgba(26,180,255,0.35), 0 0 48px rgba(26,180,255,0.15),
                    inset 0 0 14px rgba(26,180,255,0.06) !important;
    }
    .stChatInput textarea, [data-testid="stChatInput"] textarea {
        color: var(--text) !important; font-family: 'DM Sans', sans-serif !important;
        caret-color: var(--neon) !important; background: transparent !important;
    }
    .stChatInput textarea::placeholder { color: var(--text-muted) !important; }
    .stChatInput textarea:disabled { opacity: 0.35 !important; }
    .stChatInput button, [data-testid="stChatInputSubmitButton"] {
        background: linear-gradient(135deg, var(--neon), var(--electric)) !important;
        color: #01030b !important; border-radius: 50% !important;
    }
    .stChatInput button:hover { box-shadow: 0 0 14px rgba(26,180,255,0.7) !important; }

    /* ── Stop button ── */
    .st-key-stop_btn button {
        background: rgba(255,92,122,0.08) !important;
        color: var(--danger) !important;
        border: 1px solid rgba(255,92,122,0.35) !important;
        border-radius: 20px !important;
        font-size: 0.85rem !important; font-weight: 500 !important;
        transition: box-shadow 0.2s ease, background 0.2s ease !important;
    }
    .st-key-stop_btn button:hover {
        background: rgba(255,92,122,0.16) !important;
        box-shadow: 0 0 16px rgba(255,92,122,0.25) !important;
    }

    /* ── Misc ── */
    .stSpinner > div { border-top-color: var(--neon) !important; }
    .section-label {
        color: var(--text-muted) !important; font-size: 0.8rem !important;
        font-weight: 500; margin-bottom: 6px;
    }
    .powered-by { color: var(--text-muted) !important; font-size: 0.78rem !important; }
    .powered-by span { color: var(--neon) !important; text-shadow: 0 0 8px rgba(26,180,255,0.45); }

    .api-warning {
        background: linear-gradient(135deg, rgba(26,180,255,0.08), rgba(51,102,255,0.08));
        border: 1px solid var(--border-strong); padding: 24px; border-radius: 16px;
        text-align: center; margin: 30px 0; box-shadow: 0 0 30px rgba(26,180,255,0.10);
    }
    .api-warning p { color: var(--text) !important; margin: 4px 0; }
    .api-warning strong { color: var(--neon-bright) !important; }
    .api-warning code { color: var(--neon-bright) !important; background: rgba(26,180,255,0.10); padding: 2px 8px; border-radius: 5px; }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: #11203f; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(26,180,255,0.5); }

    /* Keyboard focus ring for buttons/links only (the chat input uses its own glow) */
button:focus-visible, a:focus-visible {
    outline: 2px solid var(--neon) !important;
    outline-offset: 2px;
}

/* Remove the inner box/outline inside the chat input pill */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] textarea:focus,
[data-testid="stChatInput"] textarea:focus-visible,
[data-testid="stChatInput"] div[data-baseweb="textarea"],
[data-testid="stChatInput"] div[data-baseweb="base-input"] {
    outline: none !important;
    box-shadow: none !important;
    border: none !important;
    background: transparent !important;
}
    @media (prefers-reduced-motion: reduce) {
        .glow-title { animation: none !important; }
    }

    /* ── Mobile ── */
    @media (max-width: 768px) {
        .glow-title { font-size: 2.2rem !important; margin-top: 1.5rem !important; }
        [data-testid="stChatMessage"] { padding: 12px 14px !important; }
        section[data-testid="stSidebar"] [class*="st-key-load_"] button { font-size: 0.9rem !important; padding: 10px !important; }
        section[data-testid="stSidebar"] [class*="st-key-del_"] button { font-size: 1.1rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ══════════════════════════════════════════════
# 7. SIDEBAR
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚡ ZtifAI")
    st.markdown("---")

    st.button(
        ":material/add: New chat",
        on_click=cb_new_chat,
        use_container_width=True,
        key="new_chat",
    )

    st.markdown("---")

    conversations = load_all_conversations()
    if conversations:
        st.markdown('<p class="section-label">Recent chats</p>', unsafe_allow_html=True)
        for chat_id, conv in conversations.items():
            is_current = chat_id == st.session_state.current_chat_id

            if st.session_state.confirm_delete_id == chat_id:
                col_y, col_n = st.columns(2)
                with col_y:
                    st.button(
                        ":material/check:",
                        key=f"yes_{chat_id}",
                        on_click=cb_delete_chat,
                        args=(chat_id,),
                        use_container_width=True,
                        help="Confirm delete",
                    )
                with col_n:
                    st.button(
                        ":material/close:",
                        key=f"no_{chat_id}",
                        on_click=cb_cancel_delete,
                        use_container_width=True,
                        help="Cancel",
                    )
            else:
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.button(
                        conv["title"],
                        key=f"load_{chat_id}",
                        on_click=cb_load_chat,
                        args=(chat_id,),
                        use_container_width=True,
                        disabled=is_current,
                    )
                with col2:
                    st.button(
                        ":material/delete:",
                        key=f"del_{chat_id}",
                        on_click=cb_init_delete,
                        args=(chat_id,),
                        use_container_width=True,
                        help="Delete chat",
                    )

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
            <p><strong>⚠️ API key not configured</strong></p>
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
    },
)

SYSTEM_INSTRUCTION = (
    "You are ZtifAI, a helpful, friendly, and concise AI assistant created by Fitz. "
    "You answer questions clearly and accurately. When you don't know something, "
    "you say so honestly. You can use markdown formatting in your responses."
)

# ══════════════════════════════════════════════
# 10. MAIN HEADER + STARTERS (only when chat is empty)
# ══════════════════════════════════════════════
if not st.session_state.messages and not st.session_state.processing:
    st.markdown('<h1 class="glow-title">⚡ ZtifAI</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Ask anything, or start with one of these.</p>',
        unsafe_allow_html=True,
    )
    for row in range(0, len(STARTERS), 2):
        cols = st.columns(2)
        for col, idx in zip(cols, (row, row + 1)):
            if idx < len(STARTERS):
                label, text = STARTERS[idx]
                with col:
                    st.button(
                        label,
                        key=f"sug_{idx}",
                        on_click=cb_starter,
                        args=(text,),
                        use_container_width=True,
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
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.button(
            ":material/stop_circle: Stop generating",
            on_click=cb_stop_generating,
            use_container_width=True,
            key="stop_btn",
        )

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
                messages_for_api = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
                messages_for_api.extend(st.session_state.messages)

                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages_for_api,
                    stream=True,
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
                break

            except Exception as e:
                error_str = str(e)
                is_retriable = any(
                    code in error_str for code in ["429", "403", "502", "503", "rate-limited"]
                )

                if is_retriable and attempt < max_retries:
                    time.sleep(base_delay * (2 ** attempt))
                    placeholder.markdown("▌")
                    continue
                else:
                    error_msg = f"⚠️ Something went wrong: `{e}`"
                    placeholder.markdown(error_msg)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_msg}
                    )
                    break

    st.session_state.processing = False
    st.session_state.pending_prompt = None
    st.session_state.partial_response = ""
    save_current_chat()
    st.rerun()

# ══════════════════════════════════════════════
# 14. CHAT INPUT (disabled while processing)
# ══════════════════════════════════════════════
if prompt := st.chat_input("Message ZtifAI...", disabled=st.session_state.processing):
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.processing = True
    st.session_state.pending_prompt = prompt
    save_current_chat()
    st.rerun()