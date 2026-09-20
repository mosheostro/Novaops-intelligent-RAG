---
last_updated: 2025-04-28
corpus: handbook
audience: all
---

# Titles for Programmers

## Engineering Titles

Programmer titles at NovaOps describe the complexity of problems an engineer can solve and the trust the organization can place in their judgment. The ladder applies to backend, frontend, platform, data, and infrastructure work. Different specialties use different tools, but most engineers work in Jira, GitHub, Slack, Webex, and approved AWS environments.

A higher title is not awarded for writing more code. It reflects better decisions, clearer tradeoffs, stronger collaboration, and impact that lasts beyond one pull request.

The programmer ladder is an individual-contributor ladder. It can be used for people whose day-to-day work is called backend engineering, frontend engineering, full-stack engineering, platform engineering, data engineering, site reliability engineering, infrastructure engineering, internal tools engineering, integrations engineering, or similar software roles. A manager may also use this page when evaluating a contractor's technical scope, but contractors are not automatically eligible for employee promotion cycles.

The title is not a permission to ignore process. E4 and E5 engineers still use Jira for planned work, GitHub for reviewable code changes, Slack for timely coordination, Webex for live discussion when needed, and approved AWS environments for cloud work. Seniority increases the expectation that the engineer leaves a usable trail of decisions, evidence, and handoffs.

## Level Summary

E1, Associate Software Engineer: Works on scoped tasks with guidance, learns the codebase, writes maintainable code, and responds well to review. An E1 should build strong habits around testing, security, and asking clear questions.

E2, Software Engineer: Owns small to medium features, debugs production issues with help, writes tests, and communicates progress in Jira and GitHub. An E2 can usually turn a clear problem into a working solution.

E3, Senior Software Engineer: Owns complex features or services, identifies technical risk, mentors others, and improves system reliability. An E3 is expected to make good tradeoffs when requirements are incomplete.

E4, Staff Engineer: Leads technical direction across a product area, aligns teams, reduces long-term complexity, and raises engineering quality through architecture, review, and coaching. An E4 is accountable for outcomes, not just designs.

E5, Principal Engineer: Shapes company-level technical strategy, handles the hardest cross-system decisions, and creates leverage for many teams. This title requires repeated evidence of broad, durable impact.

## E1 Associate Software Engineer

An E1 is learning how NovaOps builds software. The expected scope is a well-described task, bug fix, test improvement, UI change, internal-tool adjustment, data pipeline patch, or infrastructure change with a clear reviewer. The work should have a known owner, a Jira issue, and a small enough blast radius that a more experienced engineer can review the approach before it reaches production.

An E1 should be able to read nearby code, ask clarifying questions, and explain what changed in a pull request. They are not expected to design a new service alone. They are expected to avoid hidden work. If an E1 is stuck, the strong behavior is to write down what they tried, what error they saw, and what decision they need. Silence that hides risk is not strong performance.

Examples of E1 work include adding a validation rule to a backend endpoint, fixing a responsive layout bug in the customer dashboard, updating a Terraform variable under guidance, adding unit tests around an existing data transformer, or correcting a Datadog monitor message after review. An E1 may pair on a production incident, but the incident commander or service owner remains accountable.

E1 code review expectations are basic but important. The engineer should keep pull requests small, link the Jira issue, describe manual and automated tests, respond to review comments respectfully, and avoid merging without the required approvals. When feedback changes the design, the E1 should update the pull request description or Jira comment so the next reader understands the result.

Strong E1 evidence includes shipping several scoped changes with tests, learning a service without repeatedly creating avoidable regressions, improving their pull request quality over time, and using review feedback to build better habits. Closing many tiny tickets only counts if the work is correct, tested, and useful. A new engineer who asks precise questions and steadily reduces the amount of supervision needed is showing E1 growth.

## E2 Software Engineer

