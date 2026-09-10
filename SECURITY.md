# Security Policy

## Reporting

Do not open a public issue containing credentials, production event payloads, or exploit details.
Use GitHub's private vulnerability reporting for this repository when available.

Include the affected revision, impact, minimal reproduction, and any evidence that sensitive data
was exposed. Remove tokens, signatures, webhook secrets, provider response bodies, and personal data
from reports.

## Supported versions

This engineering lab supports the latest revision of the default branch. It is not a hosted service
and does not publish long-term support releases.

## Deployment warning

The development operator-header mechanism is intentionally disabled outside the development
environment. Production deployment requires a real identity provider, destination egress controls,
managed secrets, rate limits, retention controls, and calibrated monitoring. See the threat model.
