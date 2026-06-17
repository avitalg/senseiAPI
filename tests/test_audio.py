from tests.conftest import DEFAULT_TRANSCRIPT, ClientFactory


def test_upload_audio_returns_201_and_persists_file(make_client: ClientFactory) -> None:
    client, settings = make_client()
    content = b"ID3 fake-audio-bytes"
    res = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", content, "audio/mpeg")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["filename"] == "song.mp3"
    assert body["content_type"] == "audio/mpeg"
    assert body["size_bytes"] == len(content)
    assert body["id"].endswith(".mp3")

    stored = settings.upload_dir / body["id"]
    assert stored.exists()
    assert stored.read_bytes() == content


def test_upload_audio_returns_transcript(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"fake-audio-bytes", "audio/mpeg")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["language"] == "he"
    assert body["text"] == DEFAULT_TRANSCRIPT


def test_upload_audio_accepts_m4a(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.post(
        "/audio/upload",
        files={"file": ("voice.m4a", b"fake-m4a", "audio/x-m4a")},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["content_type"] == "audio/x-m4a"
    assert body["id"].endswith(".m4a")


def test_upload_audio_rejects_unsupported_type(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.post(
        "/audio/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 415


def test_upload_audio_rejects_empty_file(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.post(
        "/audio/upload",
        files={"file": ("empty.mp3", b"", "audio/mpeg")},
    )
    assert res.status_code == 400


def test_upload_audio_rejects_too_large(make_client: ClientFactory) -> None:
    client, _ = make_client(max_upload_bytes=4)
    res = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"too-long-content", "audio/mpeg")},
    )
    assert res.status_code == 413


def test_upload_audio_requires_file(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.post("/audio/upload")
    assert res.status_code == 422


def test_list_audio_is_empty_initially(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.get("/audio")
    assert res.status_code == 200
    assert res.json() == []


def test_list_audio_returns_uploaded_files(make_client: ClientFactory) -> None:
    client, _ = make_client()
    uploaded = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"abc", "audio/mpeg")},
    ).json()
    res = client.get("/audio")
    assert res.status_code == 200
    body = res.json()
    assert body == [{"id": uploaded["id"], "size_bytes": 3}]


def test_download_audio_returns_content(make_client: ClientFactory) -> None:
    client, _ = make_client()
    content = b"fake-audio-content"
    uploaded = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", content, "audio/mpeg")},
    ).json()
    res = client.get(f"/audio/{uploaded['id']}")
    assert res.status_code == 200
    assert res.content == content
    assert res.headers["content-type"].startswith("audio/mpeg")


def test_download_audio_missing_returns_404(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.get("/audio/does-not-exist.mp3")
    assert res.status_code == 404


def test_download_audio_rejects_path_traversal(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.get("/audio/..%2F..%2Fetc%2Fpasswd")
    assert res.status_code == 404


def test_delete_audio_returns_204_then_404(make_client: ClientFactory) -> None:
    client, settings = make_client()
    uploaded = client.post(
        "/audio/upload",
        files={"file": ("song.mp3", b"abc", "audio/mpeg")},
    ).json()
    audio_id = uploaded["id"]

    assert client.delete(f"/audio/{audio_id}").status_code == 204
    assert not (settings.upload_dir / audio_id).exists()
    assert client.get(f"/audio/{audio_id}").status_code == 404


def test_delete_audio_missing_returns_404(make_client: ClientFactory) -> None:
    client, _ = make_client()
    res = client.delete("/audio/does-not-exist.mp3")
    assert res.status_code == 404
