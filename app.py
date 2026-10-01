# pyrefly: ignore [missing-import]
import streamlit as st
# pyrefly: ignore [missing-import]
from openai import OpenAI
# pyrefly: ignore [missing-import]
import os
# pyrefly: ignore [missing-import]
import uuid
# pyrefly: ignore [missing-import]
import time
# pyrefly: ignore [missing-import]
from datetime import datetime
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
import base64

# ══════════════════════════════════════════════
# 1. CONFIGURATION
# ══════════════════════════════════════════════
load_dotenv(override=True)
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "poolside/laguna-xs-2.1:free")
AVAILABLE_MODELS_ENV = os.getenv("AVAILABLE_MODELS", "")
if AVAILABLE_MODELS_ENV:
    MODELS_LIST = [m.strip() for m in AVAILABLE_MODELS_ENV.split(",") if m.strip()]
else:
    MODELS_LIST = [MODEL_NAME]

# Models that can't read images. Add any other text-only model IDs here.
TEXT_ONLY_MODELS = {"poolside/laguna-xs-2.1:free"}


def model_label(model_id):
    """Friendly dropdown label, e.g. 'laguna-xs-2.1 (free, text only)'."""
    name = model_id.split("/")[-1].replace(":free", "")
    tags = []
    if model_id.endswith(":free"):
        tags.append("free")
    if model_id in TEXT_ONLY_MODELS:
        tags.append("text only")
    return f"{name} ({', '.join(tags)})" if tags else name


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
            content = msg["content"]
            if isinstance(content, list):
                text = " ".join([p["text"] for p in content if p.get("type") == "text"])
                if not text.strip():
                    text = "Image Upload"
            else:
                text = str(content)

            text = text.strip().replace("\n", " ")
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



def cb_view_doc(text, name, b64_preview=None, mime=None):
    st.session_state.viewing_doc_text = text
    st.session_state.viewing_doc_name = name
    st.session_state.viewing_doc_b64 = b64_preview
    st.session_state.viewing_doc_mime = mime

def cb_close_doc():
    st.session_state.viewing_doc_text = None
    st.session_state.viewing_doc_name = None
    st.session_state.viewing_doc_b64 = None
    st.session_state.viewing_doc_mime = None

def cb_select_model(model_id):
    """Switch the active model and ask the menu to close."""
    st.session_state.selected_model = model_id
    st.session_state.close_model_menu = True


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
    "selected_model": MODEL_NAME if MODEL_NAME in MODELS_LIST else MODELS_LIST[0],
    "close_model_menu": False,
    "viewing_doc_name": None,
    "viewing_doc_text": None,
    "viewing_doc_b64": None,
    "viewing_doc_mime": None,
}
for _key, _val in _defaults.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ══════════════════════════════════════════════
# 5. PAGE CONFIG & LOCAL STORAGE (PERSISTENCE)
# ══════════════════════════════════════════════
st.set_page_config(page_title="ZtifAI", page_icon="icon.svg", layout="centered")

