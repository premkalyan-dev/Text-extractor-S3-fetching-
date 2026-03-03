# Row-level processing: heading_score, hybrid_result_parser,
# is_noise_row

import re

# ----------------------------------------------------------------------
# Category scoring
# ----------------------------------------------------------------------
def heading_score(line_text, distance):
    score = 0
    score += 100 / (distance + 1)
    if ':' in line_text:
        score -= 200
    if re.search(r'\d', line_text):
        score -= 100
    if '/' in line_text or '-' in line_text:
        score -= 50
    if len(line_text) < 3:
        score -= 50
    if len(line_text) > 100:
        score -= 30
    if line_text.isupper():
        score += 20
    elif line_text.istitle():
        score += 10
    return score

# ----------------------------------------------------------------------
# Result parser (handles internal gaps)
# ----------------------------------------------------------------------
def hybrid_result_parser(result_words):
    if not result_words:
        return "", None
    result_words = sorted(result_words, key=lambda x: x["x0"])
    tokens = []
    prev_x1 = None
    for word in result_words:
        if prev_x1:
            gap = word["x0"] - prev_x1
            if gap > 15:
                break
        tokens.append(word["text"])
        prev_x1 = word["x1"]
    result_text = " ".join(tokens)
    num_match = re.search(r"[-+]?\d*\.?\d+", result_text)
    if num_match:
        try:
            return result_text, float(num_match.group())
        except ValueError:
            return result_text, None
    else:
        return result_text, None

# ----------------------------------------------------------------------
# Check if a row is noise (separator lines, end markers, signatures, etc.)
# ----------------------------------------------------------------------
def is_noise_row(row):
    full_text = " ".join(w["text"] for w in row).strip()
    if not full_text:
        return True

    noise_patterns = [
        r'^[_\-]+$',
        r'\*{3,}',
        r'END OF REPORT',
        r'Method\s*:-',
        r'Note\s*:-',
        r'Interpretation\s*:',
        r'^[_\-]+\s*$',
        r'KMC\s*No\.?\s*:?\s*\d+',
        r'Dr\.?\s+[A-Za-z]+\s+[A-Za-z]+',
        r'Senior Lab Technologist',
        r'Consultant Pathologist',
        r'Page\s+\d+\s+of\s+\d+',
    ]
    for pat in noise_patterns:
        if re.search(pat, full_text, re.IGNORECASE):
            return True
    return False