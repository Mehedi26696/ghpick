from zipfile import ZipFile

from ghpick.downloader.zip_creator import create_zip


def test_create_zip_preserves_relative_paths(tmp_path):
    source = tmp_path / "source"
    nested = source / "backend" / "auth"
    nested.mkdir(parents=True)
    (nested / "jwt.py").write_text("TOKEN = 'demo'", encoding="utf-8")

    archive = create_zip(source, tmp_path / "backend.zip")

    with ZipFile(archive) as zip_file:
        assert zip_file.namelist() == ["backend/auth/jwt.py"]
