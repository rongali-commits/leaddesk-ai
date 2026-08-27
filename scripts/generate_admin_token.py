"""Generate a deployment-safe LeadDesk admin token."""

import secrets

if __name__ == "__main__":
    print(secrets.token_urlsafe(36))

