# Backend

- [ ] Server-side authorization is enforced at the correct boundary and is not delegated only to the client.
- [ ] Input validation occurs before privileged actions, data writes, or downstream service calls.
- [ ] Error handling does not leak stack traces, secrets, or internal topology.
- [ ] Background jobs, workers, or internal service calls operate with the minimum required privilege.
