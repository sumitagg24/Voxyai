"""
AI text enhancement engine — uses Groq (free) or OpenAI GPT
Supports multilingual enhancement with language preservation
"""

import os
from typing import Optional
from ai.prompt_templates import get_enhancement_prompt, get_command_prompt
from ai.language_detector import language_detector
from utils.logger import log_info, log_error, log_debug, log_warning


class TextEnhancer:
    # Current (non-decommissioned) model candidates, tried in order.
    GROQ_MODELS = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o"]

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.openai_api_key = api_key
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        self.backend = None
        self.model = model or None
        self.custom_modes: dict = {}
        self._init_client()

    def _init_client(self):
        # Prefer Groq (free)
        if self.groq_api_key:
            try:
                from groq import Groq

                self.client = Groq(api_key=self.groq_api_key)
                self.backend = "groq"
                if not self.model:
                    self.model = self.GROQ_MODELS[0]
                log_info(f"Enhancer using Groq ({self.model})")
                return
            except Exception as e:
                log_error(f"Groq enhancer init failed: {e}")

        # Fall back to OpenAI
        if self.openai_api_key:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=self.openai_api_key)
                self.backend = "openai"
                if not self.model:
                    self.model = self.OPENAI_MODELS[0]
                log_info(f"Enhancer using OpenAI ({self.model})")
                return
            except Exception as e:
                log_error(f"OpenAI enhancer init failed: {e}")

        log_warning("No enhancement backend available — enhancement disabled")

    def _model_candidates(self) -> list:
        candidates = [self.model]
        candidates += self.GROQ_MODELS if self.backend == "groq" else self.OPENAI_MODELS
        seen = set()
        return [m for m in candidates if m and not (m in seen or seen.add(m))]

    def _chat(self, prompt: str, max_tokens: int = 1000) -> str:
        """Chat completion with automatic fallback to a current model."""
        last_error = None
        for model in self._model_candidates():
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=max_tokens,
                )
                if model != self.model:
                    log_info(f"Model fallback: {self.model} -> {model}")
                    self.model = model
                return (response.choices[0].message.content or "").strip()
            except Exception as e:  # noqa: BLE001 - try next candidate
                last_error = e
                log_warning(f"Model '{model}' failed: {e}")
        raise RuntimeError(
            f"All models failed for backend {self.backend}: {last_error}"
        )

    def set_custom_modes(self, custom_modes: dict):
        """Update custom enhancement modes."""
        self.custom_modes = custom_modes

    def enhance(self, text: str, mode: str = "formal", settings: dict = None) -> Optional[str]:
        if not self.client:
            log_warning("No enhancement client — returning original text")
            return text

        try:
            if not text or not text.strip():
                return text

            # Tier-based mode enforcement
            if settings:
                from config.constants import get_user_tier, TIER_ENHANCEMENT_MODES
                tier = get_user_tier(settings)
                allowed = TIER_ENHANCEMENT_MODES.get(tier, TIER_ENHANCEMENT_MODES["free"])
                if mode not in allowed:
                    log_info(f"Mode '{mode}' not allowed for tier '{tier}', falling back to formal")
                    mode = "formal"

            # Detect language from text
            lang_code, script, confidence = language_detector.detect_from_text(text)
            lang_name = language_detector.get_language_name(lang_code)

            log_debug(
                f"Language detected: {lang_name} ({lang_code}), "
                f"script: {script}, confidence: {confidence:.2f}"
            )

            # Check if enhancement is appropriate for this language
            if not language_detector.should_enhance(lang_code):
                log_info(
                    f"Language {lang_name} not well supported for enhancement, "
                    "returning original text"
                )
                return text

            # Get base prompt
            base_prompt = get_enhancement_prompt(mode, text, self.custom_modes)

            # If not English, add language preservation instructions
            if lang_code != "en":
                # Create language-specific prompt
                enhanced_prompt = f"""{base_prompt}

IMPORTANT: The text is in {lang_name}. DO NOT translate it to English.
- Keep the text in {lang_name}
- Preserve the original language and script
- Only improve grammar, punctuation, and clarity
- Do not change the language or translate
- Return text in the same {lang_name} script

Original text in {lang_name}: {text}"""

                prompt = enhanced_prompt
            else:
                prompt = base_prompt

            log_debug(
                f"Enhancing {lang_name} text with mode '{mode}' via {self.backend}"
            )

            result = self._chat(prompt, max_tokens=1000)
            log_info(
                f"Enhancement OK ({self.backend}): {len(result)} chars in {lang_name}"
            )
            return result

        except Exception as e:
            log_error(f"Enhancement error: {e}", exc_info=True)
            return text

    def process_command(self, text: str, command: str) -> Optional[str]:
        if not self.client:
            return text
        try:
            # Detect language
            lang_code, script, confidence = language_detector.detect_from_text(text)
            lang_name = language_detector.get_language_name(lang_code)

            prompt = get_command_prompt(command, text)

            # Add language preservation for non-English
            if lang_code != "en":
                prompt = f"""{prompt}

IMPORTANT: The text is in {lang_name}. DO NOT translate it to English.
- Keep the text in {lang_name}
- Preserve the original language and script
- Return result in the same {lang_name} script

Original text in {lang_name}: {text}"""

            return self._chat(prompt, max_tokens=2000)
        except Exception as e:
            log_error(f"Command processing error: {e}", exc_info=True)
            return text

    def translate(self, text: str, target_language: str) -> Optional[str]:
        """Translate text to target language."""
        if not self.client:
            return text
        try:
            # Detect source language
            lang_code, script, confidence = language_detector.detect_from_text(text)
            source_lang_name = language_detector.get_language_name(lang_code)

            # Get target language name
            target_lang_name = language_detector.get_language_name(target_language)

            prompt = f"""Translate the following text from {source_lang_name} to {target_lang_name}.
- Keep the meaning and tone intact
- Return only the translated text
- Do not add any explanations or notes

Source text ({source_lang_name}):
{text}

Translation ({target_lang_name}):"""

            result = self._chat(prompt, max_tokens=2000)
            log_info(
                f"Translation from {source_lang_name} to {target_lang_name}: {len(result)} chars"
            )
            return result
        except Exception as e:
            log_error(f"Translation error: {e}", exc_info=True)
            return text
