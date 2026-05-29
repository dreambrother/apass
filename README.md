# APass

A dead-simple cross-platform password manager.

## Status

**Under active development.** CLI is functional — generates a password and copies it to the clipboard. Vault is a stub, passwords are not persisted yet.

## Features

| Feature                    | Status       |
| -------------------------- | ------------ |
| Password generation        | Done         |
| Copy to clipboard          | Done         |
| Password storage           | In progress  |
| Password rotation          | Planned      |
| Cloud sync                 | Planned      |
| Android client             | TODO         |

## CLI

Install and run:

```bash
cd cli
poetry install
poetry run apass create github
```

Prompts for a master password, generates a service password, copies it to clipboard,
and (eventually) stores it in an encrypted local vault.

Requires **Python ≥ 3.14**, Poetry 2.x.

### CLI roadmap

1. Storage: encrypt and persist passwords to `~/.apass/`.
2. Retrieval: `apass get <service>` — decrypt and copy to clipboard.
3. Rotation: `apass rotate <service>` — generate a new password and replace in vault.
4. Sync: optional sync of the encrypted vault to user's cloud storage (WebDAV / rclone-compatible remote).

## Android

TODO. Mobile client development begins after CLI and vault format stabilize.

### Android roadmap

1. List services and copy password to clipboard (without storing in system clipboard history).
2. Generate new password from the app.
3. Rotate password.
4. Sync with the same cloud backend as CLI.
