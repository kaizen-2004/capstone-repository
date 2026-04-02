# Change Safety

## Avoid risky behavior
- Do not make speculative changes.
- Do not assume a dependency or framework API without checking the repo or docs already present in the project.
- Do not silently change behavior outside the request.
- Do not perform mass formatting changes unless requested.

## Escalate before doing these
- deleting or moving many files
- changing CI, Docker, deployment, or environment config
- introducing new packages or services
- changing storage schemas or migrations
- changing auth, security, or permissions logic broadly

## Reversibility
- Prefer changes that are easy to review and revert.
- Keep patches logically grouped.
