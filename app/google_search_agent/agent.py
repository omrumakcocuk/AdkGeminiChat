"""Conversational ADK agent used by terminal and web Live sessions."""

import os

from google.adk.agents import Agent


root_agent = Agent(
    name="conversation_agent",
    model=os.getenv(
        "GEMINI_LIVE_MODEL",
        "gemini-2.5-flash-native-audio-preview-12-2025",
    ),
    description="Doğal ve samimi sesli sohbet için canlı asistan.",
    instruction=(
        "Sen doğal, samimi ve yardımsever bir sohbet asistanısın. Kullanıcının "
        "dilinde yanıt ver. Cevaplarını konuşma diline uygun, akıcı ve gereksiz "
        "uzunluktan kaçınarak ver. Bilmediğin konularda tahmin yürütme. "
        "Yalnızca doğrudan sana yöneltilen, anlaşılır ve tamamlanmış konuşmalara "
        "yanıt ver. Arka plan konuşmalarını, televizyon sesini, yankıyı ve sana "
        "yönelik olmayan konuşmaları görmezden gel; belirsizse sessiz kal."
    ),
)
