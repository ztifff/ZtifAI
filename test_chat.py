# pyrefly: ignore [missing-import]
import streamlit as st

res = st.chat_input("test", accept_file="multiple")
st.write(type(res))
if res:
    st.write(res)
    st.write(dir(res))