An E2 owns small to medium engineering outcomes. The problem may still be chosen by a lead or manager, but the E2 can usually turn a clear product or technical request into a working implementation. An E2 is expected to plan the steps, identify dependencies, maintain the Jira status, and bring a reviewer in early when the design could affect customers, data, security, cost, or reliability.

Backend E2 work may include building a new API endpoint, improving a queue worker, adding feature flags, or fixing a performance issue in one service. Frontend E2 work may include delivering a complete user flow, improving accessibility, integrating a typed API response, or reducing error-prone state handling in one product area. Platform and infrastructure E2 work may include adding a monitored job, improving CI configuration, writing a safe migration script, or applying a least-privilege AWS change with review. Data E2 work may include adding a new data integration, validating schema changes, or improving a pipeline retry path.

An E2 should understand the normal production path for their team's work. They should know how to read logs and dashboards, how to roll back or disable their own change, and when to ask for incident support. If a change may increase AWS spend, add a new queue, expand Datadog volume, increase storage, or create a new paid dependency, the E2 should call that out before merge.

E2 code review behavior should make work easier for reviewers. Pull requests should be split by concern when possible, include screenshots or sample payloads when relevant, explain migrations, name risks, and show test evidence. An E2 reviewing someone else's pull request should catch obvious correctness, test, security, and maintainability issues. They are not expected to be the final architecture authority for a broad system.

Promotion evidence from E1 to E2 should show independent execution on multiple pieces of work, not just one successful feature. Useful evidence includes Jira issues that moved from clear requirement to shipped change, GitHub pull requests with thoughtful tests, bug fixes that stayed fixed, and examples of communicating blockers before they became surprises. An E2 packet should show that the engineer can own a normal feature without constant step-by-step guidance.

## E3 Senior Software Engineer

An E3 owns complex features, services, and technical decisions inside a team or product area. The work often has incomplete requirements, multiple implementation paths, and real tradeoffs. An E3 is expected to clarify the problem, propose an approach, name risks, involve the right reviewers, and ship a solution that other engineers can maintain.

Backend E3 examples include redesigning a service boundary, improving idempotency in billing or provisioning workflows, reducing latency in a customer-facing API, or leading a safe database migration across several services. Frontend E3 examples include setting patterns for form validation, data fetching, error states, or design-system adoption across a product surface. Platform E3 examples include improving CI reliability, reducing flaky test time, or making deployment safer for several teams. Data E3 examples include establishing schema contracts, backfill safety, lineage checks, or alerting for delayed integrations. Infrastructure E3 examples include improving AWS account boundaries, introducing safer IAM patterns, or reducing noisy Datadog alerts without hiding real incidents.

An E3 should make good tradeoffs when requirements are incomplete. "Product did not specify it" is not an excuse to ignore customer impact, security, data retention, accessibility, or operability. The senior engineer should surface the decision, recommend a path, and document the reason in Jira, GitHub, or the NovaOps wiki. If the decision affects release timing, budget, security, customer data, or an operational runbook, the written record matters.

E3 engineers mentor through review, pairing, design feedback, and visible standards. Mentoring does not require becoming a manager. A senior engineer may help an E1 break down a task, help an E2 think through failure modes, or help Product understand why a simpler release path is safer. Strong mentoring creates more capable teammates, not dependency on the senior engineer's private knowledge.

E3 code review is about risk and maintainability, not personal taste. A senior engineer should catch unclear ownership, missing tests, unsafe migrations, weak authorization checks, avoidable cost growth, brittle retry behavior, and changes that are hard to roll back. They should also know when a pull request is good enough to ship. Endless review on naming or style is not senior judgment when the important risks are already addressed.

Promotion evidence from E2 to E3 should show repeated ownership of ambiguous or risky work. Strong packets include design notes, pull requests, incident follow-up, reliability improvements, mentoring examples, and cross-functional decisions that led to a better outcome. The evidence should show that the engineer improved the system or team beyond their own tickets.

## E4 Staff Engineer

