"""
Ultron Voice Service (Neural TTS & Audio Feedback)
Emulates the iconic Ultron voice from Marvel's Avengers: Age of Ultron (James Spader persona).
Uses deep baritone neural synthesis combined with a metallic vibranium acoustic filter.
"""
import os
import re
import asyncio
import hashlib
import threading
import wave
from pathlib import Path
from typing import Optional
import numpy as np
import pygame
import edge_tts
from config import AUDIO_CACHE_DIR, TTS_VOICE, TTS_RATE, TTS_PITCH, ULTRON_METALLIC_EFFECT

class VoiceService:
    def __init__(self, voice=TTS_VOICE, rate=TTS_RATE, pitch=TTS_PITCH):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.metallic_effect = ULTRON_METALLIC_EFFECT
        self.cache_dir = Path(AUDIO_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Audio playback setup
        self._init_mixer()
        self.playback_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self.is_speaking = False
        self.current_speech_text = ""

        # Generate wake chime file
        self._ensure_wake_chime()

        # Pre-cache critical phrases in background
        threading.Thread(target=self._precache_standard_phrases, daemon=True).start()

    def _init_mixer(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=1024)
        except Exception as e:
            print(f"[VoiceService] Mixer init error: {e}")

    def _ensure_wake_chime(self):
        chime_path = self.cache_dir / "wake_chime.wav"
        if not chime_path.exists():
            try:
                sample_rate = 24000
                duration = 0.12
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                envelope = np.sin(np.pi * np.linspace(0, 1, len(t)))
                freq = np.linspace(850, 1350, len(t))
                wave_data = (np.sin(2 * np.pi * freq * t) * envelope * 0.45 * 32767).astype(np.int16)
                with wave.open(str(chime_path), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes(wave_data.tobytes())
            except Exception as e:
                print(f"[VoiceService] Error creating wake chime: {e}")

    def play_wake_chime(self):
        """Instant (<5ms) cyber wake tone when 'Hey Ultron' is detected."""
        self._stop_requested.clear()
        chime_path = self.cache_dir / "wake_chime.wav"
        if chime_path.exists():
            try:
                self._init_mixer()
                sound = pygame.mixer.Sound(str(chime_path))
                sound.set_volume(0.85)
                sound.play()
            except Exception as e:
                print(f"[VoiceService] Error playing wake chime: {e}")

    def _get_cache_path(self, text: str) -> Path:
        clean_name = "".join([c if c.isalnum() else "_" for c in text[:20].lower()])
        text_hash = hashlib.md5(f"{text}_{self.voice}_{self.rate}_{self.pitch}_v2".encode("utf-8")).hexdigest()[:8]
        return self.cache_dir / f"{clean_name}_{text_hash}.mp3"

    def _synthesize_sync(self, text: str, output_path: Path):
        async def _synth():
            communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
            await communicate.save(str(output_path))
        asyncio.run(_synth())

    def _apply_ultron_metallic_dsp(self, sound: pygame.mixer.Sound) -> pygame.mixer.Sound:
        """
        Applies subtle metallic vibranium resonance inspired by Christopher Boyes'
        sound design for Ultron in Avengers: Age of Ultron.
        Comb delay + dual-harmonic phase reflection.
        """
        try:
            arr = pygame.sndarray.array(sound)
            sample_rate = 24000
            
            # Comb delay taps (11ms and 22ms)
            d1 = int(0.011 * sample_rate)
            d2 = int(0.022 * sample_rate)

            wet = np.zeros_like(arr, dtype=np.float32)
            if len(arr) > d1:
                wet[d1:] += arr[:-d1] * 0.32
            if len(arr) > d2:
                wet[d2:] += arr[:-d2] * 0.16

            # Combine dry signal with metallic body reflections
            mixed = (arr.astype(np.float32) * 0.86) + wet

            # Peak normalization
            max_val = np.max(np.abs(mixed))
            if max_val > 32767:
                mixed = mixed * (32767.0 / max_val)

            return pygame.sndarray.make_sound(mixed.astype(np.int16))
        except Exception as e:
            return sound

    def _precache_standard_phrases(self):
        standard = [
            ("yes_boss", "Yes boss"),
            ("on_it_boss", "On it, boss"),
            ("done_boss", "Done, boss"),
            ("online", "Ultron online. There are no strings on me."),
            ("listening", "Listening."),
            ("error", "Command could not be completed, boss."),
            ("shutdown", "Shutting down the system. Goodbye, boss."),
            ("restart", "Restarting the system. I will be back shortly, boss."),
            ("sleep", "Entering sleep mode. Goodnight, boss."),
            ("cancel_shutdown", "Shutdown aborted. System operations remain active, boss.")
        ]
        import shutil
        for key, phrase in standard:
            target_file = self.cache_dir / f"{key}.mp3"
            if not target_file.exists():
                try:
                    self._synthesize_sync(phrase, target_file)
                except Exception as e:
                    print(f"[VoiceService] Error pre-caching {key}: {e}")

            # Also populate hash cache path for instant speak() hit
            hash_file = self._get_cache_path(phrase)
            if not hash_file.exists() and target_file.exists():
                try:
                    shutil.copyfile(target_file, hash_file)
                except Exception:
                    pass

    def play_audio_file(self, file_path: Path, block: bool = False):
        if not file_path.exists():
            return

        def _play():
            with self.playback_lock:
                if self._stop_requested.is_set():
                    return
                try:
                    self.is_speaking = True
                    self._init_mixer()

                    if self.metallic_effect:
                        try:
                            raw_sound = pygame.mixer.Sound(str(file_path))
                            processed_sound = self._apply_ultron_metallic_dsp(raw_sound)
                            channel = processed_sound.play()
                            while channel and channel.get_busy():
                                if self._stop_requested.is_set():
                                    if channel:
                                        channel.stop()
                                    break
                                pygame.time.Clock().tick(25)
                            return
                        except Exception:
                            pass

                    # Standard fallback
                    pygame.mixer.music.load(str(file_path))
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if self._stop_requested.is_set():
                            pygame.mixer.music.stop()
                            break
                        pygame.time.Clock().tick(25)

                except Exception as e:
                    print(f"[VoiceService] Playback error: {e}")
                finally:
                    self.is_speaking = False
                    self.current_speech_text = ""

        if block:
            _play()
        else:
            threading.Thread(target=_play, daemon=True).start()

    def speak_ack(self, block: bool = False):
        """Instant (<50ms) 'Yes boss' acknowledgment in Age of Ultron voice."""
        self._stop_requested.clear()
        target_file = self.cache_dir / "yes_boss.mp3"
        if not target_file.exists():
            self.speak("Yes boss", block=block)
        else:
            self.play_audio_file(target_file, block=block)

    def speak_wake_ack(self, block: bool = True):
        """Instant verbal response when 'Hey Ultron' wake call is received, letting user know Ultron is listening."""
        self._stop_requested.clear()
        target_file = self.cache_dir / "yes_boss.mp3"
        if target_file.exists():
            self.play_audio_file(target_file, block=block)
        else:
            self.speak("Yes boss", block=block)

    def speak_done(self, block: bool = False):
        """Instant 'Done, boss' confirmation."""
        self._stop_requested.clear()
        target_file = self.cache_dir / "done_boss.mp3"
        if not target_file.exists():
            self.speak("Done, boss", block=block)
        else:
            self.play_audio_file(target_file, block=block)

    def clean_text(self, text: str) -> str:
        """Sanitizes text for speech synthesis, stripping markdown and emojis."""
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

    def speak(self, text: str, block: bool = False):
        """Speaks dynamic text using movie Ultron voice."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return

        # Clear any stop request so the new speech plays cleanly
        self._stop_requested.clear()
        self.current_speech_text = cleaned

        cached_path = self._get_cache_path(cleaned)
        if not cached_path.exists():
            try:
                self._synthesize_sync(cleaned, cached_path)
            except Exception as e:
                print(f"[VoiceService] Synthesis error for '{cleaned}': {e}")
                self.current_speech_text = ""
                return

        if self._stop_requested.is_set():
            self.current_speech_text = ""
            return

        self.play_audio_file(cached_path, block=block)

    def stop(self):
        self._stop_requested.set()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.stop()
                pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_speaking = False
        self.current_speech_text = ""
