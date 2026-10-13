# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub: **Security → Report a vulnerability** on <https://github.com/carlok/aristowrap/security/advisories/new>. Do not open a public issue for them. You can expect a first reply within about a week.

## Scope and trust model

- `aristowrap verify` runs `lake build` on an archive returned by a remote service. Lean can execute code during a build, so treat that archive as untrusted. See *Security notes* in the [README](README.md#security-notes) for how to run `verify` without your API key and with a read-only mount.
- Archives are extracted with `tarfile`'s `data` filter; members that escape the extraction directory are rejected.
- The image contains no secrets. `ARISTOTLE_API_KEY` is supplied at run time through `aristotle.env`, which is git-ignored and excluded from the Docker build context. Never commit it.

## Supported versions

Only the latest release and `main` receive fixes.