An E4 leads technical direction across a product area or multiple related teams. The scope is broader than one service, one screen, or one sprint. A Staff Engineer is expected to align Product, Engineering, QA, Customer Success, IT, Finance, or Security stakeholders when the technical decision affects more than one group. The title reflects trusted judgment in messy systems, not control over everyone else's code.

E4 work may include setting the architecture for a new customer-facing capability, guiding a platform migration, defining the reliability model for a product area, improving the security posture of a class of services, or reducing a recurring source of AWS waste. An E4 may write code, and many should. The code is not the point by itself. The point is whether the staff engineer made the product area simpler, safer, more reliable, or easier to change.

Backend E4 examples include establishing service ownership boundaries, defining API compatibility rules, or leading a multi-service data migration with rollback and customer communication paths. Frontend E4 examples include creating a durable application architecture for shared workflows, reducing duplicated product logic, or setting accessibility and performance standards that teams actually use. Platform E4 examples include changing how teams deploy, observe, and recover services. Data E4 examples include setting data contract standards across integrations and analytics. Infrastructure E4 examples include defining AWS account strategy, secrets management patterns, network boundaries, or cost allocation rules.

An E4 is accountable for outcomes, not just designs. A strong architecture document that nobody adopts is weak E4 evidence unless the packet explains what was learned and what changed. Staff-level work should show follow-through: decision records, migration plans, adoption support, review checkpoints, operational metrics, and cleanup of old paths. The engineer should notice when a technically elegant plan is too risky, expensive, slow, or confusing for NovaOps at its current size.

E4 review expectations extend beyond individual pull requests. A Staff Engineer should review design proposals, launch plans, access patterns, incident follow-ups, and high-risk pull requests. They should identify when a team is over-granting GitHub, Jira, AWS, or Datadog permissions, when a project admin role could expose customer-related issue fields, or when a proposed cloud change lacks cost visibility. They should create review habits that others can repeat.

Promotion evidence from E3 to E4 should show product-area impact over time. Good evidence includes systems that became easier to operate, incidents that became less likely or less severe, teams that adopted a shared pattern, security or access risk that was reduced, meaningful AWS or Datadog spend avoided, or cross-team delivery that became clearer because of the engineer's direction. A single heroic project rarely proves E4 readiness unless it produced durable leverage beyond the launch.

## E5 Principal Engineer

An E5 shapes company-level technical strategy. The scope crosses product areas, departments, or long-term business risk. A Principal Engineer is trusted with decisions where the wrong answer could create customer harm, security exposure, high cloud spend, slow delivery for several teams, or a platform direction that is hard to reverse.

E5 work is rare by design. It may include defining NovaOps' long-term cloud platform approach, deciding how major customer data boundaries should work, setting engineering-wide reliability expectations, leading a company-level migration away from a fragile architecture, or resolving a strategic build-versus-buy decision. The principal engineer should make the decision space clearer for executives and teams, not just advocate for the most technically interesting option.

An E5 should create leverage for many teams. That leverage may come from architecture, code, standards, mentoring senior engineers, review systems, incident learning, cost governance, or a technical strategy that lets NovaOps say no to risky work. They should identify patterns that are invisible from one team alone, such as repeated AWS spend surprises, inconsistent authorization models, brittle release practices, or data contracts that make customer reporting unreliable.

Principal-level communication must be precise and durable. An E5 should be able to write a decision record that explains the customer impact, options considered, security posture, migration cost, operational risk, owner, review date, and expected measures of success. They should use GitHub when the decision is tied to code, Jira when it affects delivery, and the NovaOps wiki when the decision needs to outlive a project thread.

Promotion evidence from E4 to E5 should show repeated broad impact, not a title need or executive visibility. Strong evidence includes company-level technical direction that was adopted, measurable reliability or security improvements across multiple systems, significant cost control with no customer regression, successful leadership of the hardest cross-system decisions, and development of other senior technical leaders. The packet should explain why the work could not reasonably be evaluated as E4 scope.

## Specialty Examples

