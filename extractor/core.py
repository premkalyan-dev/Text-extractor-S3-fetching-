import pdfplumber
import pandas as pd
import re
from .bold_detector import get_abnormal_tests
from db.db_config import get_connection
import uuid
from .header_extractor import extract_header_until_testname

from .utils import (
    strip_page_markers,
    parse_range_improved,
    deduplicate_by_completeness,
    contains_header_words
)

from .column import detect_columns, build_header_based_intervals, refine_intervals_with_gaps
from .row_processor import heading_score, hybrid_result_parser, is_noise_row


# ----------------------------------------------------------------------
# Main extraction function per page
# ----------------------------------------------------------------------
def extract_from_page(page, words_sorted, abnormal_tests, use_gap_refinement=True):

    ROW_TOL = 4
    page_rows = []

    current_category = None
    current_group = None

    i = 0

    while i < len(words_sorted):

        w = words_sorted[i]

        if w["text"].lower() in ["test", "testname"] or "test" in w["text"].lower():

            header_y = w["top"]

            # -----------------------------
            # Detect category above table
            # -----------------------------
            above_words = [
                word for word in words_sorted
                if word["top"] < header_y - ROW_TOL and header_y - word["top"] < 50
            ]

            lines = {}

            for word in above_words:
                y_rounded = round(word["top"], 1)
                lines.setdefault(y_rounded, []).append((word["x0"], word["text"]))

            best_line = None
            best_score = -float("inf")

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

            # -----------------------------
            # Footer detection
            # -----------------------------
            footer_top = page.height

            for word in words_sorted:

                if word["top"] > header_y:

                    if re.search(r'\*{3,}\s*END\s+OF\s+REPORT\s*\*{3,}', word["text"], re.IGNORECASE):

                        footer_top = word["top"]
                        break

            # -----------------------------
            # Crop table area
            # -----------------------------
            cropped = page.crop((0, header_y, page.width, footer_top))

            table_words = cropped.extract_words(
                use_text_flow=True,
                keep_blank_chars=True
            )

            table_words = sorted(table_words, key=lambda x: (x["top"], x["x0"]))

            header_words = [
                x for x in table_words
                if abs(x["top"] - header_y) < ROW_TOL
            ]

            col_pos = detect_columns(header_words)

            required = {"test", "result", "ref"}

            if not required.issubset(col_pos.keys()):
                i += 1
                continue

            # -----------------------------
            # Group words into rows
            # -----------------------------
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

            # -----------------------------
            # Column intervals
            # -----------------------------
            if use_gap_refinement:
                intervals = refine_intervals_with_gaps(
                    rows,
                    header_y,
                    col_pos,
                    page.width,
                    ROW_TOL
                )
            else:
                intervals = build_header_based_intervals(
                    col_pos,
                    page.width
                )

            current_test = None

            # -----------------------------
            # Process rows
            # -----------------------------
            for row in rows:

                if any(abs(w["top"] - header_y) < ROW_TOL for w in row):
                    continue

                if is_noise_row(row):
                    continue

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

                # -----------------------------
                # Category heading detection
                # -----------------------------
                if not test_name and not result_text:

                    full_row_text = " ".join(w["text"] for w in row).strip()

                    if full_row_text and len(full_row_text) < 50 and not re.search(r"\d", full_row_text):

                        score = heading_score(full_row_text, 0)

                        if score > 50:
                            current_category = full_row_text
                            current_group = None
                            continue

                # -----------------------------
                # Group header row
                # -----------------------------
                if test_name and not result_text:

                    if len(test_name) > 25 and "," in test_name:
                        continue

                    if len(test_name) <= 40 and "," not in test_name:
                        current_group = test_name

                    continue

                # -----------------------------
                # Continuation row
                # -----------------------------
                if not test_name and not result_text and (ref or method or unit):

                    if current_test:

                        if ref:
                            current_test["Reference Range"] = (
                                current_test["Reference Range"] + " " + ref
                            ).strip() if current_test["Reference Range"] else ref

                        if method:
                            current_test["Method"] = (
                                current_test["Method"] + " " + method
                            ).strip() if current_test["Method"] else method

                        if unit and not current_test["Unit"]:
                            current_test["Unit"] = unit

                    continue

                # -----------------------------
                # Valid test row
                # -----------------------------
                if test_name and result_text:

                    if not current_group:
                        current_group = current_category if current_category else test_name

                    abnormal = 1 if test_name.lower() in abnormal_tests else 0

                    current_test = {
                        "Category": current_category,
                        "Test Group": current_group,
                        "Test Name": test_name,
                        "Result": result_text,
                        "Unit": unit,
                        "Reference Range": ref,
                        "Method": method,
                        "Abnormal": abnormal
                    }

                    page_rows.append(current_test)

        i += 1

    return page_rows


# ----------------------------------------------------------------------
# Main extraction function
# ----------------------------------------------------------------------
def extract_lab_data(file_path):

    header_data = extract_header_until_testname(file_path)

    abnormal_tests = get_abnormal_tests(file_path)

    all_rows = []

    with pdfplumber.open(file_path) as pdf:

        for page in pdf.pages:

            words = page.extract_words(
                use_text_flow=True,
                keep_blank_chars=True
            )

            words_sorted = sorted(words, key=lambda x: (x["top"], x["x0"]))

            rows = extract_from_page(
                page,
                words_sorted,
                abnormal_tests,
                use_gap_refinement=True
            )

            if not rows:
                rows = extract_from_page(
                    page,
                    words_sorted,
                    abnormal_tests,
                    use_gap_refinement=False
                )

            all_rows.extend(rows)

    # -----------------------------
    # Build dataframe
    # -----------------------------
    if all_rows:

        final_df = pd.DataFrame(all_rows)

        mask_test = ~final_df["Test Name"].apply(contains_header_words)
        mask_group = ~final_df["Test Group"].apply(contains_header_words)

        final_df = final_df[mask_test & mask_group].reset_index(drop=True)

        final_df = deduplicate_by_completeness(final_df)

        required_cols = [
            "Category",
            "Test Group",
            "Test Name",
            "Result",
            "Unit",
            "Reference Range",
            "Method",
            "Abnormal"
        ]

        for col in required_cols:
            if col not in final_df.columns:
                final_df[col] = ""

        final_df["Min Range"], final_df["Max Range"] = zip(
            *final_df["Reference Range"].apply(parse_range_improved)
        )

        final_df = final_df[
            [
                "Category",
                "Test Group",
                "Test Name",
                "Result",
                "Unit",
                "Reference Range",
                "Method",
                "Min Range",
                "Max Range",
                "Abnormal"
            ]
        ]

    else:

        final_df = pd.DataFrame(
            columns=[
                "Category",
                "Test Group",
                "Test Name",
                "Result",
                "Unit",
                "Reference Range",
                "Method",
                "Min Range",
                "Max Range",
                "Abnormal"
            ]
        )

    return header_data, final_df