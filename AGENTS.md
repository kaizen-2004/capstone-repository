# Project Agent Rules

You are working in an existing codebase.

## Core behavior
- Do not start coding immediately.
- First inspect the codebase and explain the current behavior.
- Prefer root-cause fixes over surface-level patches.
- Prefer modifying existing files over creating new ones.
- Prefer minimal diffs over broad refactors.
- Preserve the current architecture unless explicitly asked to change it.
- Do not invent APIs, commands, file paths, config keys, or library behavior.
- If uncertain, say what is uncertain and inspect further before changing code.

## Workflow
For non-trivial tasks, follow this order:
1. Understand the request
2. Inspect relevant files and patterns
3. Explain findings
4. Propose a minimal plan
5. Implement only what is necessary
6. Validate with the narrowest relevant command
7. Summarize exactly what changed

## Editing rules
- Keep naming and style consistent with nearby code.
- Do not rewrite unrelated code.
- Do not introduce new dependencies unless necessary.
- Do not create helper abstractions unless they clearly reduce complexity.
- Keep functions, classes, and modules aligned with the project’s existing style.

## Safety rules
Ask before:
- deleting files
- changing build or deployment config
- adding dependencies
- performing broad refactors
- modifying database schema
- changing public APIs in a breaking way

## Testing rules
- If logic changes, add or update tests when the repo already uses tests.
- Run the smallest relevant validation first.
- Report what command was run and what the result was.

## Output format
For non-trivial tasks, respond in this structure:
1. Findings
2. Plan
3. Files to change
4. Implementation
5. Validation
6. Notes / risks
