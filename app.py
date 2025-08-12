# # app.py

# import streamlit as st
# from scraper import scrape_website
# from rag_pipeline import prepare_rag_pipeline, retrieve_relevant_chunks
# import google.generativeai as genai
# from dotenv import load_dotenv
# import os

# # Load environment variables
# load_dotenv()
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# # Initialize Gemini model
# model = genai.GenerativeModel("gemini-2.0-flash")
# chat = model.start_chat(history=[])

# # UI Title
# st.set_page_config(page_title="MoreYeahs Chatbot")
# st.title("MoreYeahs Chatbot")

# # Scrape and Prepare Data
# with st.spinner("Scraping and preparing website data..."):
#     site_text = scrape_website()
#     prepare_rag_pipeline(site_text)
# st.success("Knowledge base ready!")

# # User input
# question = st.text_input("Ask a question about MoreYeahs:")
# submit = st.button("Ask")

# if submit and question:
#     # Retrieve relevant chunks from index
#     relevant_chunks = retrieve_relevant_chunks(question)
#     context = "\n---\n".join(relevant_chunks)

#     # Compose prompt for Gemini
#     prompt = f"""
# You are a helpful assistant. Use the information from the company's website below to answer the user's question.

# Company Info:
# {context}

# Question:
# {question}
# """

#     # Ask Gemini and stream response
#     response = chat.send_message(prompt, stream=True)

#     st.subheader("Answer:")
#     for chunk in response:
#         st.write(chunk.text)
# app.py

# import streamlit as st
# from scraper import scrape_website
# from rag_pipeline import prepare_rag_pipeline, retrieve_relevant_chunks
# import google.generativeai as genai
# from dotenv import load_dotenv
# import os

# # -------------------- CONFIG & SETUP --------------------

# # Load environment variables and Gemini API key
# load_dotenv()
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# model = genai.GenerativeModel("gemini-2.0-flash")
# chat = model.start_chat(history=[])

# # Streamlit page setup
# st.set_page_config(page_title="MoreYeahs Chatbot", layout="centered", page_icon="🤖")

# # Custom CSS for styling
# st.markdown("""
#     <style>
#     .main { background-color: #F8F9FA; }
#     .stTextInput>div>div>input {
#         padding: 12px;
#         border-radius: 10px;
#         border: 1px solid #ccc;
#     }
#     .chat-bubble {
#         background-color: #e1f5fe;
#         padding: 12px;
#         border-radius: 12px;
#         margin: 10px 0;
#         font-size: 16px;
#         line-height: 1.6;
#     }
#     </style>
# """, unsafe_allow_html=True)

# # -------------------- HEADER --------------------

# st.markdown("<h1 style='text-align: center;'>🤖 MoreYeahs AI Chatbot</h1>", unsafe_allow_html=True)
# st.markdown("<p style='text-align: center; font-size: 18px;'>Ask about services, careers, ethics, or anything from the company's website.</p>", unsafe_allow_html=True)

# # -------------------- SCRAPE & RAG PIPELINE INIT --------------------

# with st.spinner("🔍 Scraping and preparing the knowledge base..."):
#     site_text = scrape_website()
#     prepare_rag_pipeline(site_text)
# st.success("✅ Knowledge base ready!")

# # -------------------- USER INPUT --------------------

# with st.form(key="query_form", clear_on_submit=True):
#     question = st.text_input("Your Question:", placeholder="e.g. Who is the founder of MoreYeahs?")
#     submit = st.form_submit_button("Ask")

# # -------------------- HANDLE SUBMISSION --------------------

# if submit and question:
#     with st.spinner("🤖 Thinking..."):
#         relevant_chunks = retrieve_relevant_chunks(question)
#         context = "\n---\n".join(relevant_chunks)

#         prompt = f"""
# You are a helpful assistant. Use the information from the company's website below to answer the user's question.

# Company Info:
# {context}

# Question:
# {question}
# """
#         response = chat.send_message(prompt, stream=True)

#     # -------------------- DISPLAY RESPONSE --------------------
#     st.markdown("### 💬 Answer")
#     final_response = ""
#     for chunk in response:
#         final_response += chunk.text
#     st.markdown(f"<div class='chat-bubble'>{final_response}</div>", unsafe_allow_html=True)

    # app.py



import streamlit as st
from scraper import scrape_website
from rag_pipeline import prepare_rag_pipeline, retrieve_relevant_chunks
import google.generativeai as genai
from dotenv import load_dotenv
import os
import time
from datetime import datetime
import re

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Gemini model
model = genai.GenerativeModel("gemini-2.0-flash")