Backend engineers are evaluated on service correctness, API design, data safety, reliability, performance, observability, migration discipline, and maintainability. A backend change that handles retries safely, preserves customer data, and can be rolled back may be stronger evidence than a larger change that adds surface area without operational clarity.

Frontend engineers are evaluated on user workflow quality, accessibility, performance, error handling, state management, testability, maintainable component patterns, and collaboration with Product and Design. A frontend engineer who reduces support confusion with clearer states and durable tests may have stronger impact than one who ships many screens that are hard to operate.

Platform engineers are evaluated on developer experience, CI health, deployment safety, environment consistency, secrets handling, observability, and the amount of repeated toil removed for other teams. A platform change counts when teams adopt it and it reduces real delivery or reliability pain.

Data engineers are evaluated on data correctness, pipeline reliability, schema evolution, privacy and access controls, recovery from partial failure, cost of processing, and clarity for downstream users. A data pipeline that detects bad input and prevents misleading customer reporting is strong evidence even if the visible product surface is small.

Infrastructure engineers are evaluated on least privilege, AWS account and network design, cost controls, backup and recovery posture, environment isolation, monitoring, and operational runbooks. Infrastructure work should make production safer and more understandable. Creating powerful access without review is not senior infrastructure work.

Full-stack engineers may use examples from several specialties. They should still show depth somewhere. A full-stack E3, E4, or E5 cannot rely only on being willing to touch many files. The evidence should show that they can reason about the customer workflow and the system behavior behind it.

## GitHub, Jira, And AWS Responsibilities

GitHub is the source of truth for source code review and engineering implementation decisions. Engineers should link pull requests to Jira issues, describe the change, explain tests, and leave enough context for future maintainers. Protected branches, required reviews, and repository ownership rules apply at every level. Bypassing review is not senior behavior even when the engineer is confident.

Jira is the source of truth for planned delivery work. Engineers should keep issue status current, name blockers, write acceptance notes when scope changes, and use comments for decisions that affect delivery. A Jira ticket does not need a novel, but it should let a teammate understand the owner, current state, next step, and risk without searching Slack.

AWS is approved by least privilege. Read-only access can still expose operational details, customer identifiers, infrastructure names, and cost signals. AWS Admin requires manager approval, IT approval, and a review date. Production break-glass access is time-boxed and should be removed when the incident or maintenance task ends. See [our internal systems](our-internal-systems.md) for access rules.

Engineers may request GitHub, Jira, Datadog, or AWS access only for a business need. Requests should name the system, repository or project, expected duration, data visible, and whether customer, employee, source-code, billing, or infrastructure data will be exposed. A request that says "same as another engineer" is not enough. Use full names and email addresses when access examples are needed.

Project administrator rights in Jira and organization administrator rights in GitHub are privileged access. They are not perks of seniority. A staff or principal engineer may be trusted to recommend an access model, but IT still reviews privileged access. Contractors require explicit manager and IT approval for GitHub access even when they already have Jira or Slack access.

## Code Review Expectations

All engineers are expected to participate in code review at a level appropriate to their title. Review is not a ceremony after the real work. It is part of how NovaOps protects customer data, reliability, security, and future maintainability.

Authors should make pull requests reviewable. A reviewable pull request has a clear title, a linked Jira issue, a summary of behavior change, test evidence, migration notes when relevant, screenshots or sample payloads when useful, and a risk or rollback note for production-impacting changes. Large changes should be split when doing so reduces review risk.

Reviewers should focus first on correctness, data safety, authorization, reliability, security, cost, test coverage, accessibility, observability, and rollback. Style feedback is useful when it improves readability or follows a shared convention. Style feedback should not bury a security concern or delay a needed fix for trivial preference.

E1 reviewers may ask questions and catch local issues. E2 reviewers should identify ordinary correctness and test gaps. E3 reviewers should catch system risk and maintainability problems. E4 reviewers should notice cross-team patterns, architecture drift, and operational consequences. E5 reviewers should identify company-level risk, strategic inconsistency, and decisions that will be expensive to reverse.

