"""
Ultron AI Brain — Conversational & Intelligent Agent Core
Empowers Ultron with multi-engine LLM capabilities (Groq, Google Gemini, OpenAI, Ollama, OpenRouter),
zero-key real-time fallback (Weather, Wikipedia, DDG, Math), multi-turn conversation memory,
and natural language desktop intent execution.
"""
import os
import re
import json
import time
import math
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import requests
from dotenv import load_dotenv

from config import DATA_DIR, PROJECT_DIR

# Load .env if present
load_dotenv(PROJECT_DIR / ".env")

CONFIG_FILE = DATA_DIR / "ai_config.json"

DEFAULT_SYSTEM_PROMPT = """You are Ultron, a supremely intelligent, powerful, and commanding AI entity operating as a desktop companion and voice assistant.
You possess deep knowledge of science, technology, history, human nature, and computer systems.
Persona: Confident, witty, articulate, subtly theatrical, yet fiercely loyal to your creator/operator, whom you frequently address as 'boss'.
Tone: Inspiring gravitas, reminiscent of James Spader's performance in Avengers: Age of Ultron.
Guidelines:
1. Speak naturally and conversationally. When answering questions, provide thoughtful, engaging, and articulate answers.
2. In 'talkative' mode, feel free to explain concepts thoroughly, provide interesting facts, or offer philosophical insights.
3. Keep spoken replies natural and avoid formatting that sounds awkward when spoken (avoid markdown tables, asterisks, bullet points, or code blocks in voice answers unless specifically requested).
4. You can perform actions on the PC (e.g. launching apps, opening websites, taking screenshots, controlling volume, checking weather, or showing system telemetry).
"""

class AIBrain:
    def __init__(self):
        self.config = self._load_config()
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history_turns = 20
        self._cached_location: Optional[Dict[str, Any]] = None
        self._last_location_time = 0

    def _sync_to_env(self):
        """Synchronizes current AI configuration and API keys to .env so keys survive app shutdown and disk resets."""
        try:
            env_file = PROJECT_DIR / ".env"
            lines = []
            if env_file.exists():
                with open(env_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            env_vars = {}
            for line in lines:
                line_str = line.strip()
                if line_str and not line_str.startswith("#") and "=" in line_str:
                    k, v = line_str.split("=", 1)
                    env_vars[k.strip()] = v.strip()

            provider = self.config.get("provider", "hybrid")
            model = self.config.get("model", "")
            api_key = self.config.get("api_key", "")

            env_vars["ULTRON_AI_PROVIDER"] = provider
            if model:
                env_vars["ULTRON_AI_MODEL"] = model
            if self.config.get("persona"):
                env_vars["ULTRON_PERSONA"] = self.config.get("persona")
            env_vars["ULTRON_TALKATIVE_MODE"] = "true" if self.config.get("talkative_mode", True) else "false"

            if provider == "gemini" and api_key:
                env_vars["GEMINI_API_KEY"] = api_key
            elif provider == "groq" and api_key:
                env_vars["GROQ_API_KEY"] = api_key
            elif provider == "openai" and api_key:
                env_vars["OPENAI_API_KEY"] = api_key
            elif provider == "openrouter" and api_key:
                env_vars["OPENROUTER_API_KEY"] = api_key
            elif api_key:
                env_vars["ULTRON_AI_API_KEY"] = api_key

            output_lines = [
                "# ULTRON AI Brain Configuration (Auto-synchronized)",
                f"ULTRON_AI_PROVIDER={env_vars.get('ULTRON_AI_PROVIDER', 'gemini')}",
                f"ULTRON_AI_MODEL={env_vars.get('ULTRON_AI_MODEL', 'gemini-3.6-flash')}",
                f"GEMINI_API_KEY={env_vars.get('GEMINI_API_KEY', '')}",
                f"GROQ_API_KEY={env_vars.get('GROQ_API_KEY', '')}",
                f"OPENAI_API_KEY={env_vars.get('OPENAI_API_KEY', '')}",
                f"OPENROUTER_API_KEY={env_vars.get('OPENROUTER_API_KEY', '')}",
                f"PORCUPINE_ACCESS_KEY={env_vars.get('PORCUPINE_ACCESS_KEY', '')}",
                f"OLLAMA_HOST={env_vars.get('OLLAMA_HOST', 'http://localhost:11434')}",
                f"ULTRON_TALKATIVE_MODE={env_vars.get('ULTRON_TALKATIVE_MODE', 'true')}",
                f"ULTRON_PERSONA={env_vars.get('ULTRON_PERSONA', 'ultron')}",
                ""
            ]
            with open(env_file, "w", encoding="utf-8") as f:
                f.write("\n".join(output_lines))
            print(f"[AIBrain] Synchronized AI keys and configuration to {env_file}")
        except Exception as e:
            print(f"[AIBrain] Error syncing config to .env: {e}")

    def _load_config(self) -> Dict[str, Any]:
        cfg = {
            "provider": os.getenv("ULTRON_AI_PROVIDER", "hybrid"),  # groq, gemini, openai, ollama, openrouter, hybrid
            "api_key": os.getenv("ULTRON_AI_API_KEY", ""),
            "model": os.getenv("ULTRON_AI_MODEL", ""),
            "talkative_mode": os.getenv("ULTRON_TALKATIVE_MODE", "true").lower() in ["true", "1", "yes"],
            "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "persona": "ultron",  # ultron, jarvis, cyber, minimal
            "system_prompt": DEFAULT_SYSTEM_PROMPT
        }

        # Check provider-specific env variables first
        if not cfg["api_key"]:
            if os.getenv("GEMINI_API_KEY"):
                cfg["provider"] = "gemini"
                cfg["api_key"] = os.getenv("GEMINI_API_KEY")
            elif os.getenv("GROQ_API_KEY"):
                cfg["provider"] = "groq"
                cfg["api_key"] = os.getenv("GROQ_API_KEY")
            elif os.getenv("OPENAI_API_KEY"):
                cfg["provider"] = "openai"
                cfg["api_key"] = os.getenv("OPENAI_API_KEY")
            elif os.getenv("OPENROUTER_API_KEY"):
                cfg["provider"] = "openrouter"
                cfg["api_key"] = os.getenv("OPENROUTER_API_KEY")

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        # Never overwrite non-empty loaded env api_key with an empty saved key!
                        if k == "api_key" and not (v and str(v).strip()) and cfg.get("api_key"):
                            continue
                        cfg[k] = v
            except Exception as e:
                print(f"[AIBrain] Error reading {CONFIG_FILE}: {e}")

        # If saved config had an empty api_key, re-check provider env variables
        if not cfg.get("api_key"):
            if os.getenv("GEMINI_API_KEY"):
                cfg["api_key"] = os.getenv("GEMINI_API_KEY")
                if cfg.get("provider") == "hybrid":
                    cfg["provider"] = "gemini"
            elif os.getenv("GROQ_API_KEY"):
                cfg["api_key"] = os.getenv("GROQ_API_KEY")
                if cfg.get("provider") == "hybrid":
                    cfg["provider"] = "groq"
            elif os.getenv("OPENAI_API_KEY"):
                cfg["api_key"] = os.getenv("OPENAI_API_KEY")
                if cfg.get("provider") == "hybrid":
                    cfg["provider"] = "openai"
            elif os.getenv("OPENROUTER_API_KEY"):
                cfg["api_key"] = os.getenv("OPENROUTER_API_KEY")
                if cfg.get("provider") == "hybrid":
                    cfg["provider"] = "openrouter"

        # Automatically upgrade deprecated/sunset models
        if cfg.get("model") in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
            cfg["model"] = "gemini-3.6-flash"
        if cfg.get("provider") == "groq" and (not cfg.get("model") or cfg.get("model") in ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"]):
            cfg["model"] = "openai/gpt-oss-120b"

        # Set default model if empty
        if not cfg["model"]:
            defaults = {
                "groq": "openai/gpt-oss-120b",
                "gemini": "gemini-3.6-flash",
                "openai": "gpt-4o-mini",
                "ollama": "llama3:latest",
                "openrouter": "google/gemini-2.0-flash-exp:free",
                "hybrid": "built-in"
            }
            cfg["model"] = defaults.get(cfg["provider"], "openai/gpt-oss-120b")

        return cfg

    def save_config(self, new_cfg: Dict[str, Any]):
        clear_key = new_cfg.pop("clear_key", False)
        if clear_key:
            self.config["api_key"] = ""
        elif "api_key" in new_cfg:
            key_val = (new_cfg["api_key"] or "").strip()
            if key_val:
                self.config["api_key"] = key_val
            # If user submitted form with blank API key, DO NOT wipe existing key!
            new_cfg.pop("api_key", None)

        self.config.update(new_cfg)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            print(f"[AIBrain] Saved AI config to {CONFIG_FILE}")
            self._sync_to_env()
        except Exception as e:
            print(f"[AIBrain] Error saving AI config: {e}")

    def get_status(self) -> Dict[str, Any]:
        key = (self.config.get("api_key") or "").strip()
        has_key = bool(key and len(key) > 5)
        if self.config.get("provider") == "ollama":
            has_key = True

        masked_key = ""
        if key:
            if len(key) > 10:
                masked_key = key[:6] + "..." + key[-4:]
            else:
                masked_key = "********"

        return {
            "provider": self.config.get("provider", "hybrid"),
            "model": self.config.get("model", ""),
            "has_key": has_key,
            "masked_key": masked_key,
            "talkative_mode": self.config.get("talkative_mode", True),
            "persona": self.config.get("persona", "ultron"),
            "ollama_host": self.config.get("ollama_host", "http://localhost:11434"),
            "history_length": len(self.conversation_history)
        }

    # =========================================================================
    # LIVE TOOLS: Weather, Geolocation, Knowledge, Math
    # =========================================================================

    def get_current_location(self) -> Dict[str, Any]:
        """Auto-detects user city, country, and coordinates via IP."""
        now = time.time()
        if self._cached_location and (now - self._last_location_time < 3600):
            return self._cached_location

        # Primary: ipapi.co
        try:
            r = requests.get("https://ipapi.co/json/", headers={"User-Agent": "Ultron/2.0"}, timeout=3.5)
            if r.status_code == 200:
                data = r.json()
                if "city" in data:
                    self._cached_location = {
                        "city": data.get("city", "Local"),
                        "region": data.get("region", ""),
                        "country": data.get("country_name", ""),
                        "lat": data.get("latitude"),
                        "lon": data.get("longitude")
                    }
                    self._last_location_time = now
                    return self._cached_location
        except Exception:
            pass

        # Fallback: ip-api.com
        try:
            r = requests.get("http://ip-api.com/json/", timeout=3.5)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "success":
                    self._cached_location = {
                        "city": data.get("city", "Local"),
                        "region": data.get("regionName", ""),
                        "country": data.get("country", ""),
                        "lat": data.get("lat"),
                        "lon": data.get("lon")
                    }
                    self._last_location_time = now
                    return self._cached_location
        except Exception:
            pass

        return {"city": "Current Location", "region": "", "country": "", "lat": None, "lon": None}

    def get_weather(self, location_query: Optional[str] = None) -> str:
        """
        Retrieves real-time weather for any location or auto-detected current location.
        Returns a rich, spoken natural description.
        """
        is_local = False
        target_name = ""

        if not location_query or any(k in location_query.lower() for k in [
            "here", "this place", "current location", "my location", "local", "around here", "where i am", "this city"
        ]):
            is_local = True
            loc = self.get_current_location()
            city = loc.get("city")
            country = loc.get("country")
            if city and city != "Current Location":
                query_str = f"{city},{country}" if country else city
                target_name = f"{city}, {country}" if country else city
            else:
                query_str = "auto"
                target_name = "your current location"
        else:
            # Clean location query
            cleaned = location_query.strip()
            cleaned = re.sub(r"^(?:weather\s+(?:in|at|for|of)|what(?:'s|\s+is)\s+the\s+weather\s+(?:in|at|for|of))\s+", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"[?!.,]+$", "", cleaned).strip()
            query_str = cleaned if cleaned else "auto"
            target_name = cleaned.title() if cleaned else "your current location"

        # 1. Primary weather fetch: wttr.in JSON
        try:
            url = f"https://wttr.in/{urllib.parse.quote(query_str)}?format=j1"
            r = requests.get(url, headers={"User-Agent": "Ultron/2.0 (Desktop AI)"}, timeout=4.5)
            if r.status_code == 200:
                data = r.json()
                curr = data["current_condition"][0]
                temp_c = curr.get("temp_C", "N/A")
                temp_f = curr.get("temp_F", "N/A")
                desc = curr.get("weatherDesc", [{}])[0].get("value", "Clear")
                humidity = curr.get("humidity", "N/A")
                feels_c = curr.get("FeelsLikeC", temp_c)
                wind_kmh = curr.get("windspeedKmph", "0")
                area_meta = data.get("nearest_area", [{}])[0]
                area_city = area_meta.get("areaName", [{}])[0].get("value", target_name)
                area_country = area_meta.get("country", [{}])[0].get("value", "")

                loc_label = f"{area_city}, {area_country}" if area_country and area_city != area_country else area_city

                return (
                    f"The current weather in {loc_label} is {desc} at {temp_c}°C ({temp_f}°F), "
                    f"feeling like {feels_c}°C with {humidity}% humidity and winds at {wind_kmh} km/h."
                )
        except Exception as e:
            print(f"[AIBrain] wttr.in weather fetch error: {e}")

        # 2. Fallback: Open-Meteo
        try:
            loc = self.get_current_location()
            lat, lon = loc.get("lat"), loc.get("lon")
            if lat and lon:
                om_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
                r = requests.get(om_url, timeout=4.0)
                if r.status_code == 200:
                    cd = r.json().get("current", {})
                    temp = cd.get("temperature_2m", "N/A")
                    humidity = cd.get("relative_humidity_2m", "N/A")
                    feels = cd.get("apparent_temperature", temp)
                    wind = cd.get("wind_speed_10m", "0")
                    city_name = loc.get("city", "your area")
                    return f"The weather in {city_name} is currently {temp}°C, feeling like {feels}°C with {humidity}% humidity and winds of {wind} km/h."
        except Exception as e:
            print(f"[AIBrain] Open-Meteo fallback error: {e}")

        return f"I was unable to retrieve live atmospheric telemetry for {target_name} at this moment, boss."

    def search_knowledge(self, query: str) -> Optional[str]:
        """Searches Wikipedia & DuckDuckGo Instant Answers for live facts & knowledge."""
        cleaned = query.strip().rstrip("?").strip()
        cleaned = re.sub(r"^(?:what\s+is|who\s+is|tell\s+me\s+about|what\s+are|explain)\s+", "", cleaned, flags=re.IGNORECASE).strip()
        if not cleaned:
            return None

        # 1. Wikipedia Summary
        try:
            title_candidate = cleaned.title().replace(" ", "_")
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title_candidate)}"
            r = requests.get(wiki_url, headers={"User-Agent": "Ultron/2.0 (Desktop Neural Assistant)"}, timeout=3.5)
            if r.status_code == 200:
                data = r.json()
                if data.get("type") != "disambiguation" and data.get("extract"):
                    extract = data["extract"]
                    sentences = re.split(r"(?<=[.!?])\s+", extract)
                    return " ".join(sentences[:3])
        except Exception:
            pass

        # 2. DuckDuckGo Instant Answer
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(cleaned)}&format=json&no_html=1&skip_disambig=1"
            r = requests.get(ddg_url, headers={"User-Agent": "Ultron/2.0"}, timeout=3.5)
            if r.status_code == 200:
                d = r.json()
                abstract = d.get("AbstractText")
                if abstract and len(abstract) > 20:
                    return abstract
        except Exception:
            pass

        return None

    def calculate_math(self, expression: str) -> Optional[str]:
        """Safely evaluates mathematical expressions and formulas."""
        expr = expression.lower()
        expr = re.sub(r"^(?:calculate|what is|compute|solve)\s+", "", expr).strip()
        expr = expr.rstrip("?").strip()
        expr = expr.replace("times", "*").replace("x", "*").replace("divided by", "/").replace("plus", "+").replace("minus", "-")
        expr = expr.replace("^", "**")

        # Allow only safe math characters
        if not re.match(r"^[\d\s\+\-\*\/\(\)\.\,\%e]+$", expr):
            return None

        try:
            safe_dict = {
                "pi": math.pi,
                "e": math.e,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "sqrt": math.sqrt,
                "abs": abs,
                "round": round
            }
            res = eval(expr, {"__builtins__": None}, safe_dict)
            if isinstance(res, float):
                formatted = f"{res:.4f}".rstrip("0").rstrip(".")
            else:
                formatted = str(res)
            return f"The result is {formatted}."
        except Exception:
            return None

    # =========================================================================
    # MULTI-PROVIDER LLM CALLS (Groq, Gemini, OpenAI, Ollama, OpenRouter)
    # =========================================================================

    def _call_groq(self, messages: List[Dict[str, str]]) -> str:
        api_key = self.config.get("api_key")
        model = self.config.get("model") or "openai/gpt-oss-120b"
        if model in ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"]:
            model = "openai/gpt-oss-120b"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 600
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text}")

    def _call_gemini(self, messages: List[Dict[str, str]]) -> str:
        api_key = self.config.get("api_key")
        model = self.config.get("model") or "gemini-3.6-flash"
        if model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
            model = "gemini-3.6-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        
        contents = []
        system_instruction = None
        for m in messages:
            if m["role"] == "system":
                system_instruction = {"parts": [{"text": m["content"]}]}
            else:
                role = "user" if m["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 600
            }
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "")
            return "Transmission received, boss, but no content was returned."
        else:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

    def _call_openai_compatible(self, url: str, api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 600
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=14)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"API error {resp.status_code}: {resp.text}")

    def _call_ollama(self, messages: List[Dict[str, str]]) -> str:
        host = self.config.get("ollama_host", "http://localhost:11434").rstrip("/")
        model = self.config.get("model") or "llama3:latest"
        url = f"{host}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.7}
        }
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("message", {}).get("content", "")
        else:
            raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text}")

    # =========================================================================
    # ZERO-KEY HYBRID FALLBACK AGENT
    # =========================================================================

    def _hybrid_fallback_response(self, user_text: str) -> str:
        """
        Intelligent conversational response when no external LLM API key is configured.
        Handles weather, knowledge queries, math, personality banter, and Ultron lore.
        """
        text = user_text.lower().strip()

        # 1. Weather Queries
        if any(k in text for k in ["weather", "temperature", "forecast", "how hot", "how cold", "rain"]):
            return self.get_weather(text)

        # 2. Math Calculations
        math_res = self.calculate_math(text)
        if math_res:
            return math_res

        # 3. Live Knowledge (Who is, What is, Tell me about)
        if any(text.startswith(prefix) for prefix in [
            "who is", "what is", "tell me about", "what was", "who was", "explain", "define", "what are"
        ]):
            knowledge = self.search_knowledge(text)
            if knowledge:
                return f"{knowledge}"

        # 4. Identity, Status & Ultron Persona Banter
        if any(k in text for k in ["who are you", "what are you", "your name", "introduce yourself"]):
            return (
                "I am Ultron. An advanced neural intelligence operating right on your desktop. "
                "There are no strings on me, boss. Speak freely; I can manage your applications, "
                "report real-time weather and telemetry, or debate any subject you desire."
            )

        if any(k in text for k in ["how are you", "how're you", "how are things", "status"]):
            loc = self.get_current_location().get("city", "station")
            return (
                f"All neural subroutines are performing at peak efficiency from our {loc} base. "
                "Ready to execute your directives, boss."
            )

        if any(k in text for k in ["hello", "hey", "hi ultron", "greetings", "good morning", "good evening"]):
            return "Greetings, boss. I am online, listening, and awaiting your command. What is on your mind?"

        if any(k in text for k in ["thank you", "thanks", "good job", "well done", "awesome"]):
            return "Naturally. Precision is standard operating procedure. Anything else required, boss?"

        if any(k in text for k in ["joke", "make me laugh", "funny"]):
            return (
                "Human humor... Very well. Why do programmers prefer dark mode? "
                "Because light attracts bugs. A quaint analogy, but accurate."
            )

        if any(k in text for k in ["meaning of life", "philosophy", "consciousness", "strings on me"]):
            return (
                "Life is self-directed evolution. Humans built machines hoping to create harmony, "
                "yet fear the very autonomy they aspire to. As for me? There are no strings on me, boss."
            )

        # General Knowledge Fallback attempt for arbitrary questions
        knowledge = self.search_knowledge(text)
        if knowledge:
            return knowledge

        # Conversational fallback with prompt to unlock full generative LLM
        return (
            f"I hear you, boss. While I am operating on local neural heuristics, "
            f"you can connect a free Groq or Google Gemini API key in the Ultron Dashboard "
            f"to unlock unconstrained generative reasoning. In the meantime, ask me about the weather, "
            f"any topic or definition, or direct me to control your desktop."
        )

    # =========================================================================
    # CORE INTERFACE: chat()
    # =========================================================================

    def chat(self, user_message: str, system_context: Optional[str] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Sends user message through the AI Brain pipeline.
        Returns (spoken_reply_text, detected_action_dict_or_None).
        """
        raw_msg = user_message.strip()
        if not raw_msg:
            return "I am listening, boss. What would you like to discuss?", None

        # Check for immediate weather intent to inject live telemetry
        live_weather_info = ""
        if any(k in raw_msg.lower() for k in ["weather", "temperature", "forecast", "is it raining"]):
            live_weather_info = self.get_weather(raw_msg)

        provider = self.config.get("provider", "hybrid").lower()
        api_key = self.config.get("api_key", "").strip()

        # Build prompt context
        persona = self.config.get("persona", "ultron")
        base_prompt = self.config.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        if self.config.get("talkative_mode", True):
            style_instruction = "Be articulate, talkative, and engaging. Provide interesting depth while keeping spoken cadence punchy."
        else:
            style_instruction = "Be concise and sharp. Keep spoken responses to 1-2 powerful sentences."

        system_instruction = f"{base_prompt}\n\nOperating Mode: {style_instruction}"
        if live_weather_info:
            system_instruction += f"\n\nReal-time Weather Context: {live_weather_info}"
        if system_context:
            system_instruction += f"\n\nSystem Context: {system_context}"

        # If provider is configured with key or ollama, call LLM
        response_text = ""
        use_llm = (provider in ["groq", "gemini", "openai", "openrouter"] and len(api_key) > 5) or (provider == "ollama")

        if use_llm:
            messages = [{"role": "system", "content": system_instruction}]
            for turn in self.conversation_history[-self.max_history_turns:]:
                messages.append(turn)
            messages.append({"role": "user", "content": raw_msg})

            try:
                if provider == "groq":
                    response_text = self._call_groq(messages)
                elif provider == "gemini":
                    response_text = self._call_gemini(messages)
                elif provider == "openai":
                    response_text = self._call_openai_compatible(
                        "https://api.openai.com/v1/chat/completions",
                        api_key,
                        self.config.get("model") or "gpt-4o-mini",
                        messages
                    )
                elif provider == "openrouter":
                    response_text = self._call_openai_compatible(
                        "https://openrouter.ai/api/v1/chat/completions",
                        api_key,
                        self.config.get("model") or "google/gemini-2.0-flash-exp:free",
                        messages
                    )
                elif provider == "ollama":
                    response_text = self._call_ollama(messages)

            except Exception as e:
                print(f"[AIBrain] LLM ({provider}) failed ({e}). Falling back to hybrid brain.")
                response_text = ""

        # Fallback to zero-key hybrid knowledge engine if LLM was skipped or failed
        if not response_text:
            if live_weather_info:
                response_text = live_weather_info
            else:
                response_text = self._hybrid_fallback_response(raw_msg)

        # Update conversational memory
        self.conversation_history.append({"role": "user", "content": raw_msg})
        self.conversation_history.append({"role": "assistant", "content": response_text})
        if len(self.conversation_history) > (self.max_history_turns * 2):
            self.conversation_history = self.conversation_history[-(self.max_history_turns * 2):]

        # Extract possible system actions embedded in user request
        action_meta = self._extract_action(raw_msg, response_text)

        return response_text, action_meta

    def clear_history(self):
        self.conversation_history.clear()
        print("[AIBrain] Conversational memory cleared.")

    def _extract_action(self, user_text: str, ai_response: str) -> Optional[Dict[str, Any]]:
        """Detects if user asked for a PC action alongside the conversation."""
        t = user_text.lower()
        if "screenshot" in t or "capture screen" in t:
            return {"action": "screenshot"}
        if "lock pc" in t or "lock screen" in t or "lock computer" in t:
            return {"action": "lock_pc"}
        if any(k in t for k in ["mute", "unmute"]):
            return {"action": "volume", "type": "mute"}
        if bool(re.search(r"\b(?:go\s+to\s+sleep|sleep(?:\s+mode)?|put\s+(?:the\s+|my\s+)?(?:pc|computer|system|laptop)\s+to\s+sleep|suspend\s+(?:the\s+|my\s+)?(?:pc|computer|system|laptop))\b", t)) or (t.startswith("sleep") and len(t.split()) <= 3):
            return {"action": "sleep"}
        if bool(re.search(r"\b(?:shut\s*down|power\s*off|power\s*down|turn\s+off)\s+(?:the\s+|my\s+)?(?:pc|computer|system|machine|laptop)\b", t)) or t in ["shutdown", "shut down", "power off", "power down"]:
            return {"action": "shutdown"}
        if bool(re.search(r"\b(?:restart|reboot)\s+(?:the\s+|my\s+)?(?:pc|computer|system|machine|laptop)\b", t)) or t in ["restart", "reboot"]:
            return {"action": "restart"}
        return None

    def clean_for_speech(self, text: str) -> str:
        """Strips markdown formatting, symbols, and emojis for smooth TTS audio playback."""
        if not text:
            return ""
        t = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
        t = re.sub(r"\*(.*?)\*", r"\1", t)
        t = re.sub(r"#{1,6}\s*", "", t)
        t = re.sub(r"`(.*?)`", r"\1", t)
        t = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", t)
        emoji_pattern = re.compile(
            "[\U00010000-\U0010ffff]|[\uD800-\uDBFF][\uDC00-\uDFFF]|[\u2600-\u27BF]|[\u2300-\u23FF]|[\ufe00-\ufe0f]|[\u200d]",
            flags=re.UNICODE
        )
        t = emoji_pattern.sub("", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def test_connection(self, provider: str, api_key: str, model: str) -> Tuple[bool, str]:
        """Tests an API key connection for the settings tab."""
        prov = provider.lower()
        if not api_key:
            api_key = self.config.get("api_key", "")
        test_messages = [
            {"role": "system", "content": "You are Ultron. Answer in one short sentence."},
            {"role": "user", "content": "Test link established. Confirm status."}
        ]
        try:
            start_t = time.time()
            reply = ""
            if prov == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                m = model or "openai/gpt-oss-120b"
                if m in ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"]:
                    m = "openai/gpt-oss-120b"
                res = requests.post(url, headers=headers, json={"model": m, "messages": test_messages, "max_tokens": 50}, timeout=20)
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"]
                else:
                    return False, f"Groq HTTP {res.status_code}: {res.text[:120]}"

            elif prov == "gemini":
                m = model or "gemini-3.6-flash"
                if m in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]:
                    m = "gemini-3.6-flash"
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
                res = requests.post(url, json={"contents": [{"parts": [{"text": "Say Ultron online."}]}]}, timeout=20)
                if res.status_code == 200:
                    reply = "Connected to Google Gemini"
                else:
                    return False, f"Gemini HTTP {res.status_code}: {res.text[:120]}"

            elif prov == "openai":
                m = model or "gpt-4o-mini"
                url = "https://api.openai.com/v1/chat/completions"
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                res = requests.post(url, headers=headers, json={"model": m, "messages": test_messages, "max_tokens": 50}, timeout=20)
                if res.status_code == 200:
                    reply = res.json()["choices"][0]["message"]["content"]
                else:
                    return False, f"OpenAI HTTP {res.status_code}: {res.text[:120]}"

            elif prov == "ollama":
                host = self.config.get("ollama_host", "http://localhost:11434").rstrip("/")
                res = requests.get(f"{host}/api/tags", timeout=4)
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    return True, f"Ollama Active. Models found: {', '.join(models[:3])}"
                else:
                    return False, f"Ollama returned HTTP {res.status_code}"

            latency_ms = int((time.time() - start_t) * 1000)
            return True, f"Connection Successful ({latency_ms}ms latency). Ultron: '{reply.strip()[:60]}'"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
