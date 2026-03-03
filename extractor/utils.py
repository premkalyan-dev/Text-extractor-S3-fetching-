# General helpers: strip_page_markers, parse_range_improved,
# deduplicate_by_completeness, contains_header_words

import re
import pandas as pd

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