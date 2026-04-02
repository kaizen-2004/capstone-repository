# Agent Workflow

## Default operating flow
Use this workflow unless the task is trivial.

### Phase 1: Inspect first
- Read the relevant code before proposing edits.
- Identify the smallest set of files involved.
- Look for existing patterns already used in the repo.
- Reuse local conventions instead of inventing a new approach.

### Phase 2: Plan before patching
Before making changes, state:
- the likely root cause
- the files to change
- the smallest viable implementation
- edge cases
- how the change will be validated

### Phase 3: Implement carefully
- Make the smallest coherent patch.
- Preserve existing behavior outside the requested fix.
- Avoid speculative cleanup.

### Phase 4: Validate
Use the narrowest relevant command first, such as:
- one test file
- one package test
- one build target
- one lint command for touched files

### Phase 5: Report clearly
After changes:
- list the files changed
- summarize what changed
- state what command was run
- note any remaining risks or follow-up items
