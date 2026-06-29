"""
core.tools.notifier
===================
A reusable, channel-agnostic notification tool. It formats a message and hands
it to a *pluggable sink* — by default it just logs (safe everywhere), but a real
deployment can inject an email/Slack/SMS sender without touching any agent:

    registry.register(NotifierTool(sink=my_email_sender), overwrite=True)

The sink is any callable taking the message dict. Keeping transport here (and
routing/content in the domain agent) is what makes this reusable across use cases.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from core.tools.base_tool import BaseTool


class NotifierTool(BaseTool):
    name = "notifier"
    description = "Format and dispatch a notification through a pluggable sink."
    params = {
        "to": "recipient (role or address)",
        "subject": "message subject",
        "body": "message body",
        "channel": "delivery channel: email / slack / sms (default email)",
    }

    def __init__(self, sink: Optional[Callable[[Dict[str, Any]], None]] = None) -> None:
        super().__init__()
        self._sink = sink  # injectable transport; None => log only

    def _run(self, to: str, subject: str = "", body: str = "", channel: str = "email", **_: Any) -> Dict[str, Any]:
        msg: Dict[str, Any] = {"to": to, "subject": subject, "body": body, "channel": channel}
        try:
            if self._sink is not None:
                self._sink(msg)
                msg["status"] = "sent"
            else:
                self.log.info("notify[%s] -> %s | %s", channel, to, subject)
                msg["status"] = "queued"
        except Exception as exc:  # noqa: BLE001
            msg["status"] = "failed"
            msg["error"] = str(exc)
        return msg
