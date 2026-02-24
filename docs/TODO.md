# TODO

---

## In Progress

- [ ] Working through phase1 smoketest - identifying issues
  - `phase1_plan` needs logging for:
    - Research plan goals + proposed search queries (vector_db_terms, pubmed_terms)
    - Track if plan came from structured invoke (try) vs regular invoke (except)

---

## Pending

(none)

---

## Completed

- [x] Move LLM params from `.env` to `config/default.yaml`
  - Added `LLMConfig` dataclass
  - Updated `LLMClient` to accept config
  - Updated `.env.example` to only contain secrets

---

## Notes

-
