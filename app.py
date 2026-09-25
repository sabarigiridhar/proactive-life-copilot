import streamlit as st
from graph import app_brain

# Configure the Streamlit page
st.set_page_config(page_title="Life Copilot", page_icon="🤖")
st.title("🤖 Autonomous Life Copilot")
st.caption("Track your Wealth, Health, and Learning seamlessly.")

# Initialize the chat history and the AI's daily memory in Streamlit session state
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! What did you learn, eat, or spend today?"}]
    
if "daily_state" not in st.session_state:
    # This matches the DailyState in graph.py
    st.session_state.daily_state = {
        "user_message": "",
        "health": None,
        "wealth": None,
        "learning": None,
        "ai_response": ""
    }

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Wait for the user to type a message
if prompt := st.chat_input("Log your day (e.g., 'Spent ₹500 on lunch and read about RAG')..."):
    
    # 1. Display user message in the chat UI
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. Update the AI's memory with the new message
    st.session_state.daily_state["user_message"] = prompt

    # 3. Process the input through your LangGraph AI Brain
    with st.spinner("Processing your log..."):
        # We invoke the graph we built in graph.py!
        new_state = app_brain.invoke(st.session_state.daily_state)
        
        # 4. Save the updated state (what the AI learned/extracted) back to the session
        st.session_state.daily_state = new_state
        
        # 5. Get the AI's routing response (Follow-up or Confirmation)
        ai_response = new_state.get("ai_response", "Data processed.")

        # 6. Display the assistant's response
        with st.chat_message("assistant"):
            st.markdown(ai_response)
        
        st.session_state.messages.append({"role": "assistant", "content": ai_response})