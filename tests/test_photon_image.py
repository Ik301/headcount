import json
from unittest.mock import MagicMock

from src.messaging import photon_service as ps

PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4


def test_multipart_related_shape():
    ctype, body = ps.multipart_related(PNG)
    assert ctype.startswith("multipart/related; boundary=")
    boundary = ctype.split("boundary=")[1].strip('"')
    parts = body.split(f"--{boundary}".encode())
    assert parts[-1] == b"--\r\n" and len(parts) == 4
    head, meta = parts[1].split(b"\r\n\r\n", 1)
    assert b"application/json" in head
    m = json.loads(meta.rstrip(b"\r\n"))
    assert m["contentType"] == "image/png" and m["sizeBytes"] == len(PNG)
    fhead, fbody = parts[2].split(b"\r\n\r\n", 1)
    assert b"image/png" in fhead and fbody == PNG + b"\r\n"


def test_send_image_uploads_multipart_then_sends_attachment():
    photon = MagicMock()
    photon.projects.upload_attachment.return_value.id = "att_1"
    ps.send_image(photon, "pho_prj_x", "space", "agent", "parent", "chart:1", PNG)
    inp = photon.projects.upload_attachment.call_args.args[0]
    assert inp.headers.content_type.startswith("multipart/related")
    assert inp.headers.content_length == str(len(inp.body.root))
    assert inp.headers.idempotency_key == "chart:1:upload"
    sent = photon.projects.send_message.call_args.args[0]
    assert sent.body.content.attachmentId == "att_1"
