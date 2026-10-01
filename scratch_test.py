# pyrefly: ignore [missing-import]
import streamlit as st
st.set_page_config(layout="centered")
with st.sidebar:
    st.write("Sidebar")
with st.bottom:
    st.write("This is in st.bottom")
st.chat_input("Chat input")
