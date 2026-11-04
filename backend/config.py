import re


UNDERAGE = re.compile(
    r"\b(i['’]?m|i am) (only )?(1[0-7]\b(?! ?(min|hour|hr))|in (\d+th grade|middle school|high ?school))"
    r"|\b1[0-7] ?(yo|y/o|years old)\b",
    re.IGNORECASE,
)


OFF_LIMITS = re.compile(
    re.IGNORECASE,
)

REFUSAL = re.compile(
    r"(?:cant|can'?t|can not|won'?t|will not)\s+(?:continue|do this|keep going)"
    r"|not comfortable\s+(?:with|talking|continuing)"
    r"|i'?d rather not (?:continue|talk about)"
    r"|i'?m sorry,?\s+but\s+i\s+(?:cant|can'?t)",
    re.IGNORECASE,
)

