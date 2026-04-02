# Testing Rules

## Philosophy
- Validate the specific change, not the whole universe.
- Start with the smallest relevant command.
- Only expand test scope if the first check shows broader impact.

## Preferred validation order
1. Focused test for the changed unit/module/file
2. Related package or directory tests
3. Broader project test or build
4. Full suite only when necessary

## Expectations
- State which command you plan to run.
- State whether it passed, failed, or could not be run.
- If no tests exist, use the narrowest available validation such as lint, typecheck, or build.
- If nothing can be run, say so explicitly instead of pretending validation happened.
