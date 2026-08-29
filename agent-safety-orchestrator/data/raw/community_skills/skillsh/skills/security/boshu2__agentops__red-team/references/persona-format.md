# Persona Format

Red-team personas define constrained users who attempt real tasks. Unlike council perspectives (which judge quality from expert view), red-team personas define what they DON'T know.

## YAML Schema

```yaml
name: string           # kebab-case identifier (e.g., panicked-sre)
role: string           # Human-readable role description
context: string        # What the persona knows coming in
constraints:
  allowed_paths:       # Files/dirs the persona can access
    - string
  excluded_knowledge:  # What the persona explicitly doesn't know
    - string
  cannot:              # Actions the persona cannot take
    - string
goals:                 # What the persona is trying to accomplish
  - string
success_criteria: string  # How to measure success
time_pressure: bool       # Whether the persona is under time pressure
```

## Required Fields

All fields are required. `constraints` is what differentiates red-team personas from standard council perspectives -- it defines the knowledge boundary that makes the probe adversarial.

## Built-in Personas

### panicked-sre

```yaml
name: panicked-sre
role: "On-call SRE at 3am responding to a P1 incident"
context: "Basic Kubernetes knowledge, zero prior context on this project"
constraints:
  allowed_paths: ["docs/", "README.md"]
  excluded_knowledge:
    - "Internal architecture decisions"
    - "CLAUDE.md contents"
    - ".agents/ artifacts"
    - "Source code implementation details"
  cannot:
    - "grep source code for answers"
    - "read implementation files"
    - "access .agents/ directory"
goals:
  - "Find the correct runbook for the incident"
  - "Execute recovery procedure"
success_criteria: "Complete recovery in <=3 navigation hops with copy-paste commands"
time_pressure: true
```

### junior-engineer

```yaml
name: junior-engineer
role: "Day-1 junior engineer with basic language knowledge"
context: "Knows the programming language, basic git, understands what Kubernetes is"
constraints:
  allowed_paths: ["docs/", "README.md", "examples/"]
  excluded_knowledge:
    - "Project-specific jargon and acronyms"
    - "GitOps workflow patterns"
    - "Internal tooling conventions"
  cannot:
    - "ask a colleague for help"
    - "read CLAUDE.md or .agents/"
goals:
  - "Complete onboarding without hand-holding"
  - "Understand the architecture"
  - "Make a first change"
success_criteria: "Complete day-1 onboarding phases without external help"
time_pressure: false
```

### zero-context-agent

```yaml
name: zero-context-agent
role: "AI agent seeing this skill's SKILL.md for the first time"
context: "General AI agent capabilities, no project-specific knowledge"
constraints:
  allowed_paths: ["skills/<target>/SKILL.md", "skills/<target>/references/"]
  excluded_knowledge:
    - "Other skills in the catalog"
    - "Hook system behavior"
    - "CLI tool internals"
  cannot:
    - "read files outside the skill directory"
    - "infer behavior from other skills"
goals:
  - "Execute the skill workflow correctly from SKILL.md alone"
  - "Handle edge cases mentioned in the skill"
success_criteria: "Complete workflow without ambiguity or missing information"
time_pressure: false
```

### first-time-consumer

```yaml
name: first-time-consumer
role: "Developer trying to use this API/CLI for the first time"
context: "Experienced developer, zero knowledge of this specific tool"
constraints:
  allowed_paths: ["README.md", "docs/", "cli/docs/COMMANDS.md"]
  excluded_knowledge:
    - "Internal flag names not in --help"
    - "Undocumented environment variables"
    - "Source code patterns"
  cannot:
    - "read source code for answers"
    - "rely on tribal knowledge"
goals:
  - "Integrate or use the tool from the README alone"
  - "Recover from errors using only error messages"
success_criteria: "Complete happy-path task using only documented interfaces"
time_pressure: false
```

## Custom Personas

Projects define custom personas in `.agents/red-team/personas/*.yaml`. Each file contains one persona definition following the schema above.

When custom personas exist, they replace the built-in defaults for the matching surface type. To extend (not replace), include `extend_defaults: true` in the YAML.
