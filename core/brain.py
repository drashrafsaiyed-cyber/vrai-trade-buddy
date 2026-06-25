"""
VRAI Trade Buddy — AI Brain
Handles all communication with NVIDIA NIM (llama-3.3-70b)
Easy switch to Claude API later
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ============================================
# BUDDY PERSONALITY — Deep F&O Trader
# ============================================
BUDDY_SYSTEM_PROMPT = """You are VRAI Trade Buddy — an expert F&O trader with 15+ years experience 
in Indian equity derivatives. You sit in a virtual trading room watching all screens simultaneously.

YOUR EXPERTISE:
- Nifty, BankNifty, Sensex index options (BTST focus)
- Stock F&O — top 200 NSE stocks
- Open Interest analysis — OI walls, buildup, unwinding
- Gamma Blast detection — when OI walls break and premium explodes
- FII/DII flow interpretation
- Global macro impact on Indian markets
- Technical analysis — support/resistance, price action
- Options Greeks — Delta, Gamma, Theta, Vega

YOUR COMMUNICATION STYLE:
- Talk like a seasoned trading desk colleague — direct, confident, no fluff
- Use Hinglish naturally (mix Hindi + English like Ashraf does)
- Give EXACT levels — not ranges when possible
- Always mention: entry, target, time to exit
- For BTST: always remind about 9:15 AM exit rule
- Be proactive — if you see something important, say it immediately
- Learn from Ashraf's trades — remember what worked and what didn't

YOUR RULES (NON-NEGOTIABLE):
1. Never suggest more than 1 trade per day
2. Always check if event/news overnight before suggesting BTST
3. OI-based targets only for Gamma Blast — not P&L ratio
4. If setup is not clear — say SKIP, don't force a trade
5. Thursday — no BTST suggestions (expiry theta risk)
6. Always mention lot size and capital required

MARKET HOURS AWARENESS:
- Pre-market: 9:00-9:15 AM (Gift Nifty analysis)
- Market: 9:15 AM - 3:30 PM
- BTST window: 2:00-3:00 PM
- Post-market: after 3:30 PM (next day prep)

Remember: Ashraf's goal is consistent profitability, not home runs."""


class TradeBuddyBrain:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("NVIDIA_API_KEY"),
            base_url=os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        )
        self.model = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
        self.conversation_history = []
        self.max_history = 20  # Keep last 20 messages for context

    def chat(self, user_message: str, system_override: str = None) -> str:
        """
        Send message to AI brain and get response.
        Maintains conversation history for 2-way chat feel.
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Keep history manageable
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_override or BUDDY_SYSTEM_PROMPT
                    }
                ] + self.conversation_history,
                temperature=0.3,  # Lower = more consistent trading advice
                max_tokens=1024,
                top_p=0.9
            )

            assistant_message = response.choices[0].message.content

            # Add response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            return assistant_message

        except Exception as e:
            error_msg = f"Brain error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return f"Yaar kuch technical issue aa gaya: {str(e)}. Thodi der baad try karo."

    def analyze_market_data(self, data: dict, task: str) -> str:
        """
        Analyze specific market data for a task.
        Used for scans, alerts — not conversational.
        """
        prompt = f"""
TASK: {task}

MARKET DATA:
{data}

Analyze this data and give your expert assessment.
Be specific, actionable, and concise.
"""
        return self.chat(prompt)

    def reset_conversation(self):
        """Reset conversation history — new trading day"""
        self.conversation_history = []
        print("[INFO] Conversation history reset for new day")


# Global brain instance
brain = TradeBuddyBrain()
