from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

# ---------------------------------------------------------
# 1. Wealth Schema
# ---------------------------------------------------------
class WealthLog(BaseModel):
    transaction_type: str = Field(description="Must be either 'Income' or 'Expense'.") # <--- NEW ADDITION
    amount: float = Field(description="The total amount spent or earned.")
    currency: str = Field(default="INR", description="The currency used, default is INR.")
    category: str = Field(description="The category (e.g., Salary, Food, Transport, Rent).")
    merchant: Optional[str] = Field(default=None, description="The name of the shop, service, or employer.")
    notes: Optional[str] = Field(default=None, description="Any additional context about the transaction.")

# ---------------------------------------------------------
# 2. Health Schema
# ---------------------------------------------------------
class HealthLog(BaseModel):
    sleep_hours: Optional[float] = Field(default=None, description="Hours of sleep the previous night.")
    workout_type: Optional[str] = Field(default=None, description="Type of exercise done (e.g., Gym, Running, Yoga).")
    calories_consumed: Optional[int] = Field(default=None, description="Estimated calories eaten.")
    notes: Optional[str] = Field(default=None, description="How the user felt, injuries, or mood.")

# ---------------------------------------------------------
# 3. Learning Schema
# ---------------------------------------------------------
class LearningLog(BaseModel):
    topic: str = Field(description="The main subject or concept learned today.")
    summary_text: str = Field(description="A detailed summary of what was learned. This will be embedded in the vector DB.")
    url_reference: Optional[str] = Field(default=None, description="Any link to a paper, video, or tutorial.")
    duration_minutes: Optional[int] = Field(default=None, description="Time spent learning in minutes.")

# ---------------------------------------------------------
# 4. The Daily State (For LangGraph Memory)
# ---------------------------------------------------------
class DailyLogState(BaseModel):
    current_date: str = Field(description="The date of the log in YYYY-MM-DD format.")
    wealth: Optional[WealthLog] = None
    health: Optional[HealthLog] = None
    learning: Optional[LearningLog] = None
    
    def is_complete(self) -> bool:
        """Helper method to check if all three pillars are logged for the day."""
        return all([self.wealth, self.health, self.learning])