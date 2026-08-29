# Architecture

## Summary

Document only the project-specific architectural constraints that should shape implementation decisions.

## Constraints

- Constraint:

## Contract Artifacts

List shared interface files that must stay aligned across implementation
boundaries, for example OpenAPI, protobuf, GraphQL schema, AsyncAPI, generated
client config, or database migration contracts.

- Contract file:
- Owners:
- Rule: API, client, or integration-boundary changes must update the relevant
  contract file in the same task, PR, or MR unless the task explicitly records a
  separate owner and link for the contract change.

## Trust Boundaries

- Boundary:
