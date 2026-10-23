# ADR 0002: Licensing

**Status:** Accepted (23 October 2026, owner decision).

**Decision:** the repository is licensed under the Apache License, Version 2.0 (`LICENSE`), copyright Huda
Mueen 2026 (`NOTICE`). `pyproject.toml` declares `Apache-2.0`.

**Reasoning:**

- It includes an express patent grant from contributors, which MIT does not, so a university or a company
  that reuses the code has a clear position on patents.
- It is permissive: academic groups and defence industry partners can reuse and adapt the code, including in
  closed products, provided they keep the notices and state their changes.
- It is widely accepted by university technology transfer offices and by industry legal review, which lowers
  the cost of a later collaboration.

**Options considered:** MIT (simplest, no patent grant); keeping all rights reserved (public to read, nobody
may reuse, which blocks the collaboration the project seeks).

**Consequences:** contributions are accepted under the same licence. The licence covers the code and
documents only; it grants no rights over data that partners collect, which stays with them (for example the
robot data of the AAU logging session, `docs/proposals/aau-robotics-proposal.md`). Licensing makes no claim
about fitness for any use; the evidence level of every profile is still L0.
