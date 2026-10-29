from datetime import date

import pytest
import requests

from scripts.download_usgs_samples import (
    build_query,
    download,
    parse_csv_payload,
)


class FakeResponse:
    def __init__(self, content, url="https://example.test/results.csv"):
        self.content = content
        self.url = url

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        return self.response


def test_build_query_requires_bounded_parameter_and_preserves_identifiers():
    params = build_query(
        "USGS-04024315", date(2020, 1, 1), date(2020, 1, 31),
        characteristic="pH", usgs_parameter_code="00400",
    )
    assert params["monitoringLocationIdentifier"] == "USGS-04024315"
    assert params["activityStartDateLower"] == "2020-01-01"
    assert params["activityStartDateUpper"] == "2020-01-31"
    assert params["characteristic"] == "pH"
    assert params["usgsPCode"] == "00400"
    assert params["mimeType"] == "text/csv"


def test_build_query_rejects_unbounded_or_invalid_scope():
    with pytest.raises(ValueError):
        build_query("USGS-123", date(2020, 1, 1), date(2020, 1, 2))
    with pytest.raises(ValueError):
        build_query("USGS-12345", date(2020, 1, 2), date(2020, 1, 1), characteristic="pH")


def test_parse_csv_payload_counts_rows_and_keeps_header():
    header, count = parse_csv_payload(
        b"ActivityIdentifier,Characteristic,ResultMeasureValue\na1,pH,7.1\na2,pH,7.2\n",
        max_records=2,
    )
    assert header == ["ActivityIdentifier", "Characteristic", "ResultMeasureValue"]
    assert count == 2


def test_parse_csv_payload_handles_quoted_multiline_fields():
    payload = b'id,comment\\n1,"first line\\nsecond line"\\n2,"another\\nfield"\\n'
    header, count = parse_csv_payload(payload, max_records=2)
    assert header == ["id", "comment"]
    assert count == 2


def test_parse_csv_payload_rejects_html_and_excessive_results():
    with pytest.raises(ValueError):
        parse_csv_payload(b"<html><body>Service unavailable</body></html>", 10)
    with pytest.raises(ValueError):
        parse_csv_payload(b"a,b\n1,2\n2,3\n", 1)


def test_download_writes_immutable_raw_payload_and_audit(tmp_path):
    payload = (
        b"ActivityIdentifier,Characteristic,ResultMeasureValue,ResultMeasure/MeasureUnitCode\n"
        b"sample-1,pH,7.1,std units\n"
    )
    fake = FakeSession(FakeResponse(payload))
    output = tmp_path / "samples.csv"
    metadata = download(
        "USGS-04024315", date(2020, 1, 1), date(2020, 1, 31),
        "pH", None, output, session=fake,
    )
    assert output.read_bytes() == payload
    assert metadata["row_count"] == 1
    assert metadata["column_names"][0] == "ActivityIdentifier"
    assert len(metadata["sha256"]) == 64
    assert (tmp_path / "samples.csv.metadata.json").exists()
    assert fake.calls[0][2] == (15, 180)


def test_http_error_is_not_silently_swallowed(tmp_path):
    class ErrorResponse(FakeResponse):
        def raise_for_status(self):
            raise requests.HTTPError("rate limited")

    fake = FakeSession(ErrorResponse(b"a,b\n1,2\n"))
    with pytest.raises(requests.HTTPError):
        download(
            "USGS-04024315", date(2020, 1, 1), date(2020, 1, 31),
            "pH", None, tmp_path / "out.csv", session=fake,
        )
