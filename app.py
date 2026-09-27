import streamlit as st
import os
from PIL import Image
from groq import Groq
import google.generativeai as genai
from graph import app_brain

st.set_page_config(page_title="Life Copilot", page_icon="🤖")
st.title("🤖 Autonomous Life Copilot")
st.caption("Track your Wealth, Health, and Learning.")

# Initialize API clients
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ==========================================
# 1. SESSION STATE MANAGEMENT
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! Log your day via text, voice, or photo."}]
if "daily_state" not in st.session_state:
    st.session_state.daily_state = {"user_message": "", "intent": "log", "health": None, "wealth": None, "learning": None, "ai_response": ""}

if "widget_key" not in st.session_state:
    st.session_state.widget_key = 0

current_text_key = f"text_area_{st.session_state.widget_key}"
if current_text_key not in st.session_state:
    st.session_state[current_text_key] = ""

# ==========================================
# 2. CREATE PERMANENT ZONES (The Layout Fix)
# ==========================================
# This locks the chat history to the top and inputs to the bottom
chat_container = st.container()
st.write("") 
input_container = st.container()

# Render existing chat history in the top zone
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# ==========================================
# 3. INPUT AREA (Locked to the bottom zone)
# ==========================================
with input_container:
    col1, col2 = st.columns(2)
    with col1:
        audio_value = st.audio_input("Record Voice", label_visibility="collapsed", key=f"audio_{st.session_state.widget_key}")
    with col2:
        uploaded_image = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"], label_visibility="collapsed", key=f"image_{st.session_state.widget_key}")

    # Process Audio
    if audio_value and "audio_processed" not in st.session_state:
        with st.spinner("Transcribing..."):
            with open("temp_audio.wav", "wb") as f: f.write(audio_value.read())
            with open("temp_audio.wav", "rb") as file:
                transcription = groq_client.audio.transcriptions.create(
                    file=("temp_audio.wav", file.read()), model="whisper-large-v3"
                )
            st.session_state[current_text_key] += f" {transcription.text} "
            st.session_state.audio_processed = True
            os.remove("temp_audio.wav")
            st.rerun() 

    # Process Image
    if uploaded_image and "image_processed" not in st.session_state:
        with st.spinner("Analyzing..."):
            img = Image.open(uploaded_image)
            vision_model = genai.GenerativeModel("gemini-3.6-flash") 
            vision_response = vision_model.generate_content(
                ["Extract only the key data (e.g., calories, items, total amount, merchant) from this image in 1-2 short sentences.", img]
            )
            st.session_state[current_text_key] += f" {vision_response.text.strip()} "
            st.session_state.image_processed = True
            st.rerun() 

    # Text Area & Button
    current_text = st.text_area("Log your day", 
                                height=68, 
                                label_visibility="collapsed",
                                placeholder="Type your log, or upload media to extract text here...",
                                key=current_text_key)

    if st.button("Send Log 🚀", use_container_width=True, type="primary"):
        if current_text.strip():
            
            # Save the user's message to memory first
            st.session_state.messages.append({"role": "user", "content": current_text})
            st.session_state.daily_state["user_message"] = current_text

            # THE FIX: Tell Streamlit to draw the loading UI inside the TOP chat zone!
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(current_text)

                with st.spinner("Processing your log..."):
                    try:
                        new_state = app_brain.invoke(st.session_state.daily_state)
                        st.session_state.daily_state = new_state
                        ai_response = new_state.get("ai_response", "Data processed.")
                    except Exception as e:
                        ai_response = f"An error occurred: {e}"

                    with st.chat_message("assistant"):
                        st.markdown(ai_response)
                    
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
            
            # Reset everything for the next message
            st.session_state.widget_key += 1 
            if "audio_processed" in st.session_state: del st.session_state["audio_processed"]
            if "image_processed" in st.session_state: del st.session_state["image_processed"]
            
            st.rerun()