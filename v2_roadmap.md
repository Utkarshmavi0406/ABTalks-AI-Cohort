# v2 Roadmap

Prioritized by what would matter most if this were headed toward real use, informed directly by what this program's testing and debugging actually surfaced — not a generic feature wishlist.

## Priority 0 — Blocking, before touching any real member data

**A formal compliance and legal review.** Everything in this project — the PII redaction (Day 25), the guardrails, the governance checklist — is a genuine, careful learning exercise, but it is not a substitute for real HIPAA risk assessment, legal review of disclaimer language, a Business Associate Agreement with any third-party model provider, or professional security penetration testing. `GOVERNANCE.md` says this explicitly and it bears repeating here: **nothing in this codebase should touch a real member's data until that review has happened.**

## Priority 1 — Fixes directly motivated by findings during this program

- **A health check that actually exercises the Ollama connection**, not just a static `{"status": "ok"}`. Day 31's capstone walkthrough (and Day 30's kubectl debugging exercise before it) both demonstrated concretely that the current probe cannot detect a broken LLM connection — a pod can report itself as fully healthy while every real request fails.
- **Retrieval-layer PHI filtering**, not just output-side redaction. Day 25's adversarial testing found that a PHI-fishing question could pull a real enrollment record (containing a synthetic member's name, address, phone) directly into the model's context — the only thing preventing disclosure was the model's own restraint, not an explicit safeguard.
- **Less aggressive claim-ID redaction.** Day 31's walkthrough found that any claim-status answer triggers a `[SAFETY NOTICE]`-flagged duplicate, since a claim ID like `C1001` matches the same pattern used for detecting leaked identifiers — even when a member is legitimately asking about their own claim. Worth narrowing the redaction rule to avoid this false-positive noise on every single claim lookup.
- **A minimal CI/CD pipeline** that rebuilds the Docker image and runs a smoke test whenever code or dependencies change. Day 31's Langfuse-trace investigation ultimately traced back to a stale Kubernetes image that had never been rebuilt after a dependency was added — exactly the class of drift automated builds exist to prevent.

## Priority 2 — Capability expansion

- **Multi-modal (image) support for scanned documents.** The enrollment form processed back on Day 5 was already a scanned/OCR'd document; a real system should be able to accept and reason over uploaded images/PDFs directly, not just pre-processed text.
- **Voice input/output**, for accessibility and for members who'd rather call than type.
- **Additional languages.** Current guardrails, prompts, and retrieval are all English-only; a real member population would need at minimum Spanish support given the healthcare context.

## Priority 3 — Scaling and infrastructure maturity

- **Move from local Minikube to a managed cloud Kubernetes service** (e.g. GKE, EKS). This program's own experience makes a concrete case for this: Day 31 ended with Minikube's local container storage becoming corrupted mid-operation, requiring a full cluster rebuild — the kind of infrastructure fragility a managed control plane with real persistent storage guarantees would eliminate entirely.
- **Real persistent storage for the vector DB and SQLite data** (a managed database service, not files baked into a container image or a local `hostPath` volume) — today's approach works for a single-developer local demo but isn't how production data should be handled.
- **Autoscaling and multi-region deployment**, once there's real traffic data to size for.
