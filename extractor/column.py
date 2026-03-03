# Column detection & interval building: detect_columns,
# build_header_based_intervals, refine_intervals_with_gaps

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
def refine_intervals_with_gaps(rows, header_y, col_pos, page_width, row_tol=4, gap_threshold=10):
    present_cols = [name for name in ["test", "result", "unit", "ref", "method"] if name in col_pos]
    present_cols.sort(key=lambda name: col_pos[name])
    intervals = build_header_based_intervals(col_pos, page_width)

    data_rows = [r for r in rows if r and r[0]["top"] > header_y + row_tol]
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
        if gap > gap_threshold:
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