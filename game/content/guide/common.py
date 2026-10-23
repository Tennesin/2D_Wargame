"""game/content/guide/common.py — общий помощник страниц инструкции."""
from inputs import key_label

def k(action):
    """Подпись клавиши действия (берётся из привязок, поэтому текст не устаревает)."""
    return key_label(action)