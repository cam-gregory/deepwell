"""Rule-based document categorization.

Assigns every document a Top-Level Category and a Subcategory by matching a
keyword/phrase lexicon against its title, description and enrichment keywords.
The lexicon is derived from the corpus's own dominant vocabulary (iFixit-style
device-repair guides, MedlinePlus medical articles, and survival/preparedness
field manuals), so the resulting taxonomy reflects what is actually indexed.

Runs as a fast, deterministic, offline pass over the whole corpus — no LLM.
"""

import re

from app import config
from app import db

# Top-Level Category -> Subcategory -> trigger terms (matched on word boundaries,
# case-insensitively, against title + description + keywords). Multi-word phrases
# are matched as phrases. Order is only a mild tie-breaker; the best-scoring
# subcategory wins.
TAXONOMY: dict[str, dict[str, list[str]]] = {
    "Device Repair": {
        "Phones & Mobile Devices": [
            "iphone", "galaxy s", "galaxy note", "galaxy a", "galaxy sol",
            "galaxy j", "xperia", "pixel", "oneplus", "motorola", "moto g",
            "moto e", "nokia", "huawei", "xiaomi", "redmi", "oppo", "vivo",
            "blackberry", "htc", "lg g", "lg v", "zte", "alcatel", "nexus",
            "lumia", "smartphone", "cell phone", "sim card", "phone",
        ],
        "Laptops & Computers": [
            "laptop", "macbook", "thinkpad", "thinkbook", "notebook",
            "chromebook", "imac", "powerbook", "ibook", "framework laptop",
            "motherboard", "logic board", "hard drive", "ssd", "ram",
            "desktop", "dell", "lenovo", "asus", "acer", "msi", "computer",
            "vaio", "pavilion", "elitebook", "probook", "spectre", "satellite",
            "inspiron", "latitude", "xps", "ideapad", "aspire", "ultrabook",
            "sleekbook", "keyboard", "trackpad", "touchpad", "compaq",
            "presario", "clamshell", "mac mini", "mac pro",
        ],
        "Tablets & E-Readers": [
            "ipad", "galaxy tab", "tablet", "kindle", "fire tablet", "kobo",
            "nook", "remarkable", "surface pro", "surface go", "e-reader",
            "ereader",
        ],
        "Game Consoles & Controllers": [
            "xbox", "playstation", "ps3", "ps4", "ps5", "nintendo switch",
            "nintendo", "joy-con", "joycon", "wii", "gamecube", "game boy",
            "gameboy", "3ds", "2ds", "controller", "dualshock", "dualsense",
            "steam deck", "game console",
        ],
        "Cameras & Photography": [
            "camera", "nikon", "canon", "coolpix", "gopro", "dslr",
            "mirrorless", "camcorder", "lens", "point and shoot", "pentax",
            "olympus", "fujifilm", "lumix", "leica", "kodak", "polaroid",
            "shutter", "viewfinder",
        ],
        "TVs, Monitors & Projectors": [
            "television", "smart tv", "led tv", "lcd tv", "flat screen",
            "monitor", "projector", "vizio", "sceptre", "roku tv", "tv",
        ],
        "Media & Streaming Players": [
            "blu-ray", "bluray", "dvd player", "cd player", "roku",
            "chromecast", "apple tv", "set-top", "media player",
            "record player",
        ],
        "Audio & Headphones": [
            "speaker", "headphone", "headphones", "headset", "earbud",
            "earbuds", "airpods", "beats", "soundbar", "subwoofer",
            "amplifier", "turntable", "mixamp", "stereo", "earphone",
            "microphone",
        ],
        "Printers & 3D Printers": [
            "printer", "3d printer", "inkjet", "laserjet", "print head",
            "extruder", "filament", "scanner", "ender 3",
        ],
        "Home & Kitchen Appliances": [
            "refrigerator", "freezer", "washer", "washing machine", "dryer",
            "dishwasher", "microwave", "oven", "stove", "range", "whirlpool",
            "magic chef", "frigidaire", "kenmore", "maytag", "haier",
            "vacuum", "roomba", "dyson", "blender", "coffee maker", "toaster",
            "air conditioner", "hvac", "dehumidifier", "space heater",
            "water heater", "garbage disposal", "kettle", "mixer", "heater",
            "fan",
        ],
        "Power Tools & Yard Equipment": [
            "drill", "impact driver", "saw", "sander", "grinder",
            "angle grinder", "lawn mower", "mower", "string trimmer",
            "trimmer", "chainsaw", "leaf blower", "blower", "black and decker",
            "black+decker", "ridgid", "dewalt", "makita", "ryobi",
            "milwaukee", "craftsman", "power tool", "magneto", "hedge trimmer",
            "circular saw",
        ],
        "Vehicles & Automotive": [
            "engine", "brake", "alternator", "spark plug", "transmission",
            "oil change", "automotive", "carburetor", "radiator", "headlight",
            "taillight", "windshield wiper", "wiper", "bumper", "car battery",
            "ford", "chevrolet", "cadillac", "acura", "honda", "toyota",
            "pickup truck", "motorcycle",
        ],
        "Wearables & VR": [
            "apple watch", "smart watch", "smartwatch", "fitbit",
            "fitness tracker", "wristband", "galaxy watch", "gear live",
            "gear s", "garmin", "wear os", "vr headset", "oculus", "quest",
            "meta quest", "smart band",
        ],
        "Smart Home & Security": [
            "nest", "thermostat", "doorbell", "smart lock", "ring doorbell",
            "security camera", "alexa", "amazon echo", "google home",
            "smart home", "smart plug", "smart bulb",
        ],
    },
    "Health & Medicine": {
        "Conditions & Diseases": [
            "disease", "syndrome", "cancer", "infection", "disorder",
            "stenosis", "arrhythmia", "bronchitis", "asthma", "allergy",
            "allergies", "diabetes", "hypertension", "heart failure",
            "necrosis", "fissure", "cirrhosis", "spondylitis", "nephropathy",
            "anemia", "arthritis", "tumor", "regurgitation", "atherosclerosis",
            "injury", "ligament", "alkalosis", "acidosis", "aspergillosis",
            "anisocoria", "anorchia", "apnea",
        ],
        "Symptoms & Diagnosis": [
            "symptoms", "causes", "diagnosis", "signs and symptoms",
            "what to expect",
        ],
        "First Aid & Emergency Care": [
            "first aid", "wound", "bleeding", "cpr", "cardiopulmonary",
            "casualty", "trauma", "burn", "fracture", "tourniquet", "choking",
            "resuscitation", "combat casualty", "labor",
        ],
        "Tests & Procedures": [
            "biopsy", "angioplasty", "stent", "surgery", "blood test", "scan",
            "mri", "ct scan", "ultrasound", "alpha fetoprotein", "endoscopy",
            "aftercare", "x-ray", "angiography", "arteriogram", "angiogram",
            "apgar", "acth", "acid loading test", "acid-fast", "lab test",
            "hemoglobin", "aspiration", "anastomosis", "stimulation test",
        ],
        "Medications & Drugs": [
            "medication", "overdose", "antibiotic", "analgesic",
            "antidiarrheal", "dosage", "dosing", "painkiller", "prescription",
            "acetaminophen", "pain relief", "herbal", "alternative medicine",
        ],
        "Body, Aging & Wellness": [
            "aging", "bones", "muscles", "joints", "hearing loss", "nutrition",
            "pregnancy", "mental health", "hygiene", "adolescent",
            "amino acid", "aerobic", "anaerobic", "genetics", "care directive",
            "advance care",
        ],
        "Medical Reference & Anatomy": [
            "anatomy", "antibody", "antibodies", "bacteria", "medlineplus",
            "medical encyclopedia", "anterior", "building blocks", "aspartic",
        ],
    },
    "Emergency Preparedness & Survival": {
        "Kits & Everyday Carry": [
            "bug out", "bug-out", "go bag", "everyday carry", "edc",
            "survival kit", "first aid kit", "car emergency kit",
            "bug out bag", "checklist",
        ],
        "Navigation & Signaling": [
            "map reading", "land navigation", "compass", "visual signals",
            "signaling", "grid reference", "dead reckoning",
        ],
        "Food & Water": [
            "food storage", "ration", "foraging", "water purification",
            "emergency food", "safe water", "water safe", "water safety",
            "disinfection", "snare", "deadfall", "trapping", "drinking water",
        ],
        "Nuclear, Chemical & Radiological": [
            "nuclear", "radiological", "nbc", "cbrn", "fallout",
            "decontamination", "emp", "contamination", "detonation",
        ],
        "Fieldcraft, Shelter & Fire": [
            "fieldcraft", "shelter", "cold weather", "camouflage",
            "concealment", "survival", "evasion", "field hygiene",
            "sanitation", "bushcraft", "boy scout", "scouting", "scout",
        ],
        "Self-Defense & Combatives": [
            "combatives", "martial arts", "self-defense", "hand-to-hand",
            "grappling", "urban operations",
        ],
        "Planning & Response": [
            "emergency plan", "preparedness", "risk register", "risk index",
            "evacuation", "family survival", "emergency preparedness",
            "continuity", "national risk",
        ],
    },
    "Home, Garden & Self-Reliance": {
        "Gardening & Food Production": [
            "garden", "gardening", "vertical garden", "compost", "greenhouse",
            "permaculture", "homestead", "dehydrator", "maize", "milling",
            "seed",
        ],
        "Off-Grid & Sustainability": [
            "solar", "rainwater", "rain barrel", "off-grid", "off grid",
            "wind turbine", "biogas", "catch the rain", "greywater",
            "graywater", "pedal powered", "pedal generator", "generator",
            "natural paint", "biochar", "ecovillage",
        ],
        "Appropriate Technology": [
            "appropriate technology", "appropedia", "ecoladrillo", "neem",
            "bike trailer", "practical action", "tolocar", "reconstruction",
        ],
        "Home & Clothing Repairs": [
            "sew", "sewing", "stitch", "buttonhole", "zipper", "fabric",
            "garment", "shirt", "stain", "umbrella", "blind", "vertical blind",
            "curtain", "soundproofing", "airlock", "upholstery", "hemming",
        ],
    },
}

# Coverage fallbacks for documents that match no trigger, so nothing is left
# uncategorized. iFixit entries are routed by their article_path namespace;
# web/pdf docs (no article_path) are routed by their source domain / type.
_IFIXIT_GENERAL = ("Device Repair", "General Repair Guides")
_IFIXIT_DEVICE = ("Device Repair", "Devices & Models")
_IFIXIT_REFERENCE = ("Device Repair", "Reference & Tools")
_WEB_MEDICAL = ("Health & Medicine", "Medical Reference & Anatomy")
_WEB_APPROPRIATE = ("Home, Garden & Self-Reliance", "Appropriate Technology")
_SURVIVAL_OTHER = ("Emergency Preparedness & Survival", "Planning & Response")
_OTHER_FALLBACK = ("Uncategorized", None)

# Precompiled word-boundary alternation per subcategory: (category, sub, regex).
_COMPILED: list[tuple[str, str, re.Pattern]] = []
for _cat, _subs in TAXONOMY.items():
    for _sub, _terms in _subs.items():
        _alt = "|".join(re.escape(t) for t in sorted(_terms, key=len, reverse=True))
        _COMPILED.append((_cat, _sub, re.compile(rf"\b(?:{_alt})\b", re.IGNORECASE)))


def _fallback(source_type: str, article_path: str | None,
              source_file: str | None, zim_file: str | None) -> tuple[str, str | None]:
    """Assign a sensible category to a document that matched no keyword, using
    structural signals (ZIM namespace, source domain) so nothing is left out."""
    ap = article_path or ""
    zf = (zim_file or "").lower()
    if source_type == "zim":
        if ap.startswith("Device/"):
            return _IFIXIT_DEVICE
        if ap.startswith(("Info/", "Tools/")):
            return _IFIXIT_REFERENCE
        if "ifixit" in zf or ap.startswith(("Guide/", "Teardown/")):
            return _IFIXIT_GENERAL
        return _OTHER_FALLBACK
    if source_type == "web":
        sf = (source_file or "").lower()
        if "appropedia" in sf:
            return _WEB_APPROPRIATE
        if "trueprepper" in sf:
            return _SURVIVAL_OTHER
        return _WEB_MEDICAL
    if source_type == "pdf":
        return _SURVIVAL_OTHER
    return _OTHER_FALLBACK


def classify(title: str, description: str, keywords: str, source_type: str,
             article_path: str | None = None, source_file: str | None = None,
             zim_file: str | None = None) -> tuple[str, str | None]:
    """Return (category, subcategory) for one document. Title matches are
    weighted more heavily than description/keyword matches; documents that hit
    no trigger fall through to a structural fallback so all are categorized."""
    title = title or ""
    haystack = f"{title} {description or ''} {keywords or ''}"

    best_score = 0
    best: tuple[str, str] | None = None
    for cat, sub, pattern in _COMPILED:
        score = len(pattern.findall(haystack))
        if pattern.search(title):
            score += 3
        if score > best_score:
            best_score, best = score, (cat, sub)

    if best is not None:
        return best
    return _fallback(source_type, article_path, source_file, zim_file)


def categorize_all() -> None:
    """Assign category/subcategory to every document, using each document's
    title/description plus its chunks' aggregated keywords. Idempotent."""
    db.init_db()  # ensures the category/subcategory columns exist
    with db.connect() as conn:
        keywords_by_doc: dict[int, list[str]] = {}
        for doc_id, kw in conn.execute(
            "SELECT document_id, keywords FROM chunks WHERE keywords IS NOT NULL"
        ):
            if doc_id is None:
                continue
            bucket = keywords_by_doc.setdefault(doc_id, [])
            if len(bucket) < 40:  # cap: a few chunks' keywords are plenty of signal
                bucket.append(kw.replace("[", " ").replace("]", " ").replace('"', " "))

        docs = conn.execute(
            "SELECT id, display_title, title, description, source_type, "
            "article_path, source_file, zim_file FROM documents"
        ).fetchall()

        updates = []
        for row in docs:
            kw_text = " ".join(keywords_by_doc.get(row["id"], []))
            cat, sub = classify(
                row["display_title"] or row["title"] or "",
                row["description"] or "",
                kw_text,
                row["source_type"],
                row["article_path"],
                row["source_file"],
                row["zim_file"],
            )
            updates.append((cat, sub, row["id"]))

        conn.executemany(
            "UPDATE documents SET category = ?, subcategory = ? WHERE id = ?", updates
        )

    print(f"Categorized {len(updates)} documents into {config.DB_PATH}")


if __name__ == "__main__":
    categorize_all()
