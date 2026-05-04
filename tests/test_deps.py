from pathlib import Path

from labkit.deps import add_packages


def test_add_packages_appends_only_new_entries(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("# existing\nnumpy\n", encoding="utf-8")

    added = add_packages(requirements, ["numpy", "polars", " requests "])

    assert added == ["polars", "requests"]
    assert requirements.read_text(encoding="utf-8").splitlines() == [
        "# existing",
        "numpy",
        "polars",
        "requests",
    ]
