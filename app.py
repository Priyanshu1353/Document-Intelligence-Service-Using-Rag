import streamlit as st
import os
import json
import asyncio
import tempfile
from database import DocumentDB
from agent import run_chat, run_extraction

st.set_page_config(
    page_title="Document Intelligence",
    page_icon="📄",
    layout="wide"
)

# Initialize DB as a cached resource so it only loads once
@st.cache_resource
def get_db():
    return DocumentDB(dimension=384)

db = get_db()

st.title("📄 Document Intelligence Service")
st.markdown("---")

# Sidebar: Document Ingestion
with st.sidebar:
    st.header("Upload Document")
    uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

    if uploaded_file is not None:
        if st.button("🚀 Ingest Document"):
            with st.spinner("Ingesting... (this may take a moment)"):
                try:
                    # Save uploaded file to a temp file for processing
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name

                    result = asyncio.run(db.ingest_pdf(tmp_path, uploaded_file.name))
                    os.remove(tmp_path)

                    st.success(f"✅ Ingested! ({result['chunks_count']} chunks)")
                    st.session_state["file_id"] = result["file_id"]
                    st.session_state["filename"] = uploaded_file.name
                except Exception as e:
                    st.error(f"Ingestion failed: {str(e)}")

    if "file_id" in st.session_state:
        st.info(f"Currently analyzing: **{st.session_state['filename']}**")

# Main Content: Tabs
tab1, tab2 = st.tabs(["💬 Chat (RAG)", "⚡ Action Center"])

with tab1:
    st.subheader("Chat with your Document")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question about the document..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    relevant_chunks = asyncio.run(db.query_db(prompt, n_results=5))
                    context = "\n\n".join([r["content"] for r in relevant_chunks])
                    sources = list(set([r["metadata"]["filename"] for r in relevant_chunks]))

                    if not context:
                        answer = "I have no knowledge about this yet. Please ingest some documents first."
                        sources = []
                    else:
                        answer = asyncio.run(run_chat(prompt, context))

                    full_response = answer
                    if sources:
                        full_response += f"\n\n**Sources:** {', '.join(sources)}"

                    st.markdown(full_response)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"Chat failed: {str(e)}")

with tab2:
    st.subheader("Extracted Actionable Items")

    if "file_id" not in st.session_state:
        st.warning("Please ingest a document first to see actions.")
    else:
        if st.button("🔍 Extract Actions"):
            with st.spinner("Extracting..."):
                try:
                    full_text = db.get_all_text_for_file(st.session_state["file_id"])
                    if not full_text:
                        st.error("No content found for this file.")
                    else:
                        actions = asyncio.run(run_extraction(full_text))
                        if not actions:
                            st.info("No actionable items found in this document.")
                        else:
                            actions_dict = [a.model_dump() for a in actions]
                            st.table(actions_dict)
                            st.download_button(
                                label="Download Actions as JSON",
                                data=json.dumps(actions_dict, indent=2),
                                file_name=f"actions_{st.session_state['file_id']}.json",
                                mime="application/json"
                            )
                except Exception as e:
                    st.error(f"Extraction failed: {str(e)}")



