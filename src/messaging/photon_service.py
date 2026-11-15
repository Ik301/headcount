"""Photon 2.0 (Beta) messaging service: iMessage in, deepagent reply out.

Run: .venv/bin/python -m src.messaging.photon_service
Env: PHOTON_API_KEY (pho_sk_..., project:read + project:write), PHOTON_PROJECT_ID (pho_prj_...),
     API_BASE (default http://127.0.0.1:8000, the analysis API that hosts /agent and the chart).

Polls list_messages for received messages every 2 s (docs: get-started/imessage), de-duplicates by message id,
and for each new text: typing indicator, "checking" text, POST /agent, the answer text, the chart image as an
attachment, then the menu text (numbered follow-ups and the dashboard link). Replies reuse the incoming space.id and receivedBy.id with a stable
idempotency key per incoming message, as the Photon docs require. Never answers its own outbound messages.
"""
import json
import os
import sys
import uuid
import time
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv
from photon_api import ApiError, Photon
from photon_api.generated.models import (
    SendAttachmentContent,
    SendMessageRequest,
    SendTextContent,
    TextContent,
    UserSnapshot,
)
from photon_api.rpc_generated import (
    ListMessagesInput,
    SendMessageHeader,
    SendMessageInput,
    SendMessagePath,
    UploadAttachmentHeader,
    UploadAttachmentInput,
    UploadAttachmentPath,
)

from src.api import reply  # noqa: E402  (pure text helpers: intent routing, no analysis state)

CHECKING = "Checking who is pushing that. About 20 seconds."


def send_text(photon: Photon, project: str, space: str, sender: str, parent: str, key: str, text: str) -> None:
    photon.projects.send_message(
        SendMessageInput(
            path=SendMessagePath(id=project),
            headers=SendMessageHeader.model_validate({"idempotency-key": key}),
            body=SendMessageRequest(spaceId=space, senderId=sender, parentMessageId=parent, content=SendTextContent(type="text", format="plain", text=text)),
        )
    )


def multipart_related(png: bytes, filename: str = "chart.png", content_type: str = "image/png") -> tuple[str, bytes]:
    """Photon's uploadAttachment wants exactly two parts: JSON metadata (contentType, sizeBytes, filename), then the file bytes."""
    boundary = uuid.uuid4().hex
    meta = json.dumps({"contentType": content_type, "sizeBytes": len(png), "filename": filename})
    body = (
        f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{meta}\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n"
    ).encode() + png + f"\r\n--{boundary}--\r\n".encode()
    return f'multipart/related; boundary="{boundary}"', body


def send_image(photon: Photon, project: str, space: str, sender: str, parent: str, key: str, png: bytes) -> None:
    ctype, body = multipart_related(png)
    att = photon.projects.upload_attachment(
        UploadAttachmentInput(
            path=UploadAttachmentPath(id=project),
            headers=UploadAttachmentHeader(content_length=str(len(body)), content_type=ctype, idempotency_key=key + ":upload"),
            body=body,
        )
    )
    photon.projects.send_message(
        SendMessageInput(
            path=SendMessagePath(id=project),
            headers=SendMessageHeader.model_validate({"idempotency-key": key}),
            body=SendMessageRequest(spaceId=space, senderId=sender, parentMessageId=parent, content=SendAttachmentContent(type="attachment", attachmentId=att.id)),
        )
    )


def handle(photon: Photon, api: httpx.Client, project: str, m) -> None:
    space, agent_id, mid = m.space.root.id, m.receivedBy.root.id, m.id
    text = m.content.text.strip()
    human = m.sentBy.root.id
    if reply.intent(text) is None:  # help and the numbered follow-ups answer at once, so no "checking" bubble
        send_text(photon, project, space, agent_id, mid, f"ack:{mid}", CHECKING)
    try:
        r = api.post("/agent", json={"sender": human, "text": text}, timeout=120).json()
    except (httpx.HTTPError, ValueError) as e:
        print(f"agent call failed for {mid}: {e}", file=sys.stderr)
        send_text(photon, project, space, agent_id, mid, f"err:{mid}", "Something went wrong on our side. Try again in a minute.")
        return
    send_text(photon, project, space, agent_id, mid, f"reply:{mid}", r.get("reply_text") or "No answer.")
    if r.get("chart_png_url"):
        try:
            png = api.get(r["chart_png_url"], timeout=30).content
            send_image(photon, project, space, agent_id, mid, f"chart:{mid}", png)
        except (httpx.HTTPError, ApiError) as e:
            print(f"chart send failed for {mid}: {e}", file=sys.stderr)
    if r.get("menu_text"):  # third bubble, after the image, so the menu is what the texter sees last
        send_text(photon, project, space, agent_id, mid, f"menu:{mid}", r["menu_text"])


def main() -> None:
    load_dotenv()
    key, project = os.environ["PHOTON_API_KEY"], os.environ["PHOTON_PROJECT_ID"]
    api = httpx.Client(base_url=os.environ.get("API_BASE", "http://127.0.0.1:8000"))
    seen: set[str] = set()
    since = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    started = datetime.now(timezone.utc)
    with Photon(headers={"Authorization": f"Bearer {key}"}) as photon:
        print("Ready. Waiting for messages.", flush=True)
        while True:
            query = {"createdSince": since, "direction": "received", "order": "asc", "pageSize": 100, "platform": "imessage"}
            try:
                while True:
                    page = photon.projects.list_messages(ListMessagesInput.model_validate({"path": {"id": project}, "query": query}))
                    for item in page.items:
                        m = item.root.root
                        if m.id in seen or m.status != "received" or datetime.fromisoformat(m.createdAt) < started:
                            continue
                        seen.add(m.id)
                        if not isinstance(m.receivedBy, UserSnapshot) or m.sentBy.root.kind != "human" or m.receivedBy.root.kind != "agent":
                            continue
                        if not isinstance(m.content, TextContent) or not m.content.text.strip():
                            continue
                        print(f"message {m.id}: {m.content.text[:60]!r}", flush=True)
                        try:
                            handle(photon, api, project, m)
                        except ApiError as e:
                            print(f"Photon API error {e.status} on {m.id} (request {e.request_id or 'unknown'})", file=sys.stderr)
                    token = page.nextPageToken
                    if not isinstance(token, str):
                        break
                    query["pageToken"] = token
            except ApiError as e:
                print(f"Photon API error {e.status} while polling (request {e.request_id or 'unknown'})", file=sys.stderr)
                time.sleep(10 if e.status == 429 else 3)
            time.sleep(2)


if __name__ == "__main__":
    main()