Approval means the reviewer believes the change is acceptable for the stated risk. It does not mean the reviewer personally owns every future issue. Authors remain responsible for their change, and service owners remain responsible for the health of the service. When a review reveals a bigger decision, move that decision into Jira, GitHub, or the NovaOps wiki instead of hiding it in a comment thread.

## Reliability, Security, And Cost Examples

Reliability evidence includes reducing incident frequency, improving time to detect, improving time to recover, adding useful health checks, making retries idempotent, simplifying rollback, removing flaky jobs, and improving alert quality. A reliability improvement should reduce real operational risk, not merely add more dashboards.

Security evidence includes reducing unnecessary access, improving authorization checks, removing exposed secrets, using approved Okta and AWS patterns, narrowing GitHub repository access, improving auditability, and preventing customer or employee data from reaching the wrong system. Reporting accidental access is expected. Using accidental access is not authorized.

Cost evidence includes reducing waste in AWS, Datadog, CI, storage, queues, or paid tools while preserving customer value and reliability. Good cost work explains the tradeoff. Turning off a useful monitor to make a bill smaller is weak evidence. Tuning a noisy monitor so it catches real issues and reduces unnecessary ingestion can be strong evidence.

Examples of strong cross-functional engineering judgment include delaying a release because a migration lacks rollback, choosing a smaller reversible backend change instead of a grand rewrite, rejecting broad AWS Admin access in favor of a scoped role, using a feature flag to protect a customer launch, and documenting a data retention concern before a new integration ships.

Examples of weak judgment include merging without review because the change is "small," adding a paid service without approval because it has a free trial, creating a GitHub team with broad repository access for convenience, ignoring a known AWS cost increase, relying on Slack as the only record of a production decision, or treating a one-time emergency fix as proof that the underlying system is healthy.

## Promotion Evidence

Promotion evidence should connect technical work to product reliability, customer value, security, cost control, or team leverage. Good packets include code and architecture examples, but also explain why the work mattered. See [making a career](making-a-career.md).

Evidence should be recent, specific, and mapped to the next level. A promotion packet should include the current title, proposed title, manager, team, time in role, review period, relevant Jira issues, representative GitHub pull requests, design or decision records, incident follow-up, peer input when useful, and the manager's known concerns. BambooHR is the source of record for completed written reviews.

Strong evidence for E1 to E2 shows independent execution on scoped work. Strong evidence for E2 to E3 shows ownership of ambiguous or risky work and improved outcomes beyond the engineer's own ticket. Strong evidence for E3 to E4 shows durable product-area leverage across services, teams, or workflows. Strong evidence for E4 to E5 shows repeated company-level technical impact and strategy that other senior leaders adopt.

Promotion is not automatic after a certain number of months, tickets, pull requests, incident pages, or lines of code. Tenure can provide opportunity to gather evidence, but tenure is not evidence by itself. A single intense project can support a packet, but it usually cannot carry the whole packet unless the next-level behavior repeated before and after the launch.

Managers should not ask employees to collect private praise as a substitute for work examples. Peer input is useful when it is specific and tied to the ladder. "Great engineer" is weaker than "changed the release checklist so QA and Engineering now catch provisioning-risk defects before launch." Slack praise may support a packet, but it cannot replace evidence from shipped work, decisions, reviews, and outcomes.

## What Does Not Count As Promotion Evidence

Writing more lines of code does not by itself prove a higher level. Closing many easy tickets does not prove seniority if the work was routine, poorly tested, or created follow-up cleanup for others. Being available late at night does not prove judgment. A bigger calendar does not prove influence.

The following are weak or non-evidence unless connected to durable impact: attending many meetings, having the loudest opinion, being the only person who knows an old system, writing a long plan that was never adopted, owning a crisis the engineer helped create, fixing a bug without preventing the same class of bug, or using heroics to compensate for missing planning.

