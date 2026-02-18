import os

import httpx


class JMAPClient:
    def __init__(self):
        self.user = os.environ.get("FASTMAIL_USER")
        self.token = os.environ.get("FASTMAIL_TOKEN")
        if not self.user or not self.token:
            raise RuntimeError(
                "FASTMAIL_USER and FASTMAIL_TOKEN must be set in environment or .env"
            )
        self._discover_session()

    def _discover_session(self):
        resp = httpx.get(
            "https://api.fastmail.com/.well-known/jmap",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        resp.raise_for_status()
        data = resp.json()
        self.api_url = data["apiUrl"]
        self.account_id = data["primaryAccounts"]["urn:ietf:params:jmap:mail"]

    def _jmap_call(self, method_calls: list) -> list:
        resp = httpx.post(
            self.api_url,
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "using": [
                    "urn:ietf:params:jmap:core",
                    "urn:ietf:params:jmap:mail",
                ],
                "methodCalls": method_calls,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        responses = data["methodResponses"]
        for r in responses:
            if r[0].endswith("/error"):
                raise RuntimeError(f"JMAP error: {r[1]}")
        return responses

    def get_inbox_emails(self, limit: int = 500) -> list[dict]:
        # First get inbox mailbox ID
        mailbox_resp = self._jmap_call([
            ["Mailbox/get", {"accountId": self.account_id, "ids": None}, "m0"]
        ])
        mailboxes = mailbox_resp[0][1]["list"]
        inbox_id = next(m["id"] for m in mailboxes if m.get("role") == "inbox")

        # Query + fetch in one request
        responses = self._jmap_call([
            [
                "Email/query",
                {
                    "accountId": self.account_id,
                    "filter": {"inMailbox": inbox_id},
                    "sort": [{"property": "receivedAt", "isAscending": False}],
                    "limit": limit,
                },
                "0",
            ],
            [
                "Email/get",
                {
                    "accountId": self.account_id,
                    "#ids": {
                        "resultOf": "0",
                        "name": "Email/query",
                        "path": "/ids",
                    },
                    "properties": [
                        "id",
                        "subject",
                        "from",
                        "preview",
                        "threadId",
                        "mailboxIds",
                        "keywords",
                        "header:List-Unsubscribe:asText",
                        "header:Precedence:asText",
                        "header:X-Mailer:asText",
                        "header:Content-Type:asText",
                    ],
                },
                "1",
            ],
        ])
        return responses[1][1]["list"]

    def get_mailbox_id(self, name: str) -> str:
        resp = self._jmap_call([
            ["Mailbox/get", {"accountId": self.account_id, "ids": None}, "m0"]
        ])
        mailboxes = resp[0][1]["list"]

        # Check by role first (for standard mailboxes like archive)
        role = name.lower()
        for m in mailboxes:
            if m.get("role") == role:
                return m["id"]

        # Then check by name (case-insensitive)
        for m in mailboxes:
            if m.get("name", "").lower() == name.lower():
                return m["id"]

        # Create if not found
        create_resp = self._jmap_call([
            [
                "Mailbox/set",
                {
                    "accountId": self.account_id,
                    "create": {"new": {"name": name}},
                },
                "c0",
            ]
        ])
        return create_resp[0][1]["created"]["new"]["id"]

    def batch_move(self, email_ids: list[str], destination_mailbox_id: str):
        chunk_size = 50
        for i in range(0, len(email_ids), chunk_size):
            chunk = email_ids[i : i + chunk_size]
            update = {
                eid: {"mailboxIds": {destination_mailbox_id: True}} for eid in chunk
            }
            resp = self._jmap_call([
                [
                    "Email/set",
                    {"accountId": self.account_id, "update": update},
                    "u0",
                ]
            ])
            not_updated = resp[0][1].get("notUpdated")
            if not_updated:
                raise RuntimeError(f"Failed to move emails: {not_updated}")
