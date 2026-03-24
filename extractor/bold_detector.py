import pdfplumber
import pandas as pd
from collections import Counter


# --------------------------------------------------------
# Faster numeric check
# --------------------------------------------------------
def is_number(text):
    try:
        float(text)
        return True
    except:
        return False


# --------------------------------------------------------
# Optimized Word Grouping (stores text + bold once)
# --------------------------------------------------------
def group_chars_into_words(chars, x_threshold=2, y_threshold=3):

    chars.sort(key=lambda c: (round(c["top"], 1), c["x0"]))

    words = []
    current_word = []
    prev_char = None

    for char in chars:

        if not prev_char:
            current_word.append(char)

        else:
            same_line = abs(char["top"] - prev_char["top"]) < y_threshold
            close_x = abs(char["x0"] - prev_char["x1"]) < x_threshold

            if same_line and close_x:
                current_word.append(char)
            else:
                words.append(current_word)
                current_word = [char]

        prev_char = char

    if current_word:
        words.append(current_word)

    # Convert to optimized structure
    optimized_words = []

    for w in words:

        text = "".join(c["text"] for c in w)

        optimized_words.append({
            "text": text,
            "x0": round(w[0]["x0"], -1),
            "top": w[0]["top"],
            "is_bold": any("Bold" in c["fontname"] for c in w)
        })

    return optimized_words


# --------------------------------------------------------
# Optimized Row Grouping
# --------------------------------------------------------
def group_words_into_rows(words, y_threshold=3):

    words.sort(key=lambda w: w["top"])

    rows = []
    current_row = []
    prev_top = None

    for word in words:

        top = word["top"]

        if prev_top is None or abs(top - prev_top) < y_threshold:
            current_row.append(word)

        else:
            current_row.sort(key=lambda w: w["x0"])
            rows.append(current_row)
            current_row = [word]

        prev_top = top

    if current_row:
        current_row.sort(key=lambda w: w["x0"])
        rows.append(current_row)

    return rows


# --------------------------------------------------------
# Faster Column Detection
# --------------------------------------------------------
def detect_value_column_from_rows(rows):

    x_positions = []

    for row in rows:

        if len(row) < 3:
            continue

        for i in range(1, len(row) - 1):

            left = row[i - 1]["text"]
            middle = row[i]["text"]
            right = row[i + 1]["text"]

            if len(left) > 2 and is_number(middle) and len(right) < 15:
                x_positions.append(row[i]["x0"])

    if not x_positions:
        return None

    return Counter(x_positions).most_common(1)[0][0]


# --------------------------------------------------------
# Extract Bold Abnormal Tests
# --------------------------------------------------------
def extract_bold_tests(pdf_path):

    extracted = []

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            words = group_chars_into_words(page.chars)
            rows = group_words_into_rows(words)

            value_column_x = detect_value_column_from_rows(rows)

            if value_column_x is None:
                continue

            for row in rows:

                for i, word in enumerate(row):

                    if not is_number(word["text"]):
                        continue

                    if abs(word["x0"] - value_column_x) > 20:
                        continue

                    if not word["is_bold"]:
                        continue

                    test_name = " ".join(w["text"] for w in row[:i]).strip()

                    if len(test_name) < 3:
                        continue

                    extracted.append({
                        "Test Name": test_name,
                        "Bold Value": float(word["text"])
                    })

    return pd.DataFrame(extracted)


# --------------------------------------------------------
# Function used by core.py
# --------------------------------------------------------
def get_abnormal_tests(pdf_path):

    df = extract_bold_tests(pdf_path)

    if df.empty:
        return set()

    # return only test names for fast lookup
    return set(df["Test Name"].str.lower())