# Page Configuration
st.set_page_config(
    page_title="MoreYeahs AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for modern UI
st.markdown("""
<style>
/* Import Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Global Styles */
* {
    font-family: 'Inter', sans-serif !important;
}

/* Main container styling */
.main {
    padding: 0 !important;
    max-width: none !important;
}

/* Custom header */
.custom-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem 0;
    margin: -1rem -1rem 2rem -1rem;
    border-radius: 0 0 20px 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
}

.header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
    text-align: center;
}

.header-title {
    color: white;
    font-size: 3rem;
    font-weight: 700;
    margin: 0;
    text-shadow: 0 2px 4px rgba(0,0,0,0.3);
}

.header-subtitle {
    color: rgba(255,255,255,0.9);
    font-size: 1.2rem;
    font-weight: 400;
    margin: 0.5rem 0 0 0;
}

/* Chat container */
.chat-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 0 1rem;
}

/* Message styling */
.user-message {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 20px 20px 5px 20px;
    margin: 1rem 0;
    margin-left: 2rem;
    box-shadow: 0 3px 10px rgba(240, 147, 251, 0.3);
    animation: slideInRight 0.3s ease-out;
}

.bot-message {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 20px 20px 20px 5px;
    margin: 1rem 0;
    margin-right: 2rem;
    box-shadow: 0 3px 10px rgba(79, 172, 254, 0.3);
    animation: slideInLeft 0.3s ease-out;
}

.rag-indicator {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    color: white;
    font-size: 0.8rem;
    padding: 0.3rem 0.8rem;
    border-radius: 15px;
    margin-bottom: 0.5rem;
    display: inline-block;
}

.general-indicator {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    font-size: 0.8rem;
    padding: 0.3rem 0.8rem;
    border-radius: 15px;
    margin-bottom: 0.5rem;
    display: inline-block;
}

/* Input styling */
.stTextInput > div > div > input {
    border-radius: 25px !important;
    border: 2px solid #e1e5e9 !important;
    padding: 0.75rem 1.5rem !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
}

.stTextInput > div > div > input:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
}

/* Button styling */
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 25px !important;
    padding: 0.75rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3) !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4) !important;
}

/* Status messages */
.status-success {
    background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
    color: white;
    padding: 1rem;
    border-radius: 15px;
    text-align: center;
    font-weight: 500;
    margin: 1rem 0;
    box-shadow: 0 3px 10px rgba(17, 153, 142, 0.3);
}

.status-loading {
    background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
    color: #8B4513;
    padding: 1rem;
    border-radius: 15px;
    text-align: center;
    font-weight: 500;
    margin: 1rem 0;
}

/* Feature highlight */
.feature-highlight {
    background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
    padding: 1rem;
    border-radius: 15px;
    margin: 1rem 0;
    text-align: center;
    color: #8B1538;
    font-weight: 500;
}

/* Animations */
@keyframes slideInRight {
    from { opacity: 0; transform: translateX(50px); }
    to { opacity: 1; transform: translateX(0); }
}

@keyframes slideInLeft {
    from { opacity: 0; transform: translateX(-50px); }
    to { opacity: 1; transform: translateX(0); }
}

@keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); }
}

/* Hide Streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Responsive design */
@media (max-width: 768px) {
    .header-title { font-size: 2rem; }
    .header-subtitle { font-size: 1rem; }
    .user-message, .bot-message { 
        margin-left: 0.5rem; 
        margin-right: 0.5rem; 
    }
}
</style>
""", unsafe_allow_html=True)

# Function to determine if question is MoreYeahs-related
def is_moreyeahs_related(question):
    """Check if the question is related to MoreYeahs"""
    moreyeahs_keywords = [
        'moreyeahs', 'more yeahs', 'company', 'service', 'services', 'product', 'products',
        'pricing', 'price', 'cost', 'contact', 'support', 'team', 'about us', 'location',
        'office', 'business', 'client', 'customer', 'portfolio', 'work', 'project'
    ]
    
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in moreyeahs_keywords)

# Function to get hybrid response
def get_hybrid_response(question):
    """Get response using hybrid approach - RAG for MoreYeahs, Gemini for general"""
    
    if is_moreyeahs_related(question):
        # Use RAG for MoreYeahs-related questions
        try:
            relevant_chunks = retrieve_relevant_chunks(question)
            if relevant_chunks:
                context = "\n---\n".join(relevant_chunks)
                
                prompt = f"""
You are a helpful AI assistant for MoreYeahs company. Use the information from the company's website below to answer the user's question accurately and professionally.

Company Information:
{context}

User Question: {question}

Instructions:
1. Answer based primarily on the provided company information
2. Be conversational and helpful
3. If the specific information isn't in the context, mention that you can provide general guidance but recommend contacting MoreYeahs directly for specific details
4. Always maintain a professional and friendly tone

Answer:
"""
                
                response = st.session_state.chat_history.send_message(prompt)
                return response.text, "rag"
            else:
                # Fallback to general response if no relevant chunks found
                prompt = f"""
The user is asking about MoreYeahs company: "{question}"

I don't have specific information about MoreYeahs in my knowledge base. Please provide a helpful general response and suggest they contact MoreYeahs directly for specific information about their services, pricing, or other company details.

Be professional and helpful in your response.
"""
                response = st.session_state.general_chat.send_message(prompt)
                return response.text, "general"
        except:
            # Fallback to general response on error
            pass
    
    # Use general Gemini for non-MoreYeahs questions
    try:
        response = st.session_state.general_chat.send_message(question)
        return response.text, "general"
    except Exception as e:
        return f"I apologize, but I encountered an error processing your question: {str(e)}", "error"

