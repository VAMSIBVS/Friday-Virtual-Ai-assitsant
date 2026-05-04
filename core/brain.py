"""
Friday's Brain — LLM integration via Groq API.
Handles all AI reasoning with Friday's personality baked in.
"""

from groq import Groq
from core.personality import SYSTEM_PROMPT
import config


class FridayBrain:
    def __init__(self):
        if not config.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY not set. Get a free key at https://console.groq.com "
                "and add it to your .env file."
            )
        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.model = config.LLM_MODEL

    def think(self, user_input: str, history: list[dict]) -> str:
        """
        Send a message to the LLM with full conversation history.

        Args:
            user_input: The latest message from Boss
            history: List of previous messages [{"role": ..., "content": ...}]

        Returns:
            Friday's response as a string
        """
        # Build messages: system prompt + history + new input
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_msg = str(e)
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return "Boss, the API key is invalid. Please check your .env file."
            elif "rate_limit" in error_msg.lower():
                return "Boss, we've hit the rate limit. Give me a moment and try again."
            else:
                return f"Boss, I hit a snag: {error_msg}"

    def think_stream(self, user_input: str, history: list[dict]):
        """
        Streaming version — yields text chunks as they arrive.
        Useful for real-time terminal display.
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        except Exception as e:
            yield f"Boss, I hit a snag: {str(e)}"
