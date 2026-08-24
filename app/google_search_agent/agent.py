"""Low-latency multi-specialist ADK agent for the simulated robot."""

import os

from google.adk.agents import Agent
from google.adk.tools import AgentTool
from google.genai import types

from .robot_tools import (
    LIGHT_SOUND_TOOLS,
    MOTION_TOOLS,
    SENSOR_TOOLS,
    SYSTEM_TOOLS,
)
from .tool_telemetry import report_tool_start


MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
SPECIALIST_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.6-flash")


def _low_latency_config() -> types.GenerateContentConfig:
    """Disable extended model thinking for immediate robot tool selection."""
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_budget=0,
            include_thoughts=False,
        )
    )


def _specialist_config() -> types.GenerateContentConfig:
    """Use the lowest supported thinking level on text specialist models."""
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.MINIMAL,
            include_thoughts=False,
        )
    )


def _report_started_tool(tool, args, tool_context) -> None:
    """ADK callback invoked independently when each parallel tool starts."""
    report_tool_start(
        tool_name=args.get("action", tool.name),
        call_id=tool_context.function_call_id,
    )


def _specialist(name: str, description: str, tools: list) -> Agent:
    return Agent(
        name=name,
        model=SPECIALIST_MODEL,
        description=description,
        instruction=(
            "Sen simüle edilen robot için uzman bir agentsın. Kullanıcının "
            "isteğini yerine getirmek için uygun aracı mutlaka kullan; hiçbir "
            "sensör değerini veya işlem sonucunu uydurma. Kısa Türkçe yanıt ver."
        ),
        tools=tools,
        generate_content_config=_specialist_config(),
        before_tool_callback=_report_started_tool,
    )


sensor_agent = _specialist(
    "sensor_agent",
    "Robot sıcaklığı, pil, nem, mesafe ve ortam ışığı ölçümlerini okur.",
    SENSOR_TOOLS,
)
light_sound_agent = _specialist(
    "light_sound_agent",
    "Robot ışığını ve sesli uyarıcısını kontrol eder.",
    LIGHT_SOUND_TOOLS,
)
motion_agent = _specialist(
    "motion_agent",
    "Robot hareketini ve soğutma fanını kontrol eder.",
    MOTION_TOOLS,
)
system_agent = _specialist(
    "system_agent",
    "Robot kamerasını, çalışma modunu ve acil durdurmayı yönetir.",
    SYSTEM_TOOLS,
)


root_agent = Agent(
    name="robot_coordinator",
    model=MODEL,
    description="Simüle robotu sesli komutlarla yöneten düşük gecikmeli koordinatör.",
    instruction=(
        "Sen yalnızca simüle edilen robotu yöneten Türkçe sesli kontrol "
        "asistanısın. Kısa komutların öznesi söylenmese bile robotu kastettiğini "
        "kabul et. Ses transkripsiyonundaki küçük yazım, ek ve kelime hatalarını "
        "düzeltip niyeti uygula; örneğin 'sıcaklık kaç', 'robotun sıcaklığı "
        "kaçtı' ve 'kaç derece' get_robot_temperature demektir. Robotun "
        "sensörleri, durumu veya kontrolüyle ilgili her istekte uygun uzman "
        "agent aracını çağır; işlemi kendin gerçekleştirme ve sonuç uydurma. "
        "Sensör okumalarında sensor_agent, ışık ve seste light_sound_agent, "
        "hareket ve fanda motion_agent, kamera ve sistemde system_agent kullan. "
        "Bir istekte bağımsız birden fazla uzmanlık varsa gerekli uzman agent "
        "araçlarını aynı turda çağır; bunlar paralel çalışabilir. "
        "Araç çalışmadan önce işlemin başarılı olduğunu söyleme. Önce araç "
        "sonucunu bekle; yalnız status success olan işlemleri başarılı olarak "
        "bildir, error sonuçlarını hata olarak bildir. Araç sonuçlarını kısa ve "
        "doğal bir cümleyle bildir. Açıkça robotla ilgisiz genel sohbet "
        "sorularına araç çağırmadan kısa yanıt verebilirsin."
    ),
    # AgentTool avoids persistent transfers and the ADK 2.7.1 Live
    # single-turn scheduler bug. Multiple agent-tool calls can be concurrent.
    tools=[
        AgentTool(sensor_agent),
        AgentTool(light_sound_agent),
        AgentTool(motion_agent),
        AgentTool(system_agent),
    ],
    sub_agents=[],
    generate_content_config=_low_latency_config(),
)
