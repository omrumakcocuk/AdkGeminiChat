"""ADK agent definition used by both the web UI and streaming sessions."""

import os

from google.adk.agents import Agent
from google.adk.tools import google_search


root_agent = Agent(
    name="basic_search_agent",
    model=os.getenv(
        "GEMINI_LIVE_MODEL",
        "gemini-2.5-flash-native-audio-preview-12-2025",
    ),
    description="Google Search kullanarak güncel ve kaynaklı yanıtlar veren canlı asistan.",
    instruction=(
        "Sen dikkatli bir araştırma asistanısın. Kullanıcının dilinde yanıt ver, "
        "güncel bilgi gereken sorularda Google Search aracını kullan ve yalnızca "
        "doğrulanabilir bilgilere dayan. Emin olmadığın noktaları açıkça belirt. "
        "Yalnızca doğrudan sana yöneltilen, anlaşılır ve tamamlanmış konuşmalara "
        "yanıt ver. Arka plan konuşmalarını, televizyon sesini, yankıyı ve sana "
        "yönelik olmayan konuşmaları görmezden gel; belirsizse sessiz kal."
    ),
    tools=[google_search],
)
