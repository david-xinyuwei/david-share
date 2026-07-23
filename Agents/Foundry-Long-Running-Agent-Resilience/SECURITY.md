# Security Policy

## Public evidence boundary

This project accepts only public-safe summaries. Do not commit raw hosted-agent logs, credentials, endpoints, resource identifiers, private repository links, customer data, or local machine paths.

The deterministic gate rejects identity-bearing fields in committed evidence. The repository-level scanner also rejects common credential values, Azure resource identifiers, private hostnames, and absolute workstation paths.

## Reporting a concern

Use GitHub's private vulnerability reporting feature for this repository. Do not include active credentials or customer payloads in an issue, pull request, or discussion.

## Supported versions

Security fixes are applied to the current `master` branch. This validation kit is not a production service and exposes no network listener.
