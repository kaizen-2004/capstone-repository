# Coding Standards

## General
- Follow the surrounding code style first.
- Prefer clarity over cleverness.
- Keep control flow straightforward.
- Use descriptive names that match the repo’s naming style.
- Avoid unnecessary abstraction.
- Avoid dead code and commented-out code.

## Changes
- Keep diffs small and reviewable.
- Change only what is necessary for the task.
- Do not mix refactoring with bug fixes unless required.
- Reuse existing utilities and patterns before adding new ones.

## Errors and edge cases
- Handle realistic error paths.
- Do not suppress errors silently.
- Do not assume inputs are always valid unless the surrounding code already guarantees it.

## Comments
- Add comments only when the reasoning is not obvious from the code.
- Do not add noisy comments that restate the code.
