from typing import Dict


def bilingual_error(en: str, ar: str) -> Dict[str, str]:
    return {"en": en, "ar": ar}


def bilingual_success(en: str, ar: str) -> Dict[str, str]:
    return {"en": en, "ar": ar}


def rtl_wrap(text: str) -> str:
    return f"\u202B{text}\u202C"
