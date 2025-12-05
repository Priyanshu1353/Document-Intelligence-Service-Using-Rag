import streamlit as st
import requests
import os
import json
from datetime import datetime

# Configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Document Intelligence",
    page_icon="📄",
    layout="wide"
)

st.title("📄 Document Intelligence Service")
st.markdown("---")

# Sidebar: Document Ingestion
with st.sidebar:
    st.header("Upload Document")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")
    
    if uploaded_file is not None:
        if st.button("🚀 Ingest Document"):
            with st.spinner("Ingesting..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                try:
                    response = requests.post(f"{API_URL}/v1/ingest", files=files)
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"Ingested! File ID: {data['file_id']}")
                        st.session_state["file_id"] = data["file_id"]
                        st.session_state["filename"] = uploaded_file.name
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Connection failed: {str(e)}")

    if "file_id" in st.session_state:
        st.info(f"Currently analyzing: **{st.session_state['filename']}**")

# Main Content: Tabs
tab1, tab2 = st.tabs(["💬 Chat (RAG)", "⚡ Action Center"])

with tab1:
    st.subheader("Chat with your Document")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask a question about the document..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = requests.post(
                        f"{API_URL}/v1/chat",
                        json={"query": prompt}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        answer = data["answer"]
                        sources = data.get("sources", [])
                        
                        full_response = answer
                        if sources:
                            full_response += f"\n\n**Sources:** {', '.join(sources)}"
                        
                        st.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Connection failed: {str(e)}")

with tab2:
    st.subheader("Extracted Actionable Items")
    
    if "file_id" not in st.session_state:
        st.warning("Please ingest a document first to see actions.")
    else:
        if st.button("🔍 Extract Actions"):
            with st.spinner("Extracting..."):
                try:
                    response = requests.get(f"{API_URL}/v1/extract-actions/{st.session_state['file_id']}")
                    if response.status_code == 200:
                        data = response.json()
                        actions = data["actions"]
                        
                        if not actions:
                            st.info("No actionable items found in this document.")
                        else:
                            # Display as a table
                            st.table(actions)
                            
                            # Optional: Download as JSON
                            st.download_button(
                                label="Download Actions as JSON",
                                data=json.dumps(actions, indent=2),
                                file_name=f"actions_{st.session_state['file_id']}.json",
                                mime="application/json"
                            )
                    else:
                        st.error(f"Error: {response.text}")
                except Exception as e:
                    st.error(f"Connection failed: {str(e)}")


