---
description: Implement the approved plan with minimal diffs
agent: build
---

Implement the approved plan with the smallest coherent diff.

Rules:
- preserve existing architecture
- avoid unrelated refactors
- do not add dependencies unless necessary
- follow surrounding style
- run the narrowest useful validation command
- summarize exactly what changed
