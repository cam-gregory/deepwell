import json
import re
from collections import Counter

from app import config

STOP_WORDS = {
    "the", "and", "that", "this", "with", "from", "into",
    "for", "are", "was", "were", "will", "would", "could",
    "should", "have", "has", "had", "not", "but", "you",
    "your", "their", "they", "them", "then", "than", "when",
    "where", "what", "which", "while", "who", "how", "why",
    "can", "may", "also", "such", "these", "those", "been",
    "being", "its", "our", "out", "use", "used", "using",
    "more", "most", "some", "any", "each", "other", "about",
    "over", "under", "after", "before", "between", "during",
    "through", "because", "there", "here", "very", "only",
    "same", "per", "one", "two",
}

def clean_word(word: str) -> str:
    return re.sub(r"[^a-zA-Z0-9-]", "", word).lower()

def extract_keywords(text: str, limit: int = 8) -> list[str]:
    words = [clean_word(word) for word in text.split()]
    words = [
        word
        for word in words
        if len(word) >= 4 and word not in STOP_WORDS and not word.isdigit()
    ]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]

def classify_content(text: str) -> str:
    lower = text.lower()

    procedure_signals = [
        "step 1", "step one", "first,", "next,", "then,",
        "instructions", "procedure", "follow these steps",
    ]
    warning_signals = [
        "warning", "caution", "danger", "do not", "never", "hazard", "unsafe",
    ]
    definition_signals = [
        "is defined as", "refers to", "means that",
        "is the process of", "is a method of",
    ]
    science_signals = [
        "because", "mechanism", "temperature", "chemical", "biological",
        "bacteria", "virus", "pathogen", "molecule", "reaction",
    ]

    if any(signal in lower for signal in warning_signals):
        return "warning"
    if any(signal in lower for signal in procedure_signals):
        return "procedure"
    if any(signal in lower for signal in definition_signals):
        return "definition"
    if sum(signal in lower for signal in science_signals) >= 2:
        return "scientific_explanation"
    return "general_information"

def estimate_difficulty(text: str) -> str:
    words = text.split()
    if not words:
        return "basic"
    long_words = [word for word in words if len(clean_word(word)) >= 10]
    long_word_ratio = len(long_words) / len(words)
    if long_word_ratio > 0.15:
        return "advanced"
    if long_word_ratio > 0.08:
        return "intermediate"
    return "basic"

def enrich_chunk(chunk: dict) -> dict:
    enriched = dict(chunk)
    enriched["metadata"] = {
        "keywords": extract_keywords(chunk["text"]),
        "content_type": classify_content(chunk["text"]),
        "difficulty": estimate_difficulty(chunk["text"]),
    }
    return enriched

def process_file(json_path) -> None:
    with json_path.open("r", encoding="utf-8") as file:
        chunks = json.load(file)

    enriched_chunks = [enrich_chunk(chunk) for chunk in chunks]

    config.ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = config.ENRICHED_DIR / json_path.name.replace(
        "_chunks.json", "_enriched.json"
    )

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(enriched_chunks, file, ensure_ascii=False, indent=2)

    print(f"{json_path.name}: {len(enriched_chunks)} chunks enriched -> {output_path}")

def enrich_all() -> None:
    files = list(config.CHUNKS_DIR.glob("*_chunks.json"))
    if not files:
        print(f"No chunk files found in {config.CHUNKS_DIR}")
        return
    for json_path in files:
        process_file(json_path)

if __name__ == "__main__":
    enrich_all()