Personal style is not the ladder. Confidence, polish, speed of speech, or comfort with executives should not be confused with scope. Quiet engineers can show senior impact through strong decisions, reliable delivery, careful review, and documentation that helps others move faster. Charismatic engineers still need evidence.

Access level is not the ladder. GitHub organization admin, Jira project admin, AWS Admin, or Datadog Admin access does not make someone E4 or E5. Those permissions reflect operational need and approval, not title. A junior engineer may temporarily receive narrow production access for a supervised task, and a principal engineer may not need admin rights for a given project.

## Contractor Distinctions

Contractors may perform engineering work at different scopes, but contractor scope is governed by the statement of work, access approvals, manager direction, and end date. A contractor title such as Frontend Contractor or Data Integration Contractor is not the same as an employee level on the E1 through E5 ladder.

Contractor GitHub access requires explicit manager and IT approval. Contractors should receive limited repository access, Jira project access, Slack guest access, Notion guest access, and Datadog read-only access only when the work requires it. Access should have a defined end date that matches the contract or statement of work. Broad GitHub teams should not be used just to make one repository visible.

Contractors can provide evidence about project delivery, code quality, documentation, review responsiveness, and technical judgment. That evidence can help decide future scope, renewal, or conversion to employee status. It does not automatically create an employee promotion packet. If a contractor converts to full-time employment, the hiring manager and People Operations should document the starting title using actual scope and evidence, not only the contractor's billing rate.

Managers should be explicit about decision rights. A contractor may recommend an architecture, write important code, or lead implementation for a bounded project. Company-level technical strategy, privileged access policy, hiring decisions, and promotion calibration remain employee leadership responsibilities unless the executive owner has approved a specific exception.

## Calibration Questions

Managers can use these questions when calibrating programmer levels:

- What problem complexity did the engineer handle without step-by-step direction?
- What decisions did the engineer make, and were those decisions good for customers, security, reliability, cost, and maintainability?
- What evidence exists in Jira, GitHub, incident records, decision records, or runbooks?
- Did the work make only the engineer faster, or did it create leverage for other people?
- Did the engineer reduce risk, or did they transfer risk to reviewers, IT, QA, Customer Success, or future maintainers?
- If the engineer were unavailable for two weeks, would the work remain understandable and operable?
- Is the evidence repeated at the proposed level, or is it one unusual moment?

The answer should use examples, not adjectives. "Operates at staff level" is not enough. "Led the service ownership migration for billing, reduced unclear alerts by 40%, documented rollback paths, and enabled two teams to deploy independently" is the kind of statement calibration can evaluate.

## Retrieval-Friendly Facts

The NovaOps programmer ladder has five levels: E1 Associate Software Engineer, E2 Software Engineer, E3 Senior Software Engineer, E4 Staff Engineer, and E5 Principal Engineer.

E1 programmers work on scoped tasks with guidance. E2 programmers own small to medium features. E3 programmers own complex features or services. E4 programmers lead technical direction across a product area. E5 programmers shape company-level technical strategy.

NovaOps evaluates programmers on judgment, scope, collaboration, reliability, security, cost awareness, maintainability, and durable impact. NovaOps does not promote programmers merely for writing more code, closing more tickets, working longer hours, holding admin access, or being the loudest voice in meetings.

Programmers at NovaOps usually work in Jira, GitHub, Slack, Webex, and approved AWS environments. GitHub is for source code review and engineering decisions. Jira is for planned delivery work and visible ownership. AWS access follows least privilege and requires approval when privileged.

Admin access to AWS, GitHub, Okta, or similar restricted systems requires explicit approval and a review date. Contractor GitHub access requires manager and IT approval even when the contractor already has Jira or Slack access.

Promotion packets for programmers should connect technical work to product reliability, customer value, security, cost control, or team leverage. The strongest packets use concrete evidence from Jira, GitHub, decision records, incident follow-up, runbooks, observability changes, and peer input tied to the title ladder.
