with open('app.py', 'r', encoding='utf-8') as f: lines = f.readlines()

new_lines = []
in_chat_block = False

cb_code = '''
def cb_view_doc(text, name):
    st.session_state.viewing_doc_text = text
    st.session_state.viewing_doc_name = name

def cb_close_doc():
    st.session_state.viewing_doc_text = None
    st.session_state.viewing_doc_name = None
'''

for i, line in enumerate(lines):
    if 'def cb_select_model(model_id):' in line:
        new_lines.append(cb_code + '\n')
        new_lines.append(line)
        continue
    elif '"close_model_menu": False,' in line:
        new_lines.append(line)
        new_lines.append('    "viewing_doc_name": None,\n')
        new_lines.append('    "viewing_doc_text": None,\n')
        continue
    
    if '# 10. MAIN HEADER + STARTERS' in line:
        new_lines.append('''
if st.session_state.get("viewing_doc_name"):
    chat_layout, doc_layout = st.columns([1.5, 1], gap="large")
else:
    chat_layout = st.container()
    doc_layout = None

with chat_layout:
''')
        in_chat_block = True
        
    if '# 14. CHAT INPUT' in line:
        in_chat_block = False
        new_lines.append('''
if doc_layout:
    with doc_layout:
        st.markdown(f"### 📄 {st.session_state.viewing_doc_name}")
        st.button("❌ Close Panel", on_click=cb_close_doc, use_container_width=True)
        with st.container(height=600):
            st.text(st.session_state.viewing_doc_text)

''')

    if in_chat_block:
        if 'for msg in st.session_state.messages:' in line:
            new_lines.append('    for msg_idx, msg in enumerate(st.session_state.messages):\n')
            continue
        elif 'for part in msg["content"]:' in line:
            new_lines.append('            for p_idx, part in enumerate(msg["content"]):\n')
            continue
        elif 'with st.expander(f"📄 Attached: {part[\'file_name\']}"):' in line:
            new_lines.append('                        st.button(f"📄 View Attached: {part[\'file_name\']}", key=f"view_{msg_idx}_{p_idx}", on_click=cb_view_doc, args=(part["text"], part["file_name"]))\n')
            continue
        elif 'st.text(part["text"])' in line:
            continue
        
        new_lines.append('    ' + line)
    else:
        new_lines.append(line)

with open('app2.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
