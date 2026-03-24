# header_extractor.py

import pdfplumber
import re
import time
from datetime import datetime

BARCODE_PATTERN = re.compile(r'\s*Barcode.*$', re.IGNORECASE)
LINE_WITHOUT_COLON_IGNORE = re.compile(r'^\s*Barcode\s*\d', re.IGNORECASE)
AGE_PATTERN = re.compile(r'(\d+)\s*Yrs?', re.IGNORECASE)

def parse_datetime(value):
    if not value or not isinstance(value, str):
        return None

    formats = [
        "%d-%b-%Y %I:%M %p",
        "%d-%b-%Y %H:%M",
        "%d-%b-%y %I:%M %p",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue

    return None


def extract_side(side_words):
    if not side_words:
        return None, None

    colon_idx = next((i for i, w in enumerate(side_words) if w['text'] == ':'), None)

    if colon_idx is not None:
        label = ' '.join(w['text'] for w in side_words[:colon_idx]).strip()
        value = ' '.join(w['text'] for w in side_words[colon_idx+1:]).strip()
        return label, value
    else:
        return None, ' '.join(w['text'] for w in side_words).strip()


def extract_header_until_testname(pdf_path):

    start_time = time.perf_counter()

    header_data = {}
    header_lines_with_words = []

    with pdfplumber.open(pdf_path) as pdf:

        first_page = pdf.pages[0]

        words = first_page.extract_words(
            use_text_flow=True,
            keep_blank_chars=True
        )

        words_sorted = sorted(words, key=lambda w: (w['top'], w['x0']))

        lines = []
        current_line = []
        current_y = None
        TOLERANCE = 4

        for w in words_sorted:

            if current_y is None:
                current_y = w['top']
                current_line.append(w)

            elif abs(w['top'] - current_y) < TOLERANCE:
                current_line.append(w)

            else:
                current_line.sort(key=lambda x: x['x0'])
                lines.append((current_y, current_line))
                current_line = [w]
                current_y = w['top']

        if current_line:
            current_line.sort(key=lambda x: x['x0'])
            lines.append((current_y, current_line))

        for y, word_list in lines:

            line_text = ' '.join(w['text'] for w in word_list).lower()

            if 'test name' in line_text:
                break

            header_lines_with_words.append((y, word_list))

        colon_xs = []

        for y, word_list in header_lines_with_words:
            for w in word_list:
                if w['text'] == ':':
                    colon_xs.append(w['x0'])

        if len(colon_xs) >= 2:

            colon_xs.sort()

            gaps = [
                colon_xs[i+1] - colon_xs[i]
                for i in range(len(colon_xs)-1)
            ]

            max_gap_idx = gaps.index(max(gaps))

            threshold = (
                colon_xs[max_gap_idx] +
                colon_xs[max_gap_idx+1]
            ) / 2

        else:
            threshold = None

        for y, word_list in header_lines_with_words:

            line_text = ' '.join(w['text'] for w in word_list)

            if LINE_WITHOUT_COLON_IGNORE.match(line_text):
                continue

            if ':' not in line_text:
                header_data.setdefault('unstructured', []).append(line_text.strip())
                continue

            if threshold is not None:

                left_words = [w for w in word_list if w['x0'] < threshold]
                right_words = [w for w in word_list if w['x0'] >= threshold]

            else:

                left_words = word_list
                right_words = []

            left_label, left_value = extract_side(left_words)

            if left_label:

                left_value = BARCODE_PATTERN.sub('', left_value).strip()
                header_data[left_label] = left_value

            right_label, right_value = extract_side(right_words)

            if right_label:

                right_value = BARCODE_PATTERN.sub('', right_value).strip()
                header_data[right_label] = right_value

        if 'MR Number' in header_data:
            try:
                header_data['MR Number'] = int(header_data['MR Number'])
            except:
                pass

        if 'Bill no' in header_data:
            try:
                header_data['Bill no'] = int(header_data['Bill no'])
            except:
                pass

        if 'Age' in header_data:

            match = AGE_PATTERN.search(header_data['Age'])

            if match:
                header_data['Age'] = int(match.group(1))

        if 'Gender' in header_data:

            gender = header_data['Gender'].strip().lower()

            if gender.startswith('f'):
                header_data['Gender'] = 'F'

            elif gender.startswith('m'):
                header_data['Gender'] = 'M'

        datetime_fields = [
            'Registered On',
            'Sample Collected On',
            'Sample Reported On'
        ]

        for field in datetime_fields:

            if field in header_data:

                dt = parse_datetime(header_data[field])

                if dt:
                    header_data[field] = dt

    elapsed = time.perf_counter() - start_time
    print(f"Header extraction time: {elapsed:.4f}s")

    return header_data