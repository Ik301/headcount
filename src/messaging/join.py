"""Judge onboarding for Photon shared iMessage lines.

A shared line only accepts texts from a registered sender, so the QR code opens GET /join, the judge enters
their iMessage phone number or email, and POST /join creates a shared-line assignment for it (Photon Beta:
projects.platforms.imessage.assignments.create, needs platforms:write) and shows the number to text.
Free plan: 25 assignments per project.
"""
import hashlib
import os
import re

from photon_api import ApiError, Photon
from photon_api.generated.models import CreateSharedLineAssignmentRequest
from photon_api.rpc_generated import CreateSharedLineAssignmentHeader, CreateSharedLineAssignmentInput, CreateSharedLineAssignmentPath

PAGE = """<!doctype html><html><head><meta name=viewport content="width=device-width,initial-scale=1">
<title>Check a claim</title><style>body{{font-family:system-ui;max-width:420px;margin:40px auto;padding:0 16px}}
input,button{{font-size:18px;padding:10px;width:100%;box-sizing:border-box;margin:6px 0}}</style></head><body>
<h2>Text us a claim</h2><p>Enter the phone number (with country code, like +1609...) or Apple ID email you use for iMessage.
We use it only to let you text our agent during the demo.</p>
<form method=post action=/join><input name=handle placeholder="+16095551234" required><button>Get the number</button></form>
{msg}</body></html>"""


def normalize(handle: str) -> str | None:
    h = handle.strip()
    if "@" in h:
        return h.lower() if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", h) else None
    digits = re.sub(r"[^\d+]", "", h)
    if not digits.startswith("+"):
        digits = "+1" + digits if len(digits) == 10 else "+" + digits
    return digits if re.fullmatch(r"\+\d{10,15}", digits) else None


def assign(handle: str) -> str:
    key, project = os.environ["PHOTON_API_KEY"], os.environ["PHOTON_PROJECT_ID"]
    idem = "join:" + hashlib.sha1(handle.encode()).hexdigest()[:16]
    with Photon(headers={"Authorization": f"Bearer {key}"}) as photon:
        a = photon.projects.platforms.imessage.assignments.create(
            CreateSharedLineAssignmentInput(
                path=CreateSharedLineAssignmentPath(id=project),
                headers=CreateSharedLineAssignmentHeader.model_validate({"Idempotency-Key": idem}),
                body=CreateSharedLineAssignmentRequest(handle=handle),
            )
        )
    return a.assignedPhoneNumber


def page(msg: str = "") -> str:
    return PAGE.format(msg=msg)


def join(handle_raw: str) -> str:
    h = normalize(handle_raw)
    if not h:
        return page("<p style=color:#c00>That doesn't look like a phone number or email.</p>")
    try:
        number = assign(h)
    except ApiError as e:
        return page(f"<p style=color:#c00>Couldn't register that (Photon error {e.status}). Ask the team to text for you.</p>")
    return page(
        f"<h3>Text <a href='sms:{number}&body=Was Jensen Huang\\'s mistress a Chinese spy?'>{number}</a></h3>"
        "<p>Send it as an iMessage from the number or email you entered. Try any claim about the Jensen Huang story.</p>"
    )
