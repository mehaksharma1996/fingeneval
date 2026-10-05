from src.utils import text_fingerprint


def test_text_fingerprint_is_stable_across_line_endings(tmp_path):
    lf_path = tmp_path / "lf.csv"
    crlf_path = tmp_path / "crlf.csv"
    lf_path.write_bytes(b"column\nvalue\n")
    crlf_path.write_bytes(b"column\r\nvalue\r\n")

    assert text_fingerprint(lf_path) == text_fingerprint(crlf_path)
