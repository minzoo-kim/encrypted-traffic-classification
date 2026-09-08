import argparse
import json
from pathlib import Path

import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

from feature_extraction import main, parse_labels


REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_COLUMNS = [
    "avg_pkt_size",
    "std_pkt_size",
    "max_pkt_size",
    "min_pkt_size",
    "avg_delta_time",
    "std_delta_time",
    "max_delta_time",
    "duration",
    "total_packets",
]


@pytest.mark.parametrize(
    ("filename", "expected_rows", "expected_accuracy"),
    [
        ("validation_data_nofilter.csv", 2400, 0.9521),
        ("validation_data.csv", 992, 0.9397),
    ],
)
def test_derived_csv_schema_and_reported_accuracy(
    filename: str, expected_rows: int, expected_accuracy: float
) -> None:
    frame = pd.read_csv(REPO_ROOT / "data" / filename)

    assert list(frame.columns) == [*FEATURE_COLUMNS, "class"]
    assert len(frame) == expected_rows
    assert set(frame["class"]) == {"control", "video", "download"}

    x_train, x_test, y_train, y_test = train_test_split(
        frame[FEATURE_COLUMNS],
        frame["class"],
        test_size=0.2,
        random_state=42,
        stratify=frame["class"],
    )
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(x_train, y_train)

    assert accuracy_score(y_test, model.predict(x_test)) == pytest.approx(
        expected_accuracy, abs=0.00005
    )


def test_notebook_has_result_but_no_local_windows_path() -> None:
    notebook_path = REPO_ROOT / "notebooks" / "01_traffic_classification.ipynb"
    raw = notebook_path.read_text(encoding="utf-8")
    notebook = json.loads(raw)
    outputs = json.dumps(
        [cell.get("outputs", []) for cell in notebook["cells"]], ensure_ascii=False
    )

    assert "97.08%" in outputs
    assert "C:\\\\Users\\\\" not in raw
    assert "AppData" not in raw


def test_parse_labels_rejects_missing_class() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="잘못된 --labels 항목"):
        parse_labels("folder=")


def test_empty_extraction_returns_nonzero(tmp_path: Path) -> None:
    output = tmp_path / "result.csv"

    exit_code = main(
        [
            "--input",
            str(tmp_path / "missing"),
            "--labels",
            "control=control",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 1
    assert not output.exists()
