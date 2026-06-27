# Security and Support Policy

<p><b>English</b> | <a href="docs/SECURITY.zh-CN.md">简体中文</a></p>

This document describes the security research scope, maintainer support boundary, issue reporting process, and user compliance responsibilities for GSLOC-PROXY. It helps contributors and users determine which topics are appropriate for public discussion and which scenarios are outside project support.

## Project Scope

GSLOC-PROXY is intended only for security research, defensive testing, and mobile app location risk-control robustness validation on devices, apps, accounts, and controlled networks that you own or are authorized to test.

This project is a network-layer location integrity testing proxy. It is not a public proxy service, a general-purpose HTTPS MITM tool, an anti-detection tool, or a tool for bypassing third-party platform policies.

## Unsupported Requests

The maintainers will not provide issue replies, debugging support, feature implementation, configuration advice, deployment help, or any other assistance for the following scenarios:

- Bypassing attendance systems, games, financial services, delivery platforms, regional restrictions, anti-cheat systems, or platform risk controls.
- Testing third-party apps, third-party accounts, third-party devices, or unauthorized network environments.
- Hiding proxy usage, evading detection, simulating more realistic trajectories, aligning IP and location, or bypassing risk-control thresholds.
- Using this project as a public proxy, commercial proxy, shared proxy, or general-purpose MITM service.
- Collecting, storing, analyzing, or sharing other people's device, account, network, location context, or business data.
- Any unlawful, unauthorized, third-party-infringing, or clearly non-defensive use.

Related issues, discussions, or pull requests may be closed, deleted, or locked. The maintainers do not promise further explanation or continued communication.

## Acceptable Security Research Topics

Reports and improvements related to the following topics are welcome:

- Reproducibility, stability, and security boundaries in authorized lab environments.
- Host/path allowlists, fail-closed behavior, log redaction, and local-only defaults.
- Management API access control, least privilege, and local deployment security.
- Defensive detection, location trust scoring, and risk-control robustness guidance.
- Documentation wording that could cause misuse or misunderstanding.
- Security flaws in the project itself.

When submitting an issue, avoid including real accounts, device identifiers, BSSID/MAC values, raw packet captures, private CAs, keys, tokens, server addresses, full logs, or any third-party platform data. If you need to describe a logging-related issue, redact it first and include only the minimum necessary excerpt.

## Reporting Security Issues

If you discover a security issue in the project itself, please prefer GitHub's private vulnerability reporting feature on the repository Security page, or contact the maintainers through a private channel publicly listed in the repository profile. Please provide minimal reproducible information and avoid attaching sensitive packet captures, private keys, real device identifiers, full logs, or third-party business data.

## License and Responsibility

This project is released under the MIT License. The disclaimer in the license text applies to this project.

The README and this document describe the project scope, maintainer support policy, and responsible use boundary. Users are responsible for ensuring that their test environment, devices, accounts, network, and target apps are legally authorized and compliant with applicable laws and regulations, and they bear the compliance responsibility for their use of this project.
