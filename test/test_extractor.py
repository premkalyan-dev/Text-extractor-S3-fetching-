from extractor.extractor import extract_lab_data

def test_valid_pdf():
    header, df = extract_lab_data(r"C:\Users\premk\OneDrive\Desktop\DiagnoiQ\Text_extractor+db_main\reports\__Moksith_23_03_2026_02_34_52_PM.pdf")

    # Check dataframe is created
    assert df is not None

    # Check dataframe is not empty
    assert not df.empty

    # Check required columns exist
    required_cols = [
        "Category", "Test Group", "Test Name",
        "Result", "Unit", "Reference Range",
        "Method", "Min Range", "Max Range", "Abnormal"
    ]

    for col in required_cols:
        assert col in df.columns