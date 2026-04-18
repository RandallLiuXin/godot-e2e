# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | Yes      |
| 1.0.x   | Yes      |

## The E2E Server Security Model

The godot-e2e automation server is designed for **testing environments only**.
It should never be enabled in production builds. Key safeguards:

- The server only activates when the `--e2e` command-line flag is present
- Token-based authentication prevents unauthorized connections
- The server binds to localhost only (not exposed to network)
- Only one client connection is accepted at a time

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Use [GitHub Security Advisories](https://github.com/RandallLiuXin/godot-e2e/security/advisories/new) to report privately
3. Include: description, reproduction steps, potential impact
4. We will respond within 7 days

## Scope

Security concerns within scope:
- Unauthorized command execution via the TCP server
- Token bypass or authentication issues
- Path traversal via screenshot or scene commands

Out of scope:
- Vulnerabilities in Godot Engine itself
- Issues that require the `--e2e` flag to already be enabled in production
