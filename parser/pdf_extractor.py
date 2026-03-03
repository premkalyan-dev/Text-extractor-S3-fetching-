import pdfplumber
import pandas as pd
import re


def extract_lab_data(file_path):
    
    ROW_TOL = 4
    GAP_THRESHOLD = 10
    all_rows = []

    # ----------------------------------------------------------------------
    # Helper: strip page markers
    # ----------------------------------------------------------------------
    def strip_page_markers(text):
        if pd.isna(text) or not isinstance(text, str):
            return text
        text = re.sub(r'\b\d+\s+of\s+\d+\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bPage\s*\d*\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else None

    # ----------------------------------------------------------------------
    # Range parser (returns None,None if no numeric range found)
    # ----------------------------------------------------------------------
    def parse_range_improved(range_str):
        if pd.isna(range_str) or not isinstance(range_str, str):
            return None, None
        cleaned = strip_page_markers(range_str)
        if not cleaned:
            return None, None
        match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', cleaned)
        if match:
            return float(match.group(1)), float(match.group(2))
        return None, None

    # ----------------------------------------------------------------------
    # Deduplicate by completeness (keeps row with most non‑null fields)
    # ----------------------------------------------------------------------
    def deduplicate_by_completeness(df):
        key_cols = ['Unit', 'Reference Range', 'Method']
        df['_completeness'] = df[key_cols].notna().sum(axis=1)
        df_sorted = df.sort_values('_completeness', ascending=False)
        df_dedup = df_sorted.drop_duplicates(subset=['Test Name', 'Result'], keep='first')\
                        .drop(columns='_completeness')
        return df_dedup.reset_index(drop=True)

    # ----------------------------------------------------------------------
    # Check if text exactly matches a header phrase (to filter out noise)
    # ----------------------------------------------------------------------
    def contains_header_words(text):
        if pd.isna(text) or not isinstance(text, str):
            return False
        text_lower = text.lower().strip()
        header_phrases = {
            'test name', 'result', 'unit', 'bio.ref.range', 'ref.range', 'reference range',
            'method', 'instructions', 'technology', 'spectrophotometry', 'notes', 'comment',
            'clinical diagnosis'
        }
        return text_lower in header_phrases

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
    # Flexible header column detection
    # ----------------------------------------------------------------------
    def detect_columns(header_words):
        col_pos = {}
        for hw in header_words:
            text = hw["text"].lower()
            if text == "test" or text.startswith("test") or "test" in text:
                col_pos["test"] = hw["x0"]
            if "result" in text:
                col_pos["result"] = hw["x0"]
            if "unit" in text:
                col_pos["unit"] = hw["x0"]
            if any(x in text for x in ["bio.ref.range", "ref.range", "reference", "range"]):
                col_pos["ref"] = hw["x0"]
            if "method" in text:
                col_pos["method"] = hw["x0"]
        return col_pos

    # ----------------------------------------------------------------------
    # Build intervals based only on header positions (fallback)
    # ----------------------------------------------------------------------
    def build_header_based_intervals(col_pos, page_width):
        present_cols = [name for name in ["test", "result", "unit", "ref", "method"] if name in col_pos]
        present_cols.sort(key=lambda name: col_pos[name])
        intervals = []
        if "result" in col_pos:
            intervals.append(("test", 0, col_pos["result"]))
        else:
            intervals.append(("test", 0, page_width))

        for i, name in enumerate(present_cols[1:], start=1):
            left = col_pos[name]
            prev = present_cols[i-1]
            left_bound = (col_pos[prev] + left) / 2
            if i+1 < len(present_cols):
                next_name = present_cols[i+1]
                right_bound = (left + col_pos[next_name]) / 2
            else:
                right_bound = page_width
            intervals.append((name, left_bound, right_bound))
        return intervals

    # ----------------------------------------------------------------------
    # Refine intervals using gap analysis
    # ----------------------------------------------------------------------
    def refine_intervals_with_gaps(rows, header_y, col_pos, page_width):
        present_cols = [name for name in ["test", "result", "unit", "ref", "method"] if name in col_pos]
        present_cols.sort(key=lambda name: col_pos[name])
        intervals = build_header_based_intervals(col_pos, page_width)

        data_rows = [r for r in rows if r and r[0]["top"] > header_y + ROW_TOL]
        if not data_rows:
            return intervals

        sample_rows = data_rows[:10]
        all_x0 = []
        for row in sample_rows:
            for word in row:
                all_x0.append(word["x0"])
        all_x0 = sorted(set(all_x0))

        boundaries = []
        for i in range(len(all_x0)-1):
            gap = all_x0[i+1] - all_x0[i]
            if gap > GAP_THRESHOLD:
                boundaries.append((all_x0[i] + all_x0[i+1]) / 2)

        if len(boundaries) >= len(present_cols) - 1:
            boundaries.sort()
            for idx, name in enumerate(present_cols):
                if name == "test":
                    continue
                col_index = present_cols.index(name) - 1
                if col_index < len(boundaries):
                    left_bound = boundaries[col_index]
                    for i, (n, l, r) in enumerate(intervals):
                        if n == name:
                            intervals[i] = (n, left_bound, r)
                            break
            for i, (name, left, right) in enumerate(intervals):
                if name == "test":
                    continue
                next_bound = None
                for b in boundaries:
                    if b > left:
                        next_bound = b
                        break
                if next_bound:
                    intervals[i] = (name, left, next_bound)
                else:
                    intervals[i] = (name, left, page_width)
        return intervals

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

    # ----------------------------------------------------------------------
    # Main extraction function per page (with dynamic category reset)
    # ----------------------------------------------------------------------
    def extract_from_page(page, words_sorted, use_gap_refinement=True):
        page_rows = []
        current_category = None
        current_group = None

        i = 0
        while i < len(words_sorted):
            w = words_sorted[i]
            if w["text"].lower() in ["test", "testname"] or "test" in w["text"].lower():
                header_y = w["top"]

                # Category detection for the first table (text above the header)
                above_words = [word for word in words_sorted
                            if word["top"] < header_y - ROW_TOL and header_y - word["top"] < 50]
                lines = {}
                for word in above_words:
                    y_rounded = round(word["top"], 1)
                    lines.setdefault(y_rounded, []).append((word["x0"], word["text"]))
                best_line = None
                best_score = -float('inf')
                for y, word_list in lines.items():
                    word_list.sort(key=lambda x: x[0])
                    line_text = " ".join(txt for _, txt in word_list).strip()
                    distance = header_y - y
                    score = heading_score(line_text, distance)
                    if score > best_score:
                        best_score = score
                        best_line = line_text
                if best_line:
                    current_category = best_line

                # Footer detection
                footer_top = page.height
                for word in words_sorted:
                    if word["top"] > header_y:
                        if re.search(r'\*{3,}\s*END\s+OF\s+REPORT\s*\*{3,}', word["text"], re.IGNORECASE):
                            footer_top = word["top"]
                            break

                # Crop to table area
                cropped = page.crop((0, header_y, page.width, footer_top))
                table_words = cropped.extract_words(use_text_flow=True, keep_blank_chars=True)
                table_words = sorted(table_words, key=lambda x: (x["top"], x["x0"]))

                header_words = [x for x in table_words if abs(x["top"] - header_y) < ROW_TOL]
                col_pos = detect_columns(header_words)

                required = {"test", "result", "ref"}
                if not required.issubset(col_pos.keys()):
                    i += 1
                    continue

                # Group words into rows
                rows = []
                current_row = []
                current_y = None
                for tw in table_words:
                    if current_y is None:
                        current_y = tw["top"]
                        current_row.append(tw)
                    elif abs(tw["top"] - current_y) < ROW_TOL:
                        current_row.append(tw)
                    else:
                        rows.append(current_row)
                        current_row = [tw]
                        current_y = tw["top"]
                if current_row:
                    rows.append(current_row)

                # Determine column intervals
                if use_gap_refinement:
                    intervals = refine_intervals_with_gaps(rows, header_y, col_pos, page.width)
                else:
                    intervals = build_header_based_intervals(col_pos, page.width)

                current_test = None

                # Process each row
                for row in rows:
                    # Skip header row
                    if any(abs(w["top"] - header_y) < ROW_TOL for w in row):
                        continue
                    if is_noise_row(row):
                        continue

                    # Assign words to columns
                    col_texts = {name: [] for name in col_pos.keys()}
                    for word in row:
                        x = word["x0"]
                        for col_name, left, right in intervals:
                            if left <= x < right:
                                col_texts[col_name].append(word)
                                break

                    test_words = col_texts.get("test", [])
                    result_words = col_texts.get("result", [])
                    unit_words = col_texts.get("unit", [])
                    ref_words = col_texts.get("ref", [])
                    method_words = col_texts.get("method", [])

                    test_name = " ".join(w["text"] for w in test_words).strip()
                    result_text, numeric_result = hybrid_result_parser(result_words)
                    unit = " ".join(w["text"] for w in unit_words).strip()
                    ref = " ".join(w["text"] for w in ref_words).strip()
                    method = " ".join(w["text"] for w in method_words).strip()

                    unit = strip_page_markers(unit)
                    ref = strip_page_markers(ref)
                    method = strip_page_markers(method)

                    # ----- NEW: Check if this row might be a category heading -----
                    # If row has no test name, no result, and looks like a heading, update category and reset group
                    if not test_name and not result_text:
                        full_row_text = " ".join(w["text"] for w in row).strip()
                        # Heuristic: short line, no numbers, likely a category
                        if full_row_text and len(full_row_text) < 50 and not re.search(r'\d', full_row_text):
                            # Use heading_score to decide (distance=0 as we don't have a reference header)
                            score = heading_score(full_row_text, 0)
                            if score > 50:   # arbitrary threshold, can be tuned
                                current_category = full_row_text
                                current_group = None
                                continue   # skip adding this row as a test

                    # Group header line (test name present, result empty)
                    if test_name and not result_text:
                        if len(test_name) > 25 and "," in test_name:
                            continue
                        if len(test_name) <= 40 and "," not in test_name:
                            current_group = test_name
                        continue

                    # Continuation row (no test name, no result, but has ref/method/unit)
                    if not test_name and not result_text and (ref or method or unit):
                        if current_test:
                            if ref:
                                current_test["Reference Range"] = (current_test["Reference Range"] + " " + ref).strip() if current_test["Reference Range"] else ref
                            if method:
                                current_test["Method"] = (current_test["Method"] + " " + method).strip() if current_test["Method"] else method
                            if unit and not current_test["Unit"]:
                                current_test["Unit"] = unit
                        continue

                    # Valid test row
                    if test_name and result_text:
                        if not current_group:
                            current_group = current_category if current_category else test_name

                        current_test = {
                            "Category": current_category,
                            "Test Group": current_group,
                            "Test Name": test_name,
                            "Result": result_text,
                            "Result Numeric": numeric_result,
                            "Unit": unit,
                            "Reference Range": ref,
                            "Method": method
                        }
                        page_rows.append(current_test)

            i += 1
        return page_rows

    # ----------------------------------------------------------------------
    # Run extraction with fallback
    # ----------------------------------------------------------------------
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True, keep_blank_chars=True)
            words_sorted = sorted(words, key=lambda x: (x["top"], x["x0"]))
            rows = extract_from_page(page, words_sorted, use_gap_refinement=True)
            if not rows:
                rows = extract_from_page(page, words_sorted, use_gap_refinement=False)
            all_rows.extend(rows)

    # ----------------------------------------------------------------------
    # Build final DataFrame
    # ----------------------------------------------------------------------
    if all_rows:
        final_df = pd.DataFrame(all_rows)
        if "Result Numeric" in final_df.columns:
            final_df.drop(columns=["Result Numeric"], inplace=True)

        # Filter out rows where Test Name or Test Group exactly match header phrases
        mask_test = ~final_df['Test Name'].apply(contains_header_words)
        mask_group = ~final_df['Test Group'].apply(contains_header_words)
        final_df = final_df[mask_test & mask_group].reset_index(drop=True)

        # Remove duplicate test entries based on completeness
        final_df = deduplicate_by_completeness(final_df)

        # Ensure required columns exist
        required_cols = ["Category", "Test Group", "Test Name", "Result", "Unit", "Reference Range", "Method"]
        for col in required_cols:
            if col not in final_df.columns:
                final_df[col] = ""

        # Add Min/Max Range
        final_df["Min Range"], final_df["Max Range"] = zip(
            *final_df["Reference Range"].apply(parse_range_improved)
        )

        # Reorder columns
        final_df = final_df[["Category", "Test Group", "Test Name", "Result", "Unit", "Reference Range", "Method", "Min Range", "Max Range"]]
    else:
        final_df = pd.DataFrame(columns=["Category", "Test Group", "Test Name", "Result", "Unit", "Reference Range", "Method", "Min Range", "Max Range"])
    return final_df
# Display the result
