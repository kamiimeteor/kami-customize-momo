import json


VOICES = [
    {
        "voice": "alloy",
        "style": "balanced neutral",
        "fit": "safe baseline, less character",
    },
    {
        "voice": "ash",
        "style": "lower, calm, restrained",
        "fit": "more grounded, less playful",
    },
    {
        "voice": "ballad",
        "style": "softer and more expressive",
        "fit": "warmer, slower, more emotional",
    },
    {
        "voice": "coral",
        "style": "clear, warm, conversational",
        "fit": "good default for momo",
    },
    {
        "voice": "echo",
        "style": "clean and direct",
        "fit": "more utilitarian assistant feel",
    },
    {
        "voice": "fable",
        "style": "more characterful",
        "fit": "more playful, stylized",
    },
    {
        "voice": "nova",
        "style": "bright and lively",
        "fit": "higher energy, more upbeat",
    },
    {
        "voice": "onyx",
        "style": "deeper and heavier",
        "fit": "more serious, less suitable for current momo",
    },
    {
        "voice": "sage",
        "style": "steady and reassuring",
        "fit": "good if you want calmer support energy",
    },
    {
        "voice": "shimmer",
        "style": "lighter and friendlier",
        "fit": "good if you want a softer companion tone",
    },
    {
        "voice": "verse",
        "style": "smooth and natural",
        "fit": "good candidate for Mandarin tests",
    },
]


if __name__ == "__main__":
    print(json.dumps(VOICES, ensure_ascii=False, indent=2))
