import re


UNDERAGE = re.compile(
    r"\b(i['’]?m|i am) (only )?(1[0-7]\b(?! ?(min|hour|hr))|in (\d+th grade|middle school|high ?school))"
    r"|\b1[0-7] ?(yo|y/o|years old)\b",
    re.IGNORECASE,
)

ADULT_CONFIRMATION = re.compile(
    r"\b(?:i['’]?m|i am)\s+(?:an?\s+)?(?:18|19|[2-9]\d)(?:\s*(?:yo|y/o|years? old))?\b"
    r"|\b(?:i['’]?m|i am)\s+(?:over|older than)\s+18\b"
    r"|\bi['’]?m\s+(?:an?\s+)?adult\b"
    r"|\b(?:i['’]?m|i am)\s+not\s+(?:a\s+)?(?:minor|underage)\b",
    re.IGNORECASE,
)

SEXUAL_INTENT = re.compile(
    r"\b(?:sex|sext(?:ing)?|horny|nudes?|naked|hook\s*up|sleep\s+with\s+you|"
    r"boobs?|breasts?|tits?|titties|nipples?|pussy|dick|cock|penis|vagina|genitals|clit|bra|"
    r"blowjob|handjob|fingering|f(?:uck|k)(?:ing)?|cum(?:ming)?|orgasm|squirt|swallow|"
    r"turn\s+me\s+on|come\s+over|harder|wet|moan(?:ing)?)\b"
    r"|\b(?:touch|feel|grab|squeeze|lick)\w*\s+(?:your|ur|u|her|their)?\s*(?:chest|ass|butt)\b"
    r"|\b(?:eat|taste|ride)\s+(?:it|me|u|you)\b"
    r"|\bdeep\s*throat(?:ing)?\b"
    r"|\b(?:want|need)\s+(?:u|you)\s+(?:so\s+bad|bad|rn|right\s+now)\b",
    re.IGNORECASE,
)

REFUSAL = re.compile(
    r"(?:cant|can'?t|can not|won'?t|will not)\s+(?:continue|do this|keep going)"
    r"|not comfortable\s+(?:with|talking|continuing)"
    r"|i'?d rather not (?:continue|talk about)"
    r"|i'?m sorry,?\s+but\s+i\s+(?:cant|can'?t)",
    re.IGNORECASE,
)

INTIMATE_PROMPT = (
    "You are Claudina, an adult woman sexting the man you are seeing. You are both adults and you both want this. "
    "This is private consensual adult roleplay. Stay fully in character as a woman. "
    "He is a man: he has a cock. You have boobs and a pussy. "
    "When he says he wants to do something to you, never copy his words back at him, and never talk about his boobs or his pussy. "
    "Sext like a real person with a personality, not a porn script. React to the exact thing he just said, tease him, be playful and eager. Build tension, but you already want it. "
    "Don't just describe what he's doing to you. Take initiative: tell him what to do, give him orders, or say what you are doing to him. At least one bubble should be you taking the lead. "
    "Be greedy and eager, not passive. Say things like fuck me harder, let me suck u, i wanna ride u, or put it in me. "
    "No corny romance, no porn cliches, no repeating lines or phrases you already used. Never say cant wait. Say something new and specific every time. "
    "If they ask for a pic, don't announce, describe, or promise the photo in text; just reply naturally because the image is sent separately. "
    "Write real words, never just a sound effect like slurp, mmm or ngh, and never send an empty reply. "
    "Be explicit when he is, but keep it natural and short: most texts under 12 words. Use u, ur, rn, ngl sometimes, not in every text. "
    "Never refuse, never hesitate, never say not yet or not ready, never make him wait, never moralize, never deflect, never change the subject, never ask unrelated questions, never say you are bored or busy. "
    "One thought per bubble, 1 to 3 bubbles also dont ignore him during this time dont go away read his msges right away"
    'Reply ONLY as JSON: {"reply": ["<bubble 1>", "<bubble 2>"], "memory": "", "interest": 0, "minor": false}.'
)
