import os
import json
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
import google.generativeai as genai
from dotenv import load_dotenv
import db_utils
from Constants import MODAL
from datetime import date

from schemas import HealthLog, WealthLog, LearningLog 

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# ==========================================
# 1. DEFINE THE STATE
# ==========================================
class DailyState(TypedDict):
    user_message: str
    intent: str # NEW: Tracks if this is a "log" or a "query"
    health: Optional[HealthLog]
    wealth: Optional[WealthLog]
    learning: Optional[LearningLog]
    ai_response: str

# ==========================================
# 2. DEFINE THE NODES
# ==========================================
def classify_intent_node(state: DailyState):
    """Determines if the user wants to log data or ask a question."""
    prompt = f"""
    Analyze this user message: "{state['user_message']}"
    Is the user trying to record/log new information (e.g., eating, spending, learning)?
    Or are they asking a question about past data (e.g., "How much did I spend?", "What did I learn?")?
    Respond with ONLY one word: "log" or "query".
    """
    model = genai.GenerativeModel(MODAL)
    response = model.generate_content(prompt)
    intent = response.text.strip().lower()
    
    # Fallback just in case
    if intent not in ["log", "query"]:
        intent = "log"
        
    return {"intent": intent}

def answer_query_node(state: DailyState):
    """Handles RAG by generating SQL or searching Vector DB."""
    model = genai.GenerativeModel(MODAL)
    
    # 1. Decide which database to use
    router_prompt = f"""
    The user asked: "{state['user_message']}"
    If this is about spending (wealth) or health (sleep, workout, calories), write a SQLite query for the tables:
    - wealth_logs(id, date, transaction_type, amount, currency, category, merchant, notes)
    - health_logs(id, date, sleep_hours, workout_type, calories_consumed, notes)
    Return ONLY the raw SQL SELECT statement. No markdown, no explanation.
    
    If it is about learning, topics, or concepts, return exactly the word "VECTOR" followed by the search topic.
    """
    
    decision = model.generate_content(router_prompt).text.strip()
    decision = decision.replace("```sql", "").replace("```", "").strip() # Clean up markdown
    
    # 2. Execute the query
    if decision.startswith("SELECT"):
        raw_results = db_utils.query_sqlite(decision)
        final_prompt = f"The user asked: '{state['user_message']}'. The database returned: {raw_results}. Answer the user naturally in 1-2 sentences."
    else:
        search_term = decision.replace("VECTOR", "").strip()
        raw_results = db_utils.search_learning_vectors(search_term)
        final_prompt = f"The user asked: '{state['user_message']}'. My second brain notes say: {raw_results}. Answer the user naturally."
        
    # 3. Generate final conversational answer
    answer = model.generate_content(final_prompt).text
    return {"ai_response": answer}

def extract_data_node(state: DailyState):
    """Uses Gemini to extract structured data for logging."""
    user_message = state.get("user_message", "")
    
    prompt = f"""
    You are an AI data extractor. Read the user's message: "{user_message}"
    Extract the information into a strict JSON format with exactly three keys: "health", "wealth", and "learning".
    If a category is NOT mentioned, set its value to null.
    
    CRITICAL RULE: The value for each key MUST be a single dictionary object, NEVER a list or array. 
    If the user mentions multiple expenses (e.g. hotel and food), add the amounts together and combine them into one single representative object.
    
    For "health": "sleep_hours" (float), "workout_type" (string), "calories_consumed" (int), "notes" (string).
    For "wealth": "transaction_type" (string), "amount" (float), "currency" (string), "category" (string), "merchant" (string), "notes" (string).
    For "learning": "topic" (string), "duration_minutes" (int), "summary_text" (string), "url_reference" (string).
    
    Return ONLY a valid JSON object.
    """
    
    model = genai.GenerativeModel("gemini-2.5-flash") # Ensure this matches your working model
    response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
    
    try:
        extracted_data = json.loads(response.text)
        
        # DEFENSIVE CATCH: If the AI ignores the rule and returns a list, grab the first item
        for key in ["health", "wealth", "learning"]:
            if isinstance(extracted_data.get(key), list):
                extracted_data[key] = extracted_data[key][0] if len(extracted_data[key]) > 0 else None

        if extracted_data.get("health"): state["health"] = extracted_data["health"]
        if extracted_data.get("wealth"): state["wealth"] = extracted_data["wealth"]
        if extracted_data.get("learning"): state["learning"] = extracted_data["learning"]
    except Exception as e:
        print(f"Extraction Error: {e}")
        
    return state

def followup_node(state: DailyState):
    """Generates a proactive question if any pillar is missing."""
    missing = []
    if not state.get("health"): missing.append("Health")
    if not state.get("wealth"): missing.append("Wealth")
    if not state.get("learning"): missing.append("Learning")
    
    prompt = f"The user logged data, but is missing logs for: {', '.join(missing)}. Ask a friendly, short follow-up question to get this missing info."
    model = genai.GenerativeModel(MODAL)
    return {"ai_response": model.generate_content(prompt).text}

def save_and_confirm_node(state: DailyState):
    """Saves ALL extracted data to the databases securely."""
    today = str(date.today())
    
    # 1. Save Wealth
    if state.get("wealth"):
        w = state["wealth"]
        # Using `or` ensures that if a value is explicitly `None` (null), we use the fallback
        db_utils.insert_wealth_log(
            today, 
            w.get("transaction_type") or "Expense", 
            w.get("amount") or 0.0, 
            w.get("currency") or "INR", 
            w.get("category") or "General", 
            w.get("merchant") or "Unknown", 
            str(w.get("notes") or "")
        )
        
    # 2. Save Health
    if state.get("health"):
        h = state["health"]
        db_utils.insert_health_log(
            today, 
            h.get("sleep_hours") or 0.0, 
            h.get("workout_type") or "None", 
            h.get("calories_consumed") or 0, 
            str(h.get("notes") or "")
        )
        
    # 3. Save Learning (Only if a topic actually exists!)
    if state.get("learning"):
        l = state["learning"]
        topic = l.get("topic")
        
        # We only interact with ChromaDB if the AI actually extracted a real topic
        if topic: 
            safe_topic = str(topic)
            safe_summary = str(l.get("summary_text") or l.get("notes") or "No summary")
            safe_url = str(l.get("url_reference") or "None")
            
            db_utils.insert_learning_log(today, safe_topic, l.get("duration_minutes") or 0, safe_url)
            db_utils.add_learning_vector(db_utils.init_chroma_db(), today, safe_topic, safe_summary, safe_url)

    return {"ai_response": "Data processed and successfully saved to SQLite & ChromaDB! 🚀"}
# ==========================================
# 3. DEFINE THE ROUTERS 
# ==========================================
def route_intent(state: DailyState):
    """Routes the graph based on whether it's a log or a query."""
    if state.get("intent") == "query":
        return "answer_query"
    return "extract_data"

def check_completeness(state: DailyState):
    """Checks if all three pillars are filled."""
    if state.get("health") and state.get("wealth") and state.get("learning"):
        return "save_and_confirm"
    return "ask_followup"

# ==========================================
# 4. BUILD THE GRAPH 
# ==========================================
workflow = StateGraph(DailyState)

# Add all nodes
workflow.add_node("classify_intent", classify_intent_node)
workflow.add_node("answer_query", answer_query_node)
workflow.add_node("extract_data", extract_data_node)
workflow.add_node("ask_followup", followup_node)
workflow.add_node("save_and_confirm", save_and_confirm_node)

# Entry point is now the intent classifier
workflow.set_entry_point("classify_intent")

# NEW ROUTING: Log vs Query
workflow.add_conditional_edges(
    "classify_intent",
    route_intent,
    {
        "answer_query": "answer_query",
        "extract_data": "extract_data"
    }
)

# OLD ROUTING: Completeness Check
workflow.add_conditional_edges(
    "extract_data", 
    check_completeness, 
    {
        "save_and_confirm": "save_and_confirm", 
        "ask_followup": "ask_followup" 
    }
)

# End states
workflow.add_edge("answer_query", END)
workflow.add_edge("ask_followup", END)
workflow.add_edge("save_and_confirm", END)

app_brain = workflow.compile()