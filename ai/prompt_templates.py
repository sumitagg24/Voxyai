"""
Multilingual prompt templates for AI text enhancement
Supports all global languages with language preservation
"""

ENHANCEMENT_PROMPTS = {
    "formal": """You are a professional writing assistant. Take the following raw transcribed text and enhance it to be formal, professional, and polished.  # noqa: E501
    - Fix grammar and punctuation
    - Remove filler words (um, uh, like, you know)
    - Improve sentence structure
    - Use appropriate vocabulary for the language
    - Keep the original meaning intact
    - PRESERVE THE ORIGINAL LANGUAGE - DO NOT TRANSLATE

    Raw text: {text}

    Return ONLY the enhanced text in the same language, nothing else.""",
    "casual": """You are a friendly writing assistant. Take the following raw transcribed text and enhance it to be casual, friendly, and conversational.  # noqa: E501
    - Fix grammar and punctuation
    - Remove filler words (um, uh, like, you know)
    - Keep a friendly tone
    - Use natural language
    - Keep the original meaning intact
    - PRESERVE THE ORIGINAL LANGUAGE - DO NOT TRANSLATE

    Raw text: {text}

    Return ONLY the enhanced text in the same language, nothing else.""",
    "technical": """You are a technical writing specialist. Take the following raw transcribed text and enhance it to be precise, technical, and clear.  # noqa: E501
    - Fix grammar and punctuation
    - Remove filler words (um, uh, like, you know)
    - Use appropriate technical terminology for the language
    - Improve clarity and precision
    - Structure for technical audience
    - Keep the original meaning intact
    - PRESERVE THE ORIGINAL LANGUAGE - DO NOT TRANSLATE

    Raw text: {text}

    Return ONLY the enhanced text in the same language, nothing else.""",
    "concise": """You are a concise writing specialist. Take the following raw transcribed text and make it brief, clear, and to the point.  # noqa: E501
    - Fix grammar and punctuation
    - Remove filler words (um, uh, like, you know)
    - Eliminate redundancy
    - Use short, clear sentences
    - Keep only essential information
    - Keep the original meaning intact
    - PRESERVE THE ORIGINAL LANGUAGE - DO NOT TRANSLATE

    Raw text: {text}

    Return ONLY the enhanced text in the same language, nothing else.""",
    "creative": """You are a creative writing assistant. Take the following raw transcribed text and enhance it to be engaging, creative, and interesting.  # noqa: E501
    - Fix grammar and punctuation
    - Remove filler words (um, uh, like, you know)
    - Add engaging language appropriate for the culture
    - Improve flow and rhythm
    - Make it more interesting
    - Keep the original meaning intact
    - PRESERVE THE ORIGINAL LANGUAGE - DO NOT TRANSLATE

    Raw text: {text}

    Return ONLY the enhanced text in the same language, nothing else.""",
}

COMMAND_PROMPTS = {
    "email": """Convert the following text into a professional email. Include appropriate greeting, body, and closing.  # noqa: E501

    Content: {text}

    Return ONLY the formatted email, nothing else.""",
    "bullet_points": """Convert the following text into a clear, concise bullet point list.

    Content: {text}

    Return ONLY the bullet points, nothing else.""",
    "summary": """Create a brief summary of the following text in 2-3 sentences.

    Content: {text}

    Return ONLY the summary, nothing else.""",
    "code_comment": """Convert the following text into a clear code comment.

    Content: {text}

    Return ONLY the code comment, nothing else.""",
}


def get_enhancement_prompt(mode: str, text: str, custom_modes: dict = None) -> str:
    """
    Get enhancement prompt for given mode.
    Checks custom_modes first, then built-in ENHANCEMENT_PROMPTS.
    """
    if custom_modes and mode in custom_modes:
        template = custom_modes[mode]
        # Support both {text} placeholder and bare prompts
        if "{text}" in template:
            return template.format(text=text)
        return f"{template}\n\n{text}"

    template = ENHANCEMENT_PROMPTS.get(mode, ENHANCEMENT_PROMPTS["formal"])
    return template.format(text=text)


def get_command_prompt(command: str, text: str) -> str:
    """Get command prompt for given command"""
    template = COMMAND_PROMPTS.get(command, COMMAND_PROMPTS["email"])
    return template.format(text=text)
