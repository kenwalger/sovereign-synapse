# Security Policy

## Our Sovereignty Commitment
Sovereign Synapse is designed to keep your data on **your silicon**. By default, this application does not connect to the internet to process your chat logs or notebooks.

## Reporting a Vulnerability
If you discover a bug that could lead to "Cloud Leakage" (data being inadvertently sent to a third-party server) or a local data corruption issue:
1. Please **do not** open a public issue immediately.
2. Email the maintainer at [Your Email/Contact] with the details.
3. We will work to verify and fix the leak before a public disclosure is made.

## Best Practices for Users
- **.gitignore:** Always ensure your `raw_data/` and `vault/` folders are listed in your `.gitignore`.
- **Environment Variables:** Never hardcode paths or keys in the source code; use `.env` files.