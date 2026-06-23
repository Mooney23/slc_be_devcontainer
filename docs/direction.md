# Scoped Agent Harness — Direction

> **North star:** This repo is the least-privilege blast-radius layer for agentic backend work — the thing that lets an agent run the full developer lifecycle (dev → deploy → invoke → observe) with each capability scoped so that a mistake, or a hijacked agent, can't reach further than intended.

This is the direction doc for evolving this repo (the hardened Python dev-container base + per-service scaffolding, plus the `slc-plugins` marketplace) from "a dev environment that happens to run Claude Code" into a deliberate, least-privilege **agent environment**.

It grew out of two internal planning notes — a decomposition of developer work into Development / Deployment / Invocation / Observability, and a concrete read-only Postgres access spec (SSH tunnel + read-only role + SQL validation gate). Their substance is folded in below; the DB spec is the first capability slated to land in-repo.

---

## The reframe: scoping is *the* problem, not an observability detail

The original thesis treated Dev / Deploy / Invoke as "basically solved" and Observability as the hard one, because an agent's log / DB permissions are too broad. The sharper read:

**Every stage's hard part is the same — bounding the blast radius of an agent's action.**

- Dev *feels* solved only because it's already bounded — a throwaway container + git is a tight blast radius.
- Deploy / Invoke / Observe feel unsolved because we haven't bounded them yet. "Push a branch" and "hit an endpoint" are easy for a human; for an agent the hard part is identical to observability's — *what stops it doing more than you meant?*

So the repo isn't acquiring features. It's a sequence of "bound the next thing." The firewall bounded the network. A read-only DB role bounds the data. Each capability we add closes one more blast radius, until the agent can own a ticket end-to-end.

## What we're building (and what we're not)

Three altitudes:
- **The model** (Claude) — the intelligence.
- **The agent / harness** (Claude Code) — model in a loop with tools + permissions. *We use this; we don't build it.*
- **The environment the harnessed agent runs inside** — sandbox + scoped capabilities + guardrails. **This is what this repo is, and what we're extending.**

We are not building an agent. We're building the **scoped agent environment** the agent is dropped into.

> Vocabulary: the precise category is an *agent environment* / *agent runtime*; the differentiator worth naming is the scoping. "Scoped agent harness" / "least-privilege agent environment" both work; "agentic dev environment" is where the industry term is converging.

## The durable contract (delivery mechanism stays open)

Three layers are fixed. *How each ships — baked into the base image vs. shipped as a marketplace plugin — is a deliberately late-bound, per-capability decision.* We do **not** lock that in here.

| Layer | What it does | Exists today as |
|---|---|---|
| **Sandbox** | the bounded place the agent runs | devcontainer + default-deny firewall |
| **Capability** | one scoped power (deploy, query DB, search logs, invoke) | marketplace plugins |
| **Guardrail** | makes the capability least-privilege | firewall allowlist; a read-only DB role + validation script |

**Every capability must carry a guardrail in the same shape:**

> **narrow credential  +  validation gate  +  fail-closed check**

- The **firewall** is this — explicit allowlist + a verification step that fails the container start if it's wrong.
- The **read-only DB plan** is this — read-only role + SQL validation script + statement timeout.
- **`slc-be-aws-ops`'s `cloudwatch-logs-search`** is this — cost guards + false-negative protection.

If a proposed capability needs something broad, it isn't ready — it needs a guardrail first.

> One implication of "plugins must work host-direct too": a capability that has to run for host-only plugin users can't put its guardrail in the baked image — the guardrail must ship *inside* the plugin so it travels with the marketplace install. Baking into the image is only an option for devcontainer-only capabilities.

## The test of "done"

> **An agent can take a ticket from spec to verified-in-test-env without a human handing it broad credentials at any step.**

Hold every future decision against this. If a step requires broad creds, the work isn't done.

## Maturity ladder (the roadmap, mechanism-free)

| Stage | Bound by | Status |
|---|---|---|
| Dev (plan / code / test) | container + git | ✅ done |
| Observe — logs | scoped CloudWatch | ✅ reference impl (`cloudwatch-logs-search`) |
| Observe — data | read-only role + validation gate | 📝 spec'd, unbuilt |
| Deploy | branch-push (scoped by construction) | ⬜ not built |
| Invoke | endpoint / lambda call (scoped target + payload) | ⬜ not built |

Suggested build order (easiest + most-spec'd first): **DB access → logs polish → deploy → invoke.**

## Open questions (deliberately unresolved)

- **Delivery per capability** — baked vs. marketplace, decided when each is built (not now).
- **Where guardrail logic lives** — a shared library baked into the base image, or per-plugin? Likely varies by capability (see the host-direct implication above).
- **Deploy / invoke scoping** — is "branch-push only" + "no direct prod creds" sufficient, or do certain targets need an explicit approval gate?
