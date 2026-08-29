# FORGE Token Efficiency

FORGE should reduce drift and rework without becoming a large token tax.

## High-Value Rules

- Load only the files required for the current step.
- Prefer compact structured outputs over narrative explanations.
- Do not re-read unchanged repo-local docs repeatedly in one execution pass.
- Use the coordination branch only when claim or task-state transitions require it.
- Read only the relevant sections of `SECURITY_CHECKLISTS.md`, not the whole file.
- Keep `MEMORY.md` entries short and high-signal.
- Prefer fixed response shapes over free-form summaries.

## Where Tokens Usually Leak

- restating the selected task or project context in every response
- reading every governance doc at the start of every step
- narrating routine inspection and planning steps
- verbose critique and evaluation writeups
- copying all security checklist sections into every project
- echoing generated file contents back into chat
- repeated warnings about expected branch drift in team mode

## Practical Default

FORGE should behave more like:

- short action updates
- narrow file loads
- direct edits
- compact gate results
- `Done / Changed / Next` closeouts

and less like:

- long conversational explanation
- repeated context recap
- exhaustive changelog narration
- prose summaries of reasoning already stored in files
