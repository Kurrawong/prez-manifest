from pathlib import Path

try:
    from prezmanifest import validate
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parent.parent.resolve()))
    from prezmanifest import validate


def test_validator_valid():
    assert validate(Path(__file__).parent / "demo-vocabs" / "manifest.ttl")


def test_validator_invalid_01():
    try:
        validate(
            Path(__file__).parent / "demo-vocabs" / "manifest-invalid-01.ttl"
        )
    except ValueError as e:
        assert str(e).startswith("SHACL invalid")


def test_validator_invalid_03():
    try:
        validate(
            Path(__file__).parent / "demo-vocabs" / "manifest-invalid-02.ttl"
        )
    except ValueError as e:
        assert str(e) == "The content link vocabz/*.ttl is not a directory"


def test_validator_invalid_02():
    try:
        validate(
            Path(__file__).parent / "demo-vocabs" / "manifest-invalid-03.ttl"
        )
    except ValueError as e:
        assert (
            str(e)
            == "Remote content link non-resolving: https://github.com/RDFLib/prez/blob/main/prez/reference_data/profiles/ogc_records_profile.ttlx"
        )
