from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st

from jovykit.deps import add_packages, remove_packages


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


def test_add_packages_creates_manifest_when_missing(tmp_path: Path) -> None:
    requirements = tmp_path / "nested" / "requirements.txt"

    added = add_packages(requirements, ["", " scipy ", "scipy"])

    assert added == ["scipy"]
    assert requirements.read_text(encoding="utf-8").splitlines() == [
        "# Project packages managed by JovyKit.",
        "scipy",
    ]


def test_remove_packages_removes_exact_manifest_entries(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("# existing\nnumpy\npandas\nrequests\n", encoding="utf-8")

    removed = remove_packages(requirements, ["pandas", "missing"])

    assert removed == ["pandas"]
    assert requirements.read_text(encoding="utf-8").splitlines() == [
        "# existing",
        "numpy",
        "requests",
    ]


package_text = st.text(
    alphabet=st.sampled_from(
        list(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-<>=!~[] ,"
        )
    ),
    min_size=0,
    max_size=20,
)


@given(st.lists(package_text, max_size=20))
def test_add_packages_is_idempotent(packages: list[str]) -> None:
    with TemporaryDirectory() as temp_dir:
        requirements = Path(temp_dir) / "requirements.txt"

        first_added = add_packages(requirements, packages)
        second_added = add_packages(requirements, packages)

    expected_added = []
    for package in packages:
        normalized = package.strip()
        if normalized and normalized not in expected_added:
            expected_added.append(normalized)

    assert second_added == []
    assert first_added == expected_added
