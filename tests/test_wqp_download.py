from datetime import date

from scripts.download_wqp_pilot import format_wqp_date


def test_wqp_service_date_format():
    assert format_wqp_date(date(2020, 1, 9)) == "01-09-2020"
