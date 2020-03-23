intelephense_before_state = """<?php
$hello = "world";
$he
?>
"""

intelephense_expected_state = """<?php
$hello = "world";
$hello
?>
"""

intelephense_response = {"items": [{"label": "$hello", "textEdit": {"newText": "$hello", "range": {"end": {"line": 2, "character": 3}, "start": {"line": 2, "character": 0}}}, "data": 2369386987913238, "detail": "int", "kind": 6, "sortText": "$hello"}], "isIncomplete": False}  # noqa: E501
