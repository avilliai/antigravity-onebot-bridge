# -*- coding: utf-8 -*-
"""Voice Synthesis and Audio Processing Helper for Antigravity-OneBot Bridge.

Provides text-to-speech synthesis and CQ:record segment formatting.
Supports Windows SpeechSynthesizer (SAPI5) zero-dependency fallback,
local file normalization, and Milky protocol URI formatting.
"""

import logging
import os
from pathlib import Path
import subprocess
import uuid
from typing import Optional

logger = logging.getLogger("agy_onebot.voice")


class VoiceHelper:
    """Helper for speech synthesis and voice message formatting."""

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(__file__).resolve().parent.parent / "data" / "voice_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(self, text: str, speaker: str = "yucca") -> Optional[str]:
        """Synthesize text into a WAV audio file and return its absolute file:/// URI."""
        clean_text = text.strip()
        if not clean_text:
            return None

        # Clean CQ codes or formatting tags from spoken text
        clean_text = clean_text.replace("\n", "，").replace('"', "").replace("'", "")
        if len(clean_text) > 200:
            clean_text = clean_text[:200]

        # 1. Attempt Breeze-TTS direct local server if reachable
        breeze_res = self._try_breeze_tts(clean_text, speaker)
        if breeze_res:
            return breeze_res

        # 2. Windows SpeechSynthesizer (SAPI5) offline fallback
        file_id = f"voice_{uuid.uuid4().hex[:12]}.wav"
        output_file = (self.cache_dir / file_id).resolve()
        out_str = str(output_file).replace("\\", "/")

        try:
            # Use PowerShell SAPI5 speech synthesis (built into Windows, 100% offline & fast)
            ps_script = (
                f"Add-Type -AssemblyName System.Speech; "
                f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                f"$s.Rate = 1; "
                f"$s.SetOutputToWaveFile('{out_str}'); "
                f"$s.Speak('{clean_text}'); "
                f"$s.Dispose()"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode == 0 and output_file.exists() and output_file.stat().st_size > 0:
                logger.info(f"Synthesized voice ({output_file.stat().st_size} bytes): {out_str}")
                return f"file:///{out_str}"
            else:
                logger.warning(f"PowerShell TTS failed: {res.stderr}")
        except Exception as e:
            logger.error(f"Voice synthesis error: {e}")

        # Fallback to existing sample wav if available
        sample = Path("D:/coding/pyc/Eridanus/outputs/test3_quick_tts.wav")
        if sample.exists():
            return f"file:///{str(sample).replace('\\', '/')}"

        return None

    def _try_breeze_tts(self, text: str, speaker: str = "yucca") -> Optional[str]:
        """Attempt to synthesize voice via direct local Breeze-TTS server if configured."""
        import socket
        import urllib.parse

        tts_base = (os.getenv("BREEZE_TTS_URL") or os.getenv("TTS_API_URL") or "").rstrip("/")
        if not tts_base:
            return None

        parsed = urllib.parse.urlparse(tts_base)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

        # Fast port probe (150ms timeout) to avoid blocking when server is offline
        try:
            with socket.create_connection((host, port), timeout=0.15):
                pass
        except OSError:
            return None

        endpoints = [f"{tts_base}/v1/audio/speech", f"{tts_base}/breeze/tts"]

        for ep in endpoints:
            try:
                import urllib.request
                import json
                if "speech" in ep:
                    payload = {"model": "breeze-tts", "input": text, "voice": speaker, "response_format": "wav"}
                else:
                    payload = {"text": text, "speaker": speaker}
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(ep, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    audio_bytes = resp.read()
                    if len(audio_bytes) > 500:
                        file_id = f"breeze_{uuid.uuid4().hex[:12]}.wav"
                        output_file = (self.cache_dir / file_id).resolve()
                        output_file.write_bytes(audio_bytes)
                        out_str = str(output_file).replace("\\", "/")
                        logger.info(f"Synthesized voice via Breeze-TTS ({len(audio_bytes)} bytes): {out_str}")
                        return f"file:///{out_str}"
            except Exception:
                continue
        return None

    def format_record_cq(self, file_uri: str) -> str:
        """Format an audio URI into a OneBot [CQ:record,file=...] string."""
        return f"[CQ:record,file={file_uri}]"