# pyrefly: ignore [missing-import]
import streamlit_javascript as st_js
import json
# pyrefly: ignore [missing-import]
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

    /* ── Model selector (pinned below the chat input) ── */
    [data-testid="stBottomBlockContainer"] { padding-bottom: 4rem !important; }
    
    .st-key-model_bar {
        position: fixed !important;
        bottom: 12px;
        left: 0; right: 0; margin: 0 auto;
        max-width: 46rem !important; /* Exactly match Streamlit centered chat input max-width */
        padding: 0 1rem 0 1.5rem !important; /* Slightly more left padding to align with the + icon */
        z-index: 1000;
        display: flex !important;
        flex-direction: row !important;
        justify-content: flex-start !important;
        align-items: center !important;
        gap: 12px !important;
        pointer-events: none;
    }
    .st-key-model_bar > * { pointer-events: auto; }
    .st-key-model_bar [data-testid="stElementContainer"] { width: auto !important; flex: 0 0 auto !important; }
    
    /* Neon Blue UI pill */
    .st-key-model_bar button {
        background: rgba(8,17,42,0.9) !important;
        color: var(--neon-bright) !important;
        border: 1px solid var(--neon) !important;
        border-radius: 999px !important;
        min-height: 32px !important;
        padding: 4px 16px !important;
        font-size: 0.83rem !important;
        box-shadow: 0 0 12px rgba(26,180,255,0.4) !important;
        transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease !important;
        white-space: nowrap !important;
        width: auto !important;
    }
    .st-key-model_bar button:hover,
    .st-key-model_bar button[aria-expanded="true"] {
        background: rgba(26,180,255,0.15) !important;
        border-color: #fff !important;
        color: #fff !important;
        box-shadow: 0 0 20px rgba(26,180,255,0.8) !important;
    }

    .model-chip {
        font-size: 0.76rem; white-space: nowrap;
        color: #ffc46b !important;
        background: rgba(255,196,107,0.08);
        border: 1px solid rgba(255,196,107,0.28);
        border-radius: 999px; padding: 5px 11px;
    }

    /* Open menu */
    [data-testid="stPopoverBody"] {
        background: #02060f !important;
        border: 1px solid var(--border-strong) !important;
        border-radius: 16px !important;
        padding: 10px !important;
        min-width: 300px;
        box-shadow: 0 -12px 40px rgba(0,0,0,0.7), 0 0 30px rgba(26,180,255,0.20) !important;
    }
    .menu-title { color: var(--text-muted) !important; font-size: 0.78rem; margin: 2px 8px 8px 8px !important; }

    [class*="st-key-mdl_"] button, [class*="st-key-mdlsel_"] button {
        justify-content: flex-start !important;
        background: transparent !important;
        color: var(--text-soft) !important;
        border: 1px solid transparent !important;
        border-radius: 10px !important;
        padding: 9px 12px !important;
        min-height: 0 !important;
        font-size: 0.85rem !important;
        box-shadow: none !important;
    }
    [class*="st-key-mdl_"] button p, [class*="st-key-mdlsel_"] button p { text-align: left !important; }
    [class*="st-key-mdl_"] button:hover {
        background: rgba(26,180,255,0.08) !important;
        color: var(--text) !important;
    }
    [class*="st-key-mdlsel_"] button {
        background: rgba(26,180,255,0.12) !important;
        color: var(--neon-bright) !important;
        border-color: var(--border-strong) !important;
        box-shadow: inset 3px 0 0 var(--neon) !important;
    }

    @media (max-width: 640px) {
        .model-chip { display: none; }
        [data-testid="stPopoverBody"] { min-width: 260px; }
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
    icon_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="1em" height="1em" style="vertical-align: -0.15em;"><defs><linearGradient id="neonGradient" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#8fe6ff" /><stop offset="45%" stop-color="#1ab4ff" /><stop offset="100%" stop-color="#3366ff" /></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="3" result="coloredBlur"/><feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs><path d="M 25 25 L 70 25 L 30 75 L 75 75" fill="none" stroke="url(#neonGradient)" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)"/><path d="M 75 15 Q 82 20 82 27 Q 82 20 89 15 Q 82 15 82 8 Q 82 15 75 15 Z" fill="#8fe6ff" filter="url(#glow)"/><path d="M 15 85 Q 20 88 20 93 Q 20 88 25 85 Q 20 85 20 80 Q 20 85 15 85 Z" fill="#66d9ff" filter="url(#glow)"/></svg>'
    st.markdown(f"## {icon_svg} ZtifAI", unsafe_allow_html=True)
    st.markdown("---")

    st.button(
        ":material/add: New chat",
        on_click=cb_new_chat,
        use_container_width=True,
        key="new_chat",
        disabled=st.session_state.processing,
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
                        disabled=is_current or st.session_state.processing,
                    )
                with col2:
                    st.button(
                        ":material/delete:",
                        key=f"del_{chat_id}",
                        on_click=cb_init_delete,
                        args=(chat_id,),
                        use_container_width=True,
                        help="Delete chat",
                        disabled=st.session_state.processing,
                    )

    st.markdown("---")
    st.markdown(
        '<p class="powered-by">Powered by <span>OpenRouter</span></p>',
        unsafe_allow_html=True,
    )

    # (Model selector moved to main body)

# After picking a model, close the menu (it stays open by default)
if st.session_state.close_model_menu:
    components.html(
        """
        <script>
            const d = window.parent.document;
            ["keydown", "keyup"].forEach(t =>
                d.dispatchEvent(new KeyboardEvent(t, {key: "Escape", code: "Escape", keyCode: 27, which: 27, bubbles: true}))
            );
        </script>
        """,
        height=0,
    )
    st.session_state.close_model_menu = False

# ══════════════════════════════════════════════
# 8. API KEY GUARD
# ══════════════════════════════════════════════
if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
    st.markdown(f'<h1 class="glow-title">{icon_svg} ZtifAI</h1>', unsafe_allow_html=True)
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

if st.session_state.get("viewing_doc_name"):
    chat_layout, doc_layout = st.columns([1.5, 1], gap="large")
else:
    chat_layout = st.container()
    doc_layout = None

with chat_layout:
    # 10. MAIN HEADER + STARTERS (only when chat is empty)
    # ══════════════════════════════════════════════
    header_container = st.empty()
    if not st.session_state.messages and not st.session_state.processing:
        with header_container.container():
            st.markdown(f'<h1 class="glow-title">{icon_svg} ZtifAI</h1>', unsafe_allow_html=True)
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
    else:
        header_container.empty()
    
    # ══════════════════════════════════════════════
    # 11. DISPLAY CHAT MESSAGES
    # ══════════════════════════════════════════════
    for msg_idx, msg in enumerate(st.session_state.messages):
        avatar = "👤" if msg["role"] == "user" else "icon.svg"
        with st.chat_message(msg["role"], avatar=avatar):
            if isinstance(msg["content"], list):
                for p_idx, part in enumerate(msg["content"]):
                    if part.get("type") == "text":
                        if "file_name" in part:
                            st.button(
                                f"📄 View Attached: {part['file_name']}", 
                                key=f"view_{msg_idx}_{p_idx}", 
                                on_click=cb_view_doc, 
                                args=(part["text"], part["file_name"], part.get("base64_preview"), part.get("mime")),
                                disabled=st.session_state.processing
                            )
                        else:
                            st.markdown(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        st.image(part["image_url"]["url"])
            else:
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
    
        with st.chat_message("assistant", avatar="icon.svg"):
            placeholder = st.empty()
            placeholder.markdown("▌")
    
            max_retries = 4
            base_delay = 2
    
            for attempt in range(max_retries + 1):
                try:
                    messages_for_api = [{"role": "system", "content": SYSTEM_INSTRUCTION}]
                    
                    # Clean custom fields before sending to OpenRouter API
                    for m in st.session_state.messages:
                        if isinstance(m["content"], list):
                            clean_content = []
                            for part in m["content"]:
                                if part.get("type") == "text":
                                    clean_content.append({"type": "text", "text": part.get("text")})
                                elif part.get("type") == "image_url":
                                    clean_content.append({"type": "image_url", "image_url": part.get("image_url")})
                            messages_for_api.append({"role": m["role"], "content": clean_content})
                        else:
                            messages_for_api.append({"role": m["role"], "content": m["content"]})
    
                    selected_model = st.session_state.get("selected_model", MODEL_NAME)
                    response = client.chat.completions.create(
                        model=selected_model,
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
                    error_str = str(e).lower()
                    
                    is_exhausted = any(
                        code in error_str for code in ["429", "403", "402", "rate-limited", "out of credits", "token", "balance", "limit"]
                    )
                    is_temp_error = any(
                        code in error_str for code in ["502", "503", "500", "timeout", "connection"]
                    )
                    
                    if is_exhausted:
                        if "exhausted_models" not in st.session_state or isinstance(st.session_state.exhausted_models, set):
                            st.session_state.exhausted_models = {}
                            
                        import re
                        reset_time = None
                        match = re.search(r"'X-RateLimit-Reset': '(\d+)'", error_str, re.IGNORECASE)
                        if match:
                            reset_time = int(match.group(1)) / 1000.0
                            
                        st.session_state.exhausted_models[selected_model] = reset_time
                        
                        next_model = None
                        for m in MODELS_LIST:
                            if m not in st.session_state.exhausted_models:
                                next_model = m
                                break
                                
                        if next_model:
                            st.session_state.selected_model = next_model
                            st.toast(f"Model busy/exhausted. Auto-switching to {model_label(next_model)}...", icon="🔄")
                            st.rerun()
                        else:
                            error_msg = f"⚠️ All available models are currently busy or exhausted. Please try again later."
                            placeholder.markdown(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                            break
                            
                    elif is_temp_error and attempt < max_retries:
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

if doc_layout:
    with doc_layout:
        st.markdown(f"### 📄 {st.session_state.viewing_doc_name}")
        st.button("❌ Close Panel", on_click=cb_close_doc, use_container_width=True, disabled=st.session_state.processing)
        
        if st.session_state.viewing_doc_b64:
            b64 = st.session_state.viewing_doc_b64
            mime = st.session_state.viewing_doc_mime or "application/pdf"
            pdf_html = f'<iframe src="data:{mime};base64,{b64}" width="100%" height="700px" type="{mime}"></iframe>'
            st.markdown(pdf_html, unsafe_allow_html=True)
        else:
            with st.container(height=600):
                st.text(st.session_state.viewing_doc_text)

# 14. MODEL SELECTOR (Pinned below chat input)
# ══════════════════════════════════════════════
current_model = st.session_state.selected_model
with st.container(key="model_bar"):
    with st.popover(
        f":material/bolt: {model_label(current_model)}",
        disabled=st.session_state.processing,
    ):
        st.markdown('<p class="menu-title">Model</p>', unsafe_allow_html=True)
        for i, m in enumerate(MODELS_LIST):
            is_sel = m == current_model
            
            # Check exhaustion status and auto-reset
            is_exhausted = False
            label_suffix = ""
            exhausted_dict = st.session_state.get("exhausted_models", {})
            if isinstance(exhausted_dict, set):
                exhausted_dict = {model: None for model in exhausted_dict}
                st.session_state.exhausted_models = exhausted_dict
                
            if m in exhausted_dict:
                reset_time = exhausted_dict[m]
                if reset_time is not None and time.time() > reset_time:
                    del exhausted_dict[m]
                else:
                    is_exhausted = True
                    if reset_time:
                        mins = max(1, int((reset_time - time.time()) / 60))
                        label_suffix = f" (Resets in {mins}m)"
                    else:
                        label_suffix = " (Out of tokens)"
            
            if is_exhausted:
                label_prefix = ":material/error: "
            else:
                label_prefix = ":material/check: " if is_sel else ""

            st.button(
                label_prefix + model_label(m) + label_suffix,
                key=f"{'mdlsel' if is_sel else 'mdl'}_{i}",
                on_click=cb_select_model,
                args=(m,),
                use_container_width=True,
                disabled=is_exhausted
            )
    if current_model in TEXT_ONLY_MODELS:
        st.markdown('<span class="model-chip">Text only mode</span>', unsafe_allow_html=True)

# 15. CHAT INPUT (disabled while processing)
# ══════════════════════════════════════════════
if prompt := st.chat_input("Message ZtifAI...", disabled=st.session_state.processing, accept_file="multiple"):

    if hasattr(prompt, "text") and hasattr(prompt, "files"):
        text_val = prompt.text
        files_val = prompt.files
    elif isinstance(prompt, dict):
        text_val = prompt.get("text", "")
        files_val = prompt.get("files", [])
    else:
        text_val = prompt
        files_val = []

    # Text-only models can't read images: drop them and say so
    has_images = any(f.type.startswith("image/") for f in files_val)
    if has_images and st.session_state.get("selected_model", MODEL_NAME) in TEXT_ONLY_MODELS:
        st.toast(
            "This model doesn't support images, so they weren't sent. Pick another model to use images.",
            icon=":material/image_not_supported:",
        )
        files_val = []
        if not text_val:
            st.stop()

    content_list = []
    if text_val:
        content_list.append({"type": "text", "text": text_val})

    for f in files_val:
        if f.type.startswith("image/"):
            b64 = base64.b64encode(f.getvalue()).decode("utf-8")
            mime = f.type
            content_list.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"}
            })
        else:
            try:
                text_content = None
                fname = f.name.lower()
                
                if fname.endswith(".pdf"):
                    # pyrefly: ignore [missing-import]
                    from pypdf import PdfReader
                    pdf = PdfReader(f)
                    text_content = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
                
                elif fname.endswith(".docx"):
                    # pyrefly: ignore [missing-import]
                    from docx import Document
                    doc = Document(f)
                    text_content = "\n".join(para.text for para in doc.paragraphs)
                
                else:
                    text_content = f.getvalue().decode("utf-8")
                
                if text_content is not None:
                    content_list.append({
                        "type": "text",
                        "text": f"\n\n--- Contents of {f.name} ---\n{text_content}\n--- End of {f.name} ---\n",
                        "file_name": f.name,
                        "base64_preview": base64.b64encode(f.getvalue()).decode("utf-8") if fname.endswith(".pdf") else None,
                        "mime": f.type
                    })
            except Exception as e:
                st.toast(f"Could not read {f.name}. Make sure it's a valid text, PDF, Word doc, or image.", icon="⚠️")

    final_content = content_list if files_val else text_val

    st.session_state.messages.append({"role": "user", "content": final_content})
    st.session_state.processing = True
    st.session_state.pending_prompt = final_content if final_content else "image"
    save_current_chat()
    st.rerun()