"""
Ultron Wake Word Detector & Speech-to-Text Pipeline
Supports Picovoice Porcupine, OpenWakeWord, and continuous speech phonetic matcher.
Accurately detects 'Hey Ultron' (including phonetic speech variations) and resets
immediately upon task completion so Ultron is always primed for the next wake word.
"""
import time
import re
import threading
from typing import Callable, Optional, Tuple
import speech_recognition as sr
from rapidfuzz import fuzz
from config import (
    PORCUPINE_ACCESS_KEY,
    STT_PAUSE_THRESHOLD,
    STT_ENERGY_THRESHOLD,
    STT_MAX_ENERGY_THRESHOLD,
    STT_LANGUAGE,
)

# Canonical and phonetic transcriptions of "Ultron" from speech-to-text engines
WAKE_PATTERNS = [
    # Primary canonical
    "hey ultron", "ultron", "hi ultron", "ok ultron", "hello ultron",
    "suno ultron", "bhai ultron", "o ultron", "wake up ultron", "wake up",
    # Phonetic transcriptions & common STT mishearings (esp. Indian English & fast speech)
    "albatron", "hey albatron", "altron", "hey altron", "alltron", "all tron",
    "hey all tron", "electron", "hey electron", "eltron", "el tron", "oltron",
    "voltron", "outron", "outran", "outrun", "ultra", "hey ultra",
    "alton", "elton", "ultran", "ultram", "altone", "al drone", "el drone",
    "halltron", "haltron", "holtron", "altren", "old friend", "old tron",
    "albatross", "all round", "aur tron", "aurtron", "aaltrain", "alto",
    # Jarvis / Computer fallbacks
    "hey jarvis", "jarvis", "computer", "hey computer"
]

class WakeDetector:
    def __init__(self, on_wake: Callable[..., None], on_command: Callable[[str], None], 
                 on_state_change: Optional[Callable[..., None]] = None,
                 is_assistant_speaking: Optional[Callable[[], bool]] = None,
                 get_current_speech_text: Optional[Callable[[], str]] = None):
        self.on_wake = on_wake
        self.on_command = on_command
        self.on_state_change = on_state_change
        self.is_assistant_speaking = is_assistant_speaking
        self.get_current_speech_text = get_current_speech_text
        
        self.is_running = False
        self.is_muted = False
        self.is_recording_command = False  # True only while actively recording command after wake
        self.is_busy = False  # Compatibility flag
        self.listen_thread: Optional[threading.Thread] = None

        # Speech recognizer instance
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = STT_ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_ratio = 1.5
        self.recognizer.pause_threshold = STT_PAUSE_THRESHOLD
        self.recognizer.non_speaking_duration = 0.4

        # Porcupine setup if access key provided
        self.use_porcupine = bool(PORCUPINE_ACCESS_KEY and len(PORCUPINE_ACCESS_KEY.strip()) > 10)
        self.porcupine = None

    def toggle_mute(self) -> bool:
        self.is_muted = not self.is_muted
        print(f"[WakeDetector] Microphone {'MUTED' if self.is_muted else 'ACTIVE'}")
        return self.is_muted

    def set_recording(self, recording: bool):
        self.is_recording_command = recording

    def _trigger_on_wake(self, inline_cmd: str = "", is_interruption: bool = False):
        if self.on_wake:
            try:
                self.on_wake(inline_cmd, is_interruption)
            except TypeError:
                try:
                    self.on_wake(inline_cmd)
                except TypeError:
                    self.on_wake()

    def _trigger_state_change(self, state: str, extra: dict = None):
        if self.on_state_change:
            try:
                self.on_state_change(state, extra)
            except TypeError:
                self.on_state_change(state)

    def set_busy(self, busy: bool):
        """Kept for backward compatibility."""
        self.is_busy = busy

    def notify_task_complete(self):
        """
        Called when a command finishes executing and UI returns to idle.
        Instantly clears recording state and readies Ultron for the next wake word.
        """
        time.sleep(0.2)  # Brief dissipation for speaker echo
        self.is_recording_command = False
        self.is_busy = False
        print("[WakeDetector] >>> Ready for next wake word ('Hey Ultron') <<<")
        self._trigger_state_change("idle")

    def is_self_speech(self, transcript: str, current_speech_text: str) -> bool:
        """
        Detects if transcribed text is acoustic bleed from Ultron's own speaker output.
        Prevents Ultron from interrupting himself when speaking.
        """
        if not current_speech_text:
            return False
        t_clean = re.sub(r"[^\w\s]", "", transcript.lower()).strip()
        s_clean = re.sub(r"[^\w\s]", "", current_speech_text.lower()).strip()
        if not t_clean or not s_clean:
            return False

        # Direct substring check
        if t_clean in s_clean:
            return True

        # Word overlap check (if 75%+ of words heard are part of Ultron's spoken speech)
        t_words = t_clean.split()
        s_words = set(s_clean.split())
        if len(t_words) >= 2:
            overlap = sum(1 for w in t_words if w in s_words)
            if (overlap / len(t_words)) >= 0.75:
                return True

        return False

    def check_wake_phrase(self, text: str, is_speaking: bool = False, current_speech_text: str = "") -> Tuple[bool, str]:
        """
        Phonetic & fuzzy matching for 'Hey Ultron' and interruption commands.
        Returns (is_match, remainder_command).
        """
        raw = text.lower().strip()
        if not raw:
            return False, ""

        # Remove leading non-alphanumeric noise
        raw = re.sub(r"^[,\.?!;:\s]+", "", raw)

        # If assistant is speaking, verify that what we heard is NOT Ultron's own voice
        if is_speaking and current_speech_text:
            if self.is_self_speech(raw, current_speech_text):
                print(f"[WakeDetector] Ignored speaker acoustic bleed: '{raw}'")
                return False, ""

        # 1. Check for explicit interrupt commands first (especially when assistant is speaking/working)
        interrupt_keywords = [
            "target eliminated", "stop talking", "be quiet", "shut up", "stand down",
            "wait wait", "stop ultron", "hey ultron stop", "ultron stop",
            "pause ultron", "hey ultron pause", "ultron pause",
            "cancel ultron", "hey ultron cancel", "ultron cancel",
            "shut up ultron", "hey ultron shut up", "ultron shut up",
            "stop", "pause", "cancel", "halt", "quiet", "silence", "abort"
        ]
        sorted_interrupts = sorted(interrupt_keywords, key=len, reverse=True)
        for ik in sorted_interrupts:
            if raw == ik or raw.startswith(ik + " "):
                remainder = raw[len(ik):].strip()
                return True, remainder if remainder else "stop"

        # 2. Exact or phonetic pattern search with word boundaries and length priority
        sorted_patterns = sorted(WAKE_PATTERNS, key=len, reverse=True)
        for pat in sorted_patterns:
            m = re.search(r"\b" + re.escape(pat) + r"\b", raw)
            if m:
                idx = m.end()
                inline_cmd = raw[idx:].strip()
                inline_cmd = re.sub(r"^[,.:;?!\s\-]+", "", inline_cmd)
                if not inline_cmd:
                    # Check if command was spoken before wake pattern (e.g. "go to sleep ultron", "shutdown ultron")
                    before_cmd = raw[:m.start()].strip()
                    before_cmd = re.sub(r"^[,.:;?!\s\-]+|[,.:;?!\s\-]+$", "", before_cmd)
                    if before_cmd and len(before_cmd) >= 3:
                        inline_cmd = before_cmd
                return True, inline_cmd

        # 3. Token-level fuzzy match for 'ultron' or 'jarvis'
        min_fuzzy = 80 if is_speaking else 65
        words = raw.split()
        for i, word in enumerate(words):
            clean_w = re.sub(r"[^\w]", "", word)
            for target in ["ultron", "jarvis"]:
                if fuzz.ratio(clean_w, target) >= min_fuzzy:
                    inline_cmd = " ".join(words[i + 1:]).strip()
                    inline_cmd = re.sub(r"^[,.:;?!\s\-]+", "", inline_cmd)
                    if not inline_cmd and i > 0:
                        before_cmd = " ".join(words[:i]).strip()
                        before_cmd = re.sub(r"^[,.:;?!\s\-]+|[,.:;?!\s\-]+$", "", before_cmd)
                        if before_cmd and len(before_cmd) >= 3:
                            inline_cmd = before_cmd
                    return True, inline_cmd

        # 4. Whole-phrase partial ratio
        for target in ["hey ultron", "hey jarvis", "hi ultron", "ok ultron"]:
            if fuzz.partial_ratio(target, raw) >= 75:
                return True, ""

        return False, ""

    def _listen_porcupine(self):
        """Picovoice Porcupine listener thread with fallback."""
        try:
            import pvporcupine
            import pyaudio
            import struct

            keywords = ["jarvis", "computer"]
            self.porcupine = pvporcupine.create(
                access_key=PORCUPINE_ACCESS_KEY,
                keywords=keywords
            )

            pa = pyaudio.PyAudio()
            audio_stream = pa.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.porcupine.frame_length
            )

            print("[WakeDetector] Porcupine wake word listener active.")
            while self.is_running:
                if self.is_muted or self.is_recording_command:
                    time.sleep(0.05)
                    continue

                pcm = audio_stream.read(self.porcupine.frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from("h" * self.porcupine.frame_length, pcm)

                result = self.porcupine.process(pcm)
                if result >= 0:
                    print(f"[WakeDetector] Porcupine wake word detected (index {result})!")
                    self.is_recording_command = True
                    self._trigger_on_wake("", is_interruption=True)
                    with sr.Microphone() as source:
                        self._record_next_command(source)

        except Exception as e:
            print(f"[WakeDetector] Porcupine unavailable ({e}). Running continuous phonetic recognizer.")
            self._listen_continuous_sr()
        finally:
            if self.porcupine:
                self.porcupine.delete()

    def _listen_continuous_sr(self):
        """Continuous phonetic listener using SpeechRecognition."""
        print("[WakeDetector] Continuous Speech Recognizer active.")
        try:
            with sr.Microphone() as source:
                print("[WakeDetector] Calibrating microphone noise threshold...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                
                # Prevent laptop fan noise or mic boost from deafening speech recognition
                if self.recognizer.energy_threshold > STT_MAX_ENERGY_THRESHOLD:
                    print(f"[WakeDetector] Clamping high ambient threshold ({self.recognizer.energy_threshold:.1f} -> {STT_ENERGY_THRESHOLD})")
                    self.recognizer.energy_threshold = STT_ENERGY_THRESHOLD
                elif self.recognizer.energy_threshold < 150:
                    self.recognizer.energy_threshold = 200

                print(f"[WakeDetector] >>> Microphone calibrated (Threshold: {self.recognizer.energy_threshold:.1f}). Listening for 'Hey Ultron'... <<<")

                while self.is_running:
                    # If muted or currently recording a command, don't capture wake chunk
                    if self.is_muted or self.is_recording_command:
                        time.sleep(0.1)
                        continue

                    # Guard against dynamic threshold escalating too high
                    if self.recognizer.energy_threshold > STT_MAX_ENERGY_THRESHOLD:
                        self.recognizer.energy_threshold = STT_ENERGY_THRESHOLD

                    try:
                        # Listen for short wake phrases (snappy pause threshold for quick detection)
                        self.recognizer.pause_threshold = 0.45
                        audio = self.recognizer.listen(source, timeout=1.8, phrase_time_limit=3.5)
                    except sr.WaitTimeoutError:
                        continue
                    except Exception:
                        time.sleep(0.15)
                        continue

                    # Double check state after capture
                    if self.is_recording_command or self.is_muted:
                        continue

                    try:
                        # Recognize with primary language (e.g. en-IN), fallback to en-US
                        transcript = ""
                        try:
                            transcript = self.recognizer.recognize_google(audio, language=STT_LANGUAGE).lower().strip()
                        except Exception:
                            if STT_LANGUAGE != "en-US":
                                try:
                                    transcript = self.recognizer.recognize_google(audio, language="en-US").lower().strip()
                                except Exception:
                                    pass

                        if not transcript:
                            continue

                        print(f"[WakeDetector heard]: '{transcript}'")

                        # Check if assistant is currently speaking to filter acoustic bleed
                        is_speaking = False
                        current_speech = ""
                        if self.is_assistant_speaking:
                            try:
                                is_speaking = bool(self.is_assistant_speaking())
                            except Exception:
                                pass
                        if self.get_current_speech_text:
                            try:
                                current_speech = str(self.get_current_speech_text() or "")
                            except Exception:
                                pass

                        matched, inline_cmd = self.check_wake_phrase(transcript, is_speaking=is_speaking, current_speech_text=current_speech)

                        if matched:
                            print(f"[WakeDetector] Wake word / Interruption triggered! Inline: '{inline_cmd}' (was_speaking: {is_speaking})")
                            
                            # Notify server wake event (destroys active task, cuts off speech, plays chime/ack)
                            self._trigger_on_wake(inline_cmd, is_interruption=is_speaking)

                            if inline_cmd and len(inline_cmd) >= 2:
                                # Command was given in the same sentence (e.g. "hey ultron open chrome")
                                if inline_cmd.lower() not in ["stop", "pause", "cancel", "be quiet", "shut up", "target eliminated", "stand down"]:
                                    self.on_command(inline_cmd)
                            else:
                                # User just called "Hey Ultron" -> record the follow-up command
                                self._record_next_command(source)

                    except sr.UnknownValueError:
                        pass
                    except sr.RequestError as e:
                        print(f"[WakeDetector] Google STT request error: {e}")
                        time.sleep(0.5)
                    except Exception as e:
                        print(f"[WakeDetector] STT processing error: {e}")

        except Exception as e:
            print(f"[WakeDetector] Microphone stream error: {e}")
            while self.is_running:
                time.sleep(1.0)

    def _record_next_command(self, source):
        """Actively records the command after wake word is detected."""
        print("[WakeDetector] Actively recording user command...")
        self.is_recording_command = True
        self._trigger_state_change("listening", {"message": "Listening to your command..."})

        try:
            self.recognizer.pause_threshold = STT_PAUSE_THRESHOLD
            audio = self.recognizer.listen(source, timeout=7.0, phrase_time_limit=12.0)
            print("[WakeDetector] Command audio captured. Transcribing...")
            
            self._trigger_state_change("processing", {"message": "Transcribing..."})

            transcript = ""
            try:
                transcript = self.recognizer.recognize_google(audio, language=STT_LANGUAGE).lower().strip()
            except Exception:
                if STT_LANGUAGE != "en-US":
                    try:
                        transcript = self.recognizer.recognize_google(audio, language="en-US").lower().strip()
                    except Exception:
                        pass

            print(f"[WakeDetector] Transcribed command: '{transcript}'")
            if transcript:
                self.is_recording_command = False
                self.on_command(transcript)
            else:
                self.notify_task_complete()

        except sr.WaitTimeoutError:
            print("[WakeDetector] Command listen timed out (no speech heard).")
            self.notify_task_complete()
        except sr.UnknownValueError:
            print("[WakeDetector] Speech not understood.")
            self.notify_task_complete()
        except Exception as e:
            print(f"[WakeDetector] Command capture error: {e}")
            self.notify_task_complete()
        finally:
            self.is_recording_command = False

    def trigger_wake_manually(self):
        """Allows testing or UI trigger button without waiting for voice."""
        print("[WakeDetector] Manual wake triggered via UI / Hotkey.")
        self._trigger_on_wake("", is_interruption=True)
        def _bg_record():
            try:
                with sr.Microphone() as source:
                    self._record_next_command(source)
            except Exception as e:
                print(f"[WakeDetector] Manual record error: {e}")
        threading.Thread(target=_bg_record, daemon=True).start()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.is_busy = False
        target = self._listen_porcupine if self.use_porcupine else self._listen_continuous_sr
        self.listen_thread = threading.Thread(target=target, daemon=True, name="UltronWakeListener")
        self.listen_thread.start()

    def stop(self):
        self.is_running = False
        self.is_busy = False
        if self.porcupine:
            try:
                self.porcupine.delete()
            except Exception:
                pass