# Custom Header
st.markdown("""
<div class="custom-header">
    <div class="header-content">
        <h1 class="header-title">🤖 MoreYeahs AI Assistant</h1>
        <p class="header-subtitle">Your intelligent companion for all inquiries </p>
    </div>
</div>
""", unsafe_allow_html=True)



# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'knowledge_ready' not in st.session_state:
    st.session_state.knowledge_ready = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = model.start_chat(history=[])
if 'general_chat' not in st.session_state:
    st.session_state.general_chat = model.start_chat(history=[])

# Knowledge base preparation
if not st.session_state.knowledge_ready:
    with st.container():
        st.markdown('<div class="status-loading"> Initializing knowledge base...</div>', unsafe_allow_html=True)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Simulate progress updates
            status_text.text("Getting you there...")
            progress_bar.progress(25)
            time.sleep(1)
            
            site_text = scrape_website()
            
            status_text.text("Getting you there...")
            progress_bar.progress(75)
            time.sleep(1)
            
            prepare_rag_pipeline(site_text)
            
            status_text.text("Knowledge base ready!")
            progress_bar.progress(100)
            time.sleep(0.5)
            
            st.session_state.knowledge_ready = True
            
            # Clear loading elements
            progress_bar.empty()
            status_text.empty()
           
            
        except Exception as e:
            st.error(f"❌ Error initializing MoreYeahs knowledge base: {str(e)}")
            st.info("💡 Don't worry! I can still answer general questions ")
            st.session_state.knowledge_ready = True

# Chat Interface
if st.session_state.knowledge_ready:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Display chat history
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f'<div class="user-message">👤 <strong>You:</strong><br>{message["content"]}</div>', unsafe_allow_html=True)
        else:
            # Show indicator based on response type
            indicator_html = ""
            if message.get("type") == "rag":
                indicator_html = '<div class="rag-indicator"></div>'
            elif message.get("type") == "general":
                indicator_html = '<div class="general-indicator"></div>'
            
            st.markdown(f'<div class="bot-message">{indicator_html}🤖 <strong>Assistant:</strong><br>{message["content"]}</div>', unsafe_allow_html=True)
    
    # Input section
    st.markdown("---")
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        question = st.text_input(
            "Ask me about MoreYeahs or any general question...",
            placeholder=" Ask your question",
            key="user_input",
            label_visibility="collapsed"
        )
    
    with col2:
        submit = st.button("Ask", use_container_width=True)
    
    # Process user input
    if submit and question:
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": question})
        
        try:
            # Show thinking indicator
            thinking_placeholder = st.empty()
            if is_moreyeahs_related(question):
                thinking_placeholder.markdown(" Searching ...")
            else:
                thinking_placeholder.markdown(" Thinking ...")
            
            # Get hybrid response
            response_text, response_type = get_hybrid_response(question)
            
            # Clear thinking indicator
            thinking_placeholder.empty()
            
            # Add assistant response to history
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response_text,
                "type": response_type
            })
            
            # Rerun to show new messages
            st.rerun()
            
        except Exception as e:
            st.error(f"❌ Sorry, I encountered an error: {str(e)}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
   

# Sidebar with additional features
with st.sidebar:
    st.markdown("### 🎛️ Chat Controls")
    
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history = model.start_chat(history=[])
        st.session_state.general_chat = model.start_chat(history=[])
        st.rerun()
    
    if st.button("🔄 Refresh MoreYeahs Knowledge", use_container_width=True):
        st.session_state.knowledge_ready = False
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 Chat Statistics")
    
    total_messages = len([m for m in st.session_state.messages if m["role"] == "user"])
    rag_responses = len([m for m in st.session_state.messages if m.get("type") == "rag"])
    general_responses = len([m for m in st.session_state.messages if m.get("type") == "general"])
    
    st.metric("Total Questions", total_messages)
    st.metric("MoreYeahs Queries", rag_responses)
    st.metric("General Queries", general_responses)
    
    st.markdown("---")
    st.markdown("### 🔧 Assistant Modes")
    
    st.markdown("""
    **🎯 Hybrid Mode Active**
    
    **📚 MoreYeahs Mode:** 
    - Company information
    - Services & pricing
    - Contact details
    
    **🧠 General AI Mode:**
    - Any topic questions
    - Explanations
    - General assistance
    """)
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown("""
    **MoreYeahs Hybrid AI Assistant** powered by:
    - 🧠 Google Gemini 2.0 Flash
    - 🔍 RAG for MoreYeahs content
    - 💬 General AI for everything else
    - 🚀 Streamlit Interface
    
    **Capabilities:**
    - ✅ MoreYeahs company questions
    - ✅ General knowledge questions
    - ✅ Explanations & tutorials
    - ✅ Creative assistance
    - ✅ Problem solving
    
    Built with ❤️ for comprehensive assistance.
    """)

# Footer
st.markdown("---")
st.markdown(
    f'<div style="text-align: center; color: #666; padding: 1rem;">© MoreYeahs Hybrid AI Assistant | Powered by Gemini 2.0 Flash | Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>',
    unsafe_allow_html=True
)