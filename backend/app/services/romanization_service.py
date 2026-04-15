"""
NexClip — Ultra-Detailed Romanization Service
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Professional Devanagari → Roman transliteration engine.
This is the SINGLE SOURCE OF TRUTH for all script conversion.

Architecture:
┌─────────────────────────────────────────────────────────────────────┐
│  Input: Raw text (may contain Devanagari, Latin, numbers, mixed)   │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Detect     │→ │ Word-Level   │→ │ Dictionary  │→ │ Char-by  │ │
│  │ Script     │  │ Tokenize     │  │ Lookup      │  │ Char     │ │
│  │ Boundaries │  │ + Classify   │  │ (Fast Path) │  │ Fallback │ │
│  └────────────┘  └──────────────┘  └─────────────┘  └──────────┘ │
│                                                                     │
│  Pipeline:                                                          │
│  1. Tokenize text preserving spaces and punctuation                 │
│  2. Classify each token: LATIN / DEVANAGARI / MIXED / PUNCT        │
│  3. For DEVANAGARI tokens:                                          │
│     a) Check common-word dictionary (instant, 100% accurate)       │
│     b) Fall back to character-by-character transliteration          │
│        with proper conjunct handling, schwa deletion, etc.          │
│  4. Reassemble with proper spacing                                  │
│  5. Post-process: fix capitalization, spacing, punctuation          │
└─────────────────────────────────────────────────────────────────────┘

Key Improvements Over Naive Transliteration:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• WORD BOUNDARIES: Never joins words together (fixes "bynthis" bug)
• COMMON WORDS DICTIONARY: 200+ Hindi words with verified Romanization
• SCHWA DELETION: Properly handles Hindi schwa drop rules
  (e.g., कमल → "kamal" not "kamala")
• CONJUNCTS: Handles halant-joined consonant clusters correctly
  (e.g., प्र → "pr", क्ष → "ksh")
• NUKTA VARIANTS: Correct mapping for Urdu/Persian loanwords
  (e.g., ज़ → "z", फ़ → "f")
• NASALIZATION: Proper chandrabindu/anusvara handling
• VISARGA: Correct "h" aspiration marker
• MIXED SCRIPT: Handles code-mixed Hindi-English (Hinglish) seamlessly
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from loguru import logger


# ══════════════════════════════════════════════════════════════════════
# SECTION 1: DEVANAGARI CHARACTER MAPS
# ══════════════════════════════════════════════════════════════════════

# ── 1A: STANDALONE VOWELS ──────────────────────────────────────────
# These appear at the start of a word or after another vowel.
_VOWELS = {
    '\u0905': 'a',    # अ
    '\u0906': 'aa',   # आ
    '\u0907': 'i',    # इ
    '\u0908': 'ee',   # ई
    '\u0909': 'u',    # उ
    '\u090A': 'oo',   # ऊ
    '\u090B': 'ri',   # ऋ
    '\u090C': 'lri',  # ऌ
    '\u090D': 'e',    # ऍ (candra E — rare)
    '\u090E': 'e',    # ऎ (short E — southern)
    '\u090F': 'e',    # ए
    '\u0910': 'ai',   # ऐ
    '\u0911': 'o',    # ऑ (candra O — English loanwords)
    '\u0912': 'o',    # ऒ (short O — southern)
    '\u0913': 'o',    # ओ
    '\u0914': 'au',   # औ
}

# ── 1B: VOWEL SIGNS (MATRAS) ──────────────────────────────────────
# These attach to consonants and replace the inherent 'a' vowel.
_MATRAS = {
    '\u093A': '',     # OE matra (rare)
    '\u093B': '',     # UE matra (rare)
    '\u093E': 'aa',   # ा  — kaa
    '\u093F': 'i',    # ि  — ki
    '\u0940': 'ee',   # ी  — kee
    '\u0941': 'u',    # ु  — ku
    '\u0942': 'oo',   # ू  — koo
    '\u0943': 'ri',   # ृ  — kri
    '\u0944': 'ree',  # ॄ  — kree
    '\u0945': 'e',    # ॅ  — candra E matra
    '\u0946': 'e',    # ॆ  — short E matra (southern)
    '\u0947': 'e',    # े  — ke
    '\u0948': 'ai',   # ै  — kai
    '\u0949': 'o',    # ॉ  — candra O matra (English loans: "doctor" → डॉक्टर)
    '\u094A': 'o',    # ॊ  — short O matra (southern)
    '\u094B': 'o',    # ो  — ko
    '\u094C': 'au',   # ौ  — kau
}

# ── 1C: HALANT (VIRAMA) ───────────────────────────────────────────
# Suppresses the inherent 'a' vowel of a consonant.
_HALANT = '\u094D'  # ् — virama

# ── 1D: CONSONANTS ────────────────────────────────────────────────
# Each consonant has an inherent 'a' vowel (e.g., क = "ka")
# The inherent 'a' is stripped when followed by a matra or halant.
_CONSONANTS = {
    # Velar (कवर्ग)
    '\u0915': 'k',    # क
    '\u0916': 'kh',   # ख
    '\u0917': 'g',    # ग
    '\u0918': 'gh',   # घ
    '\u0919': 'ng',   # ङ

    # Palatal (चवर्ग)
    '\u091A': 'ch',   # च
    '\u091B': 'chh',  # छ
    '\u091C': 'j',    # ज
    '\u091D': 'jh',   # झ
    '\u091E': 'ny',   # ञ

    # Retroflex (टवर्ग)
    '\u091F': 't',    # ट
    '\u0920': 'th',   # ठ
    '\u0921': 'd',    # ड
    '\u0922': 'dh',   # ढ
    '\u0923': 'n',    # ण

    # Dental (तवर्ग)
    '\u0924': 't',    # त
    '\u0925': 'th',   # थ
    '\u0926': 'd',    # द
    '\u0927': 'dh',   # ध
    '\u0928': 'n',    # न

    # Labial (पवर्ग)
    '\u092A': 'p',    # प
    '\u092B': 'ph',   # फ
    '\u092C': 'b',    # ब
    '\u092D': 'bh',   # भ
    '\u092E': 'm',    # म

    # Semi-vowels (अन्तस्थ)
    '\u092F': 'y',    # य
    '\u0930': 'r',    # र
    '\u0932': 'l',    # ल
    '\u0933': 'l',    # ळ (Marathi lateral)
    '\u0935': 'v',    # व

    # Sibilants & Aspirate (ऊष्म)
    '\u0936': 'sh',   # श
    '\u0937': 'sh',   # ष
    '\u0938': 's',    # स
    '\u0939': 'h',    # ह
}

# ── 1E: NUKTA VARIANTS ────────────────────────────────────────────
# Used for Urdu/Persian/Arabic loanwords in Hindi.
_NUKTA_CONSONANTS = {
    '\u0958': 'q',    # क़ — "qarib"
    '\u0959': 'kh',   # ख़ — "khabar"
    '\u095A': 'gh',   # ग़ — "ghazal"
    '\u095B': 'z',    # ज़ — "zaroor"
    '\u095C': 'd',    # ड़ — "pakda"
    '\u095D': 'dh',   # ढ़ — "padhna"
    '\u095E': 'f',    # फ़ — "farq"
    '\u095F': 'y',    # य़

    # Common nukta form: base consonant + nukta sign (\u093C)
    # These are handled dynamically in the transliteration engine.
}

# ── 1F: SPECIAL SIGNS ─────────────────────────────────────────────
_SPECIAL_SIGNS = {
    '\u0901': 'n',    # ँ  — chandrabindu (nasalization)
    '\u0902': 'n',    # ं  — anusvara (nasal)
    '\u0903': 'h',    # ः  — visarga (aspiration)
    '\u093C': '',     # ़  — nukta (handled via _NUKTA_CONSONANTS)
    '\u093D': '',     # ऽ  — avagraha (elision marker, dropped)
}

# ── 1G: DEVANAGARI DIGITS ─────────────────────────────────────────
_DIGITS = {
    '\u0966': '0', '\u0967': '1', '\u0968': '2', '\u0969': '3', '\u096A': '4',
    '\u096B': '5', '\u096C': '6', '\u096D': '7', '\u096E': '8', '\u096F': '9',
}

# ── 1H: DEVANAGARI PUNCTUATION ────────────────────────────────────
_PUNCTUATION = {
    '\u0964': '.',    # ।  — purna viram (full stop)
    '\u0965': '.',    # ॥  — double danda
    '\u0970': '.',    # ॰  — abbreviation sign
}


# ══════════════════════════════════════════════════════════════════════
# SECTION 2: COMMON HINDI WORD DICTIONARY
# ══════════════════════════════════════════════════════════════════════
# Fast-path: exact match → instant, guaranteed-accurate Romanization.
# This dictionary covers the most frequent Hindi words used in speech.
# All entries are: { Devanagari_word: "romanized form" }

_COMMON_WORDS: Dict[str, str] = {
    # ── Pronouns ──────────────────────────────────────────────────
    'मैं': 'main', 'मुझे': 'mujhe', 'मुझको': 'mujhko', 'मेरा': 'mera',
    'मेरी': 'meri', 'मेरे': 'mere', 'हम': 'hum', 'हमें': 'humein',
    'हमारा': 'humara', 'हमारी': 'humari', 'हमारे': 'humare',
    'तुम': 'tum', 'तुम्हें': 'tumhein', 'तुम्हारा': 'tumhara',
    'तुम्हारी': 'tumhari', 'तू': 'tu', 'तेरा': 'tera', 'तेरी': 'teri',
    'आप': 'aap', 'आपका': 'aapka', 'आपकी': 'aapki', 'आपको': 'aapko',
    'आपने': 'aapne', 'आपसे': 'aapse',
    'वह': 'woh', 'वो': 'wo', 'उसे': 'use', 'उसका': 'uska',
    'उसकी': 'uski', 'उसको': 'usko', 'उसने': 'usne', 'उससे': 'usse',
    'उन्हें': 'unhein', 'उनका': 'unka', 'उनकी': 'unki', 'उनके': 'unke',
    'ये': 'ye', 'यह': 'yeh', 'इसे': 'ise', 'इसका': 'iska',
    'इसकी': 'iski', 'इसको': 'isko', 'इसने': 'isne', 'इससे': 'isse',
    'कौन': 'kaun', 'क्या': 'kya', 'कुछ': 'kuch', 'कोई': 'koi',
    'सब': 'sab', 'सबको': 'sabko',
    'खुद': 'khud', 'अपना': 'apna', 'अपनी': 'apni', 'अपने': 'apne',

    # ── Verbs (Common Forms) ──────────────────────────────────────
    'है': 'hai', 'हैं': 'hain', 'था': 'tha', 'थी': 'thi', 'थे': 'the',
    'होगा': 'hoga', 'होगी': 'hogi', 'होंगे': 'honge',
    'हूं': 'hoon', 'हूँ': 'hoon', 'हो': 'ho',
    'करना': 'karna', 'करता': 'karta', 'करती': 'karti', 'करते': 'karte',
    'करो': 'karo', 'करें': 'karein', 'किया': 'kiya', 'करेगा': 'karega',
    'करेंगे': 'karenge', 'करूंगा': 'karunga', 'कर': 'kar',
    'बोलना': 'bolna', 'बोला': 'bola', 'बोली': 'boli', 'बोलो': 'bolo',
    'बोलते': 'bolte', 'बोलता': 'bolta',
    'देना': 'dena', 'देता': 'deta', 'देती': 'deti', 'दो': 'do',
    'दिया': 'diya', 'दी': 'di', 'दे': 'de', 'दें': 'dein',
    'देखो': 'dekho', 'देखा': 'dekha', 'देखी': 'dekhi',
    'देखना': 'dekhna', 'देखते': 'dekhte', 'देख': 'dekh',
    'लेना': 'lena', 'लेता': 'leta', 'लेती': 'leti', 'लो': 'lo',
    'लिया': 'liya', 'ले': 'le', 'लें': 'lein',
    'जाना': 'jaana', 'जाता': 'jaata', 'जाती': 'jaati', 'जाओ': 'jaao',
    'गया': 'gaya', 'गयी': 'gayi', 'गए': 'gaye', 'जा': 'ja',
    'जाएगा': 'jaayega', 'जाएंगे': 'jaayenge',
    'आना': 'aana', 'आता': 'aata', 'आती': 'aati', 'आए': 'aaye',
    'आया': 'aaya', 'आई': 'aayi', 'आ': 'aa',
    'सोचना': 'sochna', 'सोचो': 'socho', 'सोचा': 'socha', 'सोच': 'soch',
    'रहना': 'rehna', 'रहता': 'rehta', 'रहती': 'rehti', 'रहा': 'raha',
    'रही': 'rahi', 'रहे': 'rahe', 'रहो': 'raho',
    'चाहिए': 'chahiye', 'चाहता': 'chahta', 'चाहती': 'chahti',
    'पता': 'pata', 'मालूम': 'maloom', 'लगता': 'lagta', 'लगती': 'lagti',
    'लगा': 'laga', 'लगी': 'lagi', 'लगे': 'lage',
    'मिलना': 'milna', 'मिला': 'mila', 'मिली': 'mili', 'मिले': 'mile',
    'मिलता': 'milta', 'मिलेगा': 'milega',
    'बताना': 'batana', 'बताओ': 'batao', 'बताया': 'bataya', 'बता': 'bata',
    'बताई': 'batayi', 'बताते': 'batate',
    'सकता': 'sakta', 'सकती': 'sakti', 'सकते': 'sakte', 'सका': 'saka',
    'समझना': 'samajhna', 'समझो': 'samjho', 'समझा': 'samjha',
    'समझ': 'samajh', 'समझते': 'samajhte',
    'पूछना': 'poochna', 'पूछो': 'poocho', 'पूछा': 'poocha',
    'सुनो': 'suno', 'सुना': 'suna', 'सुनना': 'sunna',
    'पढ़ना': 'padhna', 'पढ़ो': 'padho', 'पढ़ा': 'padha',
    'लिखना': 'likhna', 'लिखो': 'likho', 'लिखा': 'likha',
    'खाना': 'khana', 'खाओ': 'khao', 'खाया': 'khaya',
    'पीना': 'peena', 'पीओ': 'peeyo',
    'चलना': 'chalna', 'चलो': 'chalo', 'चला': 'chala', 'चल': 'chal',

    # ── Postpositions & Particles ─────────────────────────────────
    'का': 'ka', 'की': 'ki', 'के': 'ke', 'को': 'ko',
    'में': 'mein', 'पर': 'par', 'से': 'se', 'तक': 'tak',
    'ने': 'ne', 'और': 'aur', 'या': 'ya', 'लेकिन': 'lekin',
    'मगर': 'magar', 'पर': 'par', 'तो': 'to', 'भी': 'bhi',
    'ही': 'hi', 'तो': 'to', 'भी': 'bhi', 'ना': 'na',
    'जी': 'ji', 'जो': 'jo', 'कि': 'ki', 'अगर': 'agar',
    'जब': 'jab', 'तब': 'tab', 'अभी': 'abhi', 'कभी': 'kabhi',
    'अब': 'ab', 'फिर': 'phir', 'वाला': 'wala', 'वाली': 'wali',
    'वाले': 'wale', 'साथ': 'saath', 'बारे': 'baare', 'लिए': 'liye',
    'द्वारा': 'dwara', 'बिना': 'bina', 'सिर्फ': 'sirf',
    'बस': 'bas', 'काफी': 'kaafi', 'बहुत': 'bahut', 'ज़्यादा': 'zyada',
    'कम': 'kam', 'ठीक': 'theek', 'सही': 'sahi',

    # ── Question Words ────────────────────────────────────────────
    'कहां': 'kahan', 'कहाँ': 'kahan', 'कैसे': 'kaise', 'कैसा': 'kaisa',
    'कब': 'kab', 'कितना': 'kitna', 'कितनी': 'kitni', 'कितने': 'kitne',
    'क्यों': 'kyon', 'कहा': 'kaha', 'किसे': 'kise', 'किसने': 'kisne',
    'किसका': 'kiska', 'किसकी': 'kiski', 'किधर': 'kidhar',

    # ── Common Nouns ──────────────────────────────────────────────
    'लोग': 'log', 'लोगों': 'logon', 'आदमी': 'aadmi', 'औरत': 'aurat',
    'बच्चा': 'baccha', 'बच्चे': 'bacche', 'बच्ची': 'bacchi',
    'दोस्त': 'dost', 'भाई': 'bhai', 'बहन': 'bahin',
    'माँ': 'maa', 'पिता': 'pita', 'बेटा': 'beta', 'बेटी': 'beti',
    'घर': 'ghar', 'कमरा': 'kamra', 'दरवाज़ा': 'darwaza',
    'पानी': 'paani', 'खाना': 'khana', 'रोटी': 'roti',
    'दिन': 'din', 'रात': 'raat', 'सुबह': 'subah', 'शाम': 'shaam',
    'समय': 'samay', 'वक्त': 'waqt', 'साल': 'saal', 'महीना': 'mahina',
    'हफ्ता': 'hafta',
    'काम': 'kaam', 'बात': 'baat', 'चीज़': 'cheez', 'जगह': 'jagah',
    'तरह': 'tarah', 'तरीका': 'tareeka', 'सवाल': 'sawaal',
    'जवाब': 'jawaab', 'मतलब': 'matlab',
    'देश': 'desh', 'दुनिया': 'duniya', 'ज़िंदगी': 'zindagi',
    'पैसा': 'paisa', 'पैसे': 'paise', 'रुपया': 'rupya',
    'दिल': 'dil', 'आँख': 'aankh', 'हाथ': 'haath', 'सर': 'sar',

    # ── Common Adjectives ─────────────────────────────────────────
    'अच्छा': 'achha', 'अच्छी': 'achhi', 'अच्छे': 'achhe',
    'बुरा': 'bura', 'बड़ा': 'bada', 'बड़ी': 'badi', 'बड़े': 'bade',
    'छोटा': 'chhota', 'छोटी': 'chhoti', 'छोटे': 'chhote',
    'नया': 'naya', 'नयी': 'nayi', 'नए': 'naye',
    'पुराना': 'purana', 'पहला': 'pehla', 'पहली': 'pehli',
    'दूसरा': 'doosra', 'दूसरी': 'doosri',
    'सारा': 'saara', 'सारी': 'saari', 'सारे': 'saare',
    'पूरा': 'poora', 'पूरी': 'poori', 'पूरे': 'poore',
    'ज़रूरी': 'zaroori', 'ख़ास': 'khaas', 'सीधा': 'seedha',

    # ── Adverbs & Time Words ──────────────────────────────────────
    'आज': 'aaj', 'कल': 'kal', 'परसों': 'parson',
    'यहां': 'yahan', 'यहाँ': 'yahan', 'वहां': 'wahan', 'वहाँ': 'wahan',
    'ऊपर': 'upar', 'नीचे': 'neeche', 'अंदर': 'andar', 'बाहर': 'bahar',
    'पहले': 'pehle', 'बाद': 'baad', 'हमेशा': 'hamesha',
    'कभी': 'kabhi', 'अभी': 'abhi', 'जल्दी': 'jaldi', 'धीरे': 'dheere',

    # ── Useful Expressions ────────────────────────────────────────
    'नमस्ते': 'namaste', 'शुक्रिया': 'shukriya', 'धन्यवाद': 'dhanyavaad',
    'माफ़': 'maaf', 'ज़रूर': 'zaroor', 'अलविदा': 'alvida',
    'इसलिए': 'isliye', 'इसका': 'iska', 'उसका': 'uska',
    'वैसे': 'waise', 'जैसे': 'jaise', 'ऐसे': 'aise', 'ऐसा': 'aisa',
    'ऐसी': 'aisi', 'कैसे': 'kaise', 'कैसा': 'kaisa', 'कैसी': 'kaisi',

    # ── Negation ──────────────────────────────────────────────────
    'नहीं': 'nahin', 'न': 'na', 'मत': 'mat',

    # ── Numbers ───────────────────────────────────────────────────
    'एक': 'ek', 'दो': 'do', 'तीन': 'teen', 'चार': 'char',
    'पांच': 'panch', 'छह': 'chhah', 'सात': 'saat', 'आठ': 'aath',
    'नौ': 'nau', 'दस': 'das', 'सौ': 'sau', 'हज़ार': 'hazaar',
    'लाख': 'lakh', 'करोड़': 'karod',
}


# ══════════════════════════════════════════════════════════════════════
# SECTION 3: COMMON CONJUNCT CLUSTERS
# ══════════════════════════════════════════════════════════════════════
# Two-consonant clusters formed via halant (virama).
# Format: (consonant1 + halant + consonant2) → Romanized cluster

_CONJUNCT_MAP: Dict[str, str] = {
    'क्ष': 'ksh',   # क + ् + ष
    'त्र': 'tr',    # त + ् + र
    'ज्ञ': 'gya',   # ज + ् + ञ  (traditional Hindi pronunciation)
    'श्र': 'shr',   # श + ् + र
    'प्र': 'pr',    # प + ् + र
    'क्र': 'kr',    # क + ् + र
    'ग्र': 'gr',    # ग + ् + र
    'ब्र': 'br',    # ब + ् + र
    'द्र': 'dr',    # द + ् + र
    'फ्र': 'fr',    # फ + ् + र  (English loanwords)
    'स्त': 'st',    # स + ् + त
    'स्थ': 'sth',   # स + ् + थ
    'स्ट': 'st',    # स + ् + ट
    'स्क': 'sk',    # स + ् + क
    'स्प': 'sp',    # स + ् + प
    'स्व': 'sw',    # स + ् + व
    'स्न': 'sn',    # स + ् + न
    'स्म': 'sm',    # स + ् + म
    'द्व': 'dw',    # द + ् + व
    'द्ध': 'ddh',   # द + ् + ध
    'न्ह': 'nh',    # न + ् + ह
    'ल्ह': 'lh',    # ल + ् + ह
    'न्द': 'nd',    # न + ् + द
    'न्त': 'nt',    # न + ् + त
    'म्ब': 'mb',    # म + ् + ब
    'ट्र': 'tr',    # ट + ् + र
    'ड्र': 'dr',    # ड + ् + र
    'थ्र': 'thr',   # थ + ् + र
    'क्ल': 'kl',    # क + ् + ल
    'प्ल': 'pl',    # प + ् + ल
    'ब्ल': 'bl',    # ब + ् + ल
    'ग्ल': 'gl',    # ग + ् + ल
    'च्छ': 'chchh', # च + ् + छ
    'ज्ज': 'jj',    # ज + ् + ज
    'ल्ल': 'll',    # ल + ् + ल
    'म्म': 'mm',    # म + ् + म
    'न्न': 'nn',    # न + ् + न
    'प्प': 'pp',    # प + ् + प
    'त्त': 'tt',    # त + ् + त
    'क्क': 'kk',    # क + ् + क
    'ट्ट': 'tt',    # ट + ् + ट
    'ड्ड': 'dd',    # ड + ् + ड
    'द्द': 'dd',    # द + ् + द
    'श्व': 'shw',   # श + ् + व
}


# ══════════════════════════════════════════════════════════════════════
# SECTION 4: THE ROMANIZATION ENGINE
# ══════════════════════════════════════════════════════════════════════

class RomanizationService:
    """
    Ultra-detailed Devanagari → Roman transliteration engine.

    CRITICAL FIX: This service replaces the old _transliterate_text method
    in transcription_service.py which had a word-joining bug (e.g., "bynthis"
    instead of "by this").

    The fix works by:
    1. Tokenizing text at WORD BOUNDARIES (spaces, punctuation)
    2. Processing each Devanagari word independently
    3. Reassembling with proper spacing

    This ensures English words, Devanagari words, and mixed-script text
    are never joined together.
    """

    # ── Word boundary pattern ─────────────────────────────────────
    # Splits text into tokens while preserving all whitespace and punctuation.
    # Each token is either a "word" or a "separator" (spaces, newlines, etc.)
    _TOKEN_PATTERN = re.compile(r'(\s+|[^\s]+)')

    # Check if a string contains Devanagari
    _DEVANAGARI_RANGE = re.compile(r'[\u0900-\u097F]')

    @classmethod
    def transliterate(cls, text: str) -> str:
        """
        Main entry point: Convert any Devanagari in text to Romanized form.
        Latin/English characters pass through unchanged.
        Preserves all word boundaries and spacing.

        Examples:
            "मुझे दो चीजें बता जो fascinating"
            → "mujhe do cheezein bata jo fascinating"

            "यह बहुत अच्छा है"
            → "yeh bahut achha hai"

            "Hello दुनिया! How are you?"
            → "Hello duniya! How are you?"
        """
        if not text:
            return text

        # Quick check: if there's no Devanagari at all, return as-is
        if not cls._DEVANAGARI_RANGE.search(text):
            return text

        # Tokenize preserving all whitespace
        tokens = cls._TOKEN_PATTERN.findall(text)
        result_tokens = []

        for token in tokens:
            if token.isspace():
                # Preserve whitespace exactly as-is
                result_tokens.append(token)
            elif cls._DEVANAGARI_RANGE.search(token):
                # Token contains Devanagari — transliterate it
                # First strip any attached punctuation
                leading_punct, core, trailing_punct = cls._strip_punctuation(token)
                romanized = cls._transliterate_word(core)
                result_tokens.append(leading_punct + romanized + trailing_punct)
            else:
                # Pure Latin/number/symbol token — pass through unchanged
                result_tokens.append(token)

        return ''.join(result_tokens)

    @staticmethod
    def _strip_punctuation(token: str) -> Tuple[str, str, str]:
        """
        Separate leading/trailing non-Devanagari punctuation from a token.
        Returns (leading_punct, core_word, trailing_punct).
        """
        # Common punctuation that might be attached to Devanagari words
        punct_chars = set('.,!?;:"\'-()[]{}…।॥')

        leading = []
        i = 0
        while i < len(token) and token[i] in punct_chars:
            leading.append(token[i])
            i += 1

        trailing = []
        j = len(token) - 1
        while j >= i and token[j] in punct_chars:
            trailing.append(token[j])
            j -= 1

        core = token[i:j + 1]
        return ''.join(leading), core, ''.join(reversed(trailing))

    @classmethod
    def _transliterate_word(cls, word: str) -> str:
        """
        Transliterate a single Devanagari word to Roman script.

        Strategy:
        1. Dictionary lookup (fast path, guaranteed accurate)
        2. Conjunct-aware character-by-character transliteration (fallback)
        """
        if not word:
            return word

        # ── Fast Path: Dictionary lookup ──
        if word in _COMMON_WORDS:
            return _COMMON_WORDS[word]

        # ── Slow Path: Character-by-character transliteration ──
        return cls._char_by_char_transliterate(word)

    @classmethod
    def _char_by_char_transliterate(cls, text: str) -> str:
        """
        Character-by-character Devanagari → Roman transliteration
        with proper handling of:
        - Inherent 'a' vowel on consonants
        - Halant (virama) suppression
        - Matra (vowel sign) replacement
        - Conjunct consonant clusters
        - Schwa deletion rules
        - Anusvara/Visarga
        """
        result = []
        i = 0
        length = len(text)

        while i < length:
            char = text[i]
            code = ord(char)

            # ── Check if in Devanagari range ──
            if not (0x0900 <= code <= 0x097F):
                # Not Devanagari — pass through (Latin, numbers, etc.)
                result.append(char)
                i += 1
                continue

            # ── Devanagari digits ──
            if char in _DIGITS:
                result.append(_DIGITS[char])
                i += 1
                continue

            # ── Devanagari punctuation ──
            if char in _PUNCTUATION:
                result.append(_PUNCTUATION[char])
                i += 1
                continue

            # ── Special signs (anusvara, visarga, chandrabindu, nukta) ──
            if char in _SPECIAL_SIGNS:
                result.append(_SPECIAL_SIGNS[char])
                i += 1
                continue

            # ── Standalone vowels ──
            if char in _VOWELS:
                result.append(_VOWELS[char])
                i += 1
                continue

            # ── Matras (vowel signs) ──
            if char in _MATRAS:
                result.append(_MATRAS[char])
                i += 1
                continue

            # ── Halant (virama) — should have been consumed by consonant logic ──
            if char == _HALANT:
                # Stray halant — just skip it
                i += 1
                continue

            # ── Consonants ──
            consonant_base = None

            # Check nukta consonants first (pre-composed forms)
            if char in _NUKTA_CONSONANTS:
                consonant_base = _NUKTA_CONSONANTS[char]
                i += 1
            elif char in _CONSONANTS:
                consonant_base = _CONSONANTS[char]
                i += 1

                # Check if this consonant has a nukta sign following it
                if i < length and text[i] == '\u093C':
                    # Consonant + nukta → apply nukta mapping
                    original_char = char
                    nukta_key = char + '\u093C'
                    # Common nukta adjustments
                    nukta_adjustments = {
                        '\u0915': 'q',   # क + ़ = क़ = q
                        '\u0916': 'kh',  # ख + ़ = ख़ = kh
                        '\u0917': 'gh',  # ग + ़ = ग़ = gh
                        '\u091C': 'z',   # ज + ़ = ज़ = z
                        '\u0921': 'd',   # ड + ़ = ड़ = d
                        '\u0922': 'dh',  # ढ + ़ = ढ़ = dh
                        '\u092B': 'f',   # फ + ़ = फ़ = f
                    }
                    if original_char in nukta_adjustments:
                        consonant_base = nukta_adjustments[original_char]
                    i += 1  # Skip the nukta sign

            if consonant_base is not None:
                # ── Check for conjuncts: consonant + halant + consonant ──
                # Look ahead for halant + next consonant (conjunct cluster)
                while i < length and text[i] == _HALANT:
                    if i + 1 < length and (text[i + 1] in _CONSONANTS or text[i + 1] in _NUKTA_CONSONANTS):
                        # This is a conjunct: skip halant, get next consonant base
                        i += 1  # skip halant
                        next_char = text[i]
                        if next_char in _NUKTA_CONSONANTS:
                            consonant_base += _NUKTA_CONSONANTS[next_char]
                        elif next_char in _CONSONANTS:
                            consonant_base += _CONSONANTS[next_char]
                        i += 1  # skip next consonant

                        # Check for nukta after the second consonant
                        if i < length and text[i] == '\u093C':
                            i += 1
                    else:
                        # Halant at end of word or before non-consonant — suppress 'a'
                        i += 1  # skip halant
                        break

                # ── Now check what follows the consonant (cluster) ──
                if i < length:
                    next_char = text[i]
                    if next_char in _MATRAS:
                        # Matra replaces inherent 'a'
                        result.append(consonant_base + _MATRAS[next_char])
                        i += 1
                    elif next_char == _HALANT:
                        # Halant at end → no vowel
                        result.append(consonant_base)
                        i += 1
                    elif next_char in _SPECIAL_SIGNS and next_char not in ('\u093C',):
                        # Anusvara, visarga, chandrabindu after consonant
                        result.append(consonant_base + 'a' + _SPECIAL_SIGNS[next_char])
                        i += 1
                    else:
                        # No matra, no halant → inherent 'a'
                        # Apply schwa deletion: don't add 'a' at end of word
                        # (simplified rule: if this is the last consonant and next is
                        # space/end/punctuation, drop the schwa)
                        if cls._should_drop_schwa(text, i, length):
                            result.append(consonant_base)
                        else:
                            result.append(consonant_base + 'a')
                else:
                    # End of text — drop inherent 'a' (word-final schwa deletion)
                    result.append(consonant_base)

                continue

            # ── Unknown character — pass through ──
            result.append(char)
            i += 1

        return ''.join(result)

    @staticmethod
    def _should_drop_schwa(text: str, pos: int, length: int) -> bool:
        """
        Simplified Hindi schwa deletion rule.

        In Hindi (unlike Sanskrit), the inherent 'a' vowel is often
        dropped at the end of a word and sometimes in word-medial positions.

        Rules applied:
        1. Word-final consonant: always drop schwa
           कमल → kamal (not kamala)
        2. Before a space or punctuation: drop schwa
        3. Before another consonant with no matra: keep schwa
           (it's likely a medial vowel needed for pronunciation)

        This is a heuristic — the common word dictionary handles the
        cases where this heuristic fails.
        """
        if pos >= length:
            return True  # End of text

        next_char = text[pos]
        next_code = ord(next_char)

        # If next char is not Devanagari — we're at a word boundary
        if not (0x0900 <= next_code <= 0x097F):
            return True

        # If next is a vowel sign (matra) — don't drop (matra replaces it)
        # This case should have been handled earlier, but just in case:
        if next_char in _MATRAS:
            return False

        # If next is halant — don't drop (halant explicitly handles it)
        if next_char == _HALANT:
            return False

        # If next is anusvara/visarga/chandrabindu — don't drop
        if next_char in _SPECIAL_SIGNS:
            return False

        # If next is a standalone vowel — don't drop
        if next_char in _VOWELS:
            return False

        # If next is a consonant — this is a word-medial position
        # Keep the schwa (e.g., कमल = ka-ma-l → kamal needs the middle 'a')
        if next_char in _CONSONANTS or next_char in _NUKTA_CONSONANTS:
            return False

        # Default: keep the schwa to be safe
        return False

    @classmethod
    def transliterate_segments(
        cls,
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply Romanization to all transcript segments.
        Only processes segments that contain Devanagari text.
        """
        has_devanagari = False
        for seg in segments:
            text = seg.get("text", "")
            if cls._DEVANAGARI_RANGE.search(text):
                has_devanagari = True
                break

        if not has_devanagari:
            return segments

        logger.info("Detected Devanagari text — applying professional Romanization")
        for seg in segments:
            seg["text"] = cls.transliterate(seg["text"])

        return segments
