---
last_updated: 2025-04-13
corpus: handbook
audience: all
---

# Titles for QA

## How QA Titles Work

Quality work at NovaOps is about risk judgment, product understanding, and clear evidence. QA titles are not based on who finds the most bugs. They reflect the complexity of the systems you can evaluate, the independence of your test strategy, and the influence you have on how teams build reliable workflow automation software.

QA employees use Jira for test planning and defect tracking. QA engineers who need repository visibility may receive GitHub access with manager and IT approval.

The QA ladder applies to manual testing, exploratory testing, release validation, test automation, and quality leadership. A QA engineer may be embedded with one product squad, shared across several teams, or focused on release systems. The title is based on the level of judgment and impact, not on whether the person's daily work is mostly manual or mostly automated.

Workflow automation software has a particular risk profile. A small interface change can affect a customer's approval route, scheduled job, webhook, customer record update, retry behavior, or audit history. QA work therefore includes more than checking that a screen renders. Strong QA work asks whether the workflow does the right thing when data is missing, permissions are narrow, a third-party system is slow, a customer edits a rule mid-run, or a release must be rolled back.

## What Strong QA Looks Like

Strong QA work at NovaOps is visible before release week. QA should help Product and Engineering understand risk while the feature is still being shaped, not only after the implementation is complete. A good QA plan names the customer outcome, the workflow paths that matter, the assumptions being tested, the regression surface, the evidence needed for release, and the issues that would block shipping.

The strongest QA employees do all of the following at a level appropriate to their title:

- Translate acceptance criteria into concrete test coverage.
- Find gaps in Product, Engineering, or design assumptions without turning every discussion into a process fight.
- Use Jira so test plans, defects, release blockers, and fix verification are searchable.
- Use GitHub responsibly when repository visibility is required, especially for understanding code changes, test coverage, and pull request risk.
- Balance manual exploration with automated checks.
- Protect customers from defects that affect data integrity, permissions, billing, auditability, security, or critical workflow execution.
- Explain release risk clearly enough that an accountable owner can make a decision.

QA does not own product quality alone. Product owns the problem and acceptance criteria. Engineering owns implementation and technical reliability. Support and Customer Success own customer signal. QA owns independent risk evaluation, clear test evidence, and the habit of making quality visible before customers discover problems.

## Tools and Records

Jira is the primary record for QA planning and defect tracking. A QA Jira record should be understandable to someone who did not attend the meeting. For a test plan, include scope, assumptions, environments, linked product work, test data needs, regression areas, automation coverage, manual coverage, owners, and known open risks. For a defect, include steps to reproduce, actual result, expected result, build or environment, severity, customer impact, screenshots or logs when appropriate, and whether the issue blocks release.

Severity and priority are related but not identical. Severity describes the impact of the defect. Priority describes how urgently the team should act. A rare data-loss issue may be high severity even if it affects one workflow. A visual issue on a low-use settings page may be lower severity even if it is easy to fix. QA should help the team separate "annoying," "embarrassing," "blocks a customer workflow," "creates support load," "breaks audit or compliance evidence," and "risks customer data."

GitHub is used for source code, pull requests, engineering review, and automated checks. QA engineers with approved GitHub access may read pull requests, review test files, inspect CI results, and comment when a change creates test risk. GitHub access does not make a QA employee a code owner unless Engineering has explicitly granted that responsibility. QA should not request broad repository access when a narrower repository, project, or read-only role is enough. Contractor GitHub access follows the approval rules in [our internal systems](our-internal-systems.md).

Slack and Webex can help resolve ambiguity, but durable QA decisions belong in Jira, GitHub, or the NovaOps wiki. If a live discussion changes the release decision, the accountable QA owner should move the conclusion back to the relevant Jira ticket or release checklist.

## Levels

### QA1, Associate QA Analyst

QA1, Associate QA Analyst: Learns the product area, executes defined test plans, writes clear reproduction steps, and asks for help early. A QA1 is expected to become dependable in a bounded area before taking on broader release ownership.

A QA1 works from a defined plan. The plan may be written by a QA2 or QA3, or by a senior engineer with QA review. The QA1 is expected to understand what they are testing, follow the plan carefully, report uncertainty, and avoid hiding gaps. Dependability matters more than speed at this level.

Typical QA1 expectations:

- Execute smoke, regression, and feature test cases in a bounded product area.
- Verify bug fixes using the reproduction steps and acceptance criteria provided.
- Record clear results in Jira, including pass, fail, blocked, not applicable, and needs clarification.
- Write reproduction steps that another teammate can follow without private context.
- Ask for help early when setup, permissions, data, or expected behavior is unclear.
- Notice obvious customer-impact concerns and escalate them to the QA owner.
- Run existing automated checks or test scripts when instructed, and report failures accurately.

Workflow automation testing examples for QA1 include creating a simple workflow from a template, confirming that a trigger starts the workflow, checking that the expected action is executed, verifying that the run history records success or failure, and confirming that a user without the right permission cannot perform a restricted action. A QA1 may test a happy path, a simple validation error, and a basic retry scenario, but they are not expected to design the whole risk model.

Release risk judgment at QA1 is mostly escalation. A QA1 should not independently approve a risky release, but should raise concerns such as "the regression suite failed in the approvals area," "the test account cannot access the connector," "the acceptance criteria do not say what should happen when the trigger fires twice," or "this bug affects a workflow customers already use." Good QA1 judgment means saying what is known, what is unknown, and who needs to decide.

Regression strategy at QA1 is checklist discipline. A QA1 should understand which checklist belongs to the feature, execute it consistently, and avoid marking a case as passed when it was skipped or tested under different conditions. If a test case is stale, the QA1 should flag it rather than silently adapting it.

Automation expectations at QA1 are introductory. A QA1 may run automated tests, read simple failure output, gather logs, update test data, or pair with a QA2 on a small automated assertion. The level does not require owning automation design.

Jira and GitHub responsibilities at QA1 are narrow. Jira work should be complete and clear. GitHub access is not assumed. If a QA1 does receive GitHub access, they should use it for visibility into linked pull requests and CI status, not for unapproved code changes or repository administration.

Evidence that a QA1 is doing well includes clean bug reports, reliable execution of assigned test plans, early escalation of blockers, improved product understanding, and fewer repeated mistakes in the same area. Evidence for movement toward QA2 includes beginning to identify missing test cases, proposing practical additions to regression coverage, and verifying fixes with less prompting.

### QA2, QA Engineer

QA2, QA Engineer: Designs test cases for normal product work, verifies fixes, contributes to regression coverage, and spots gaps in acceptance criteria. A QA2 can own quality for a small project with support from a senior teammate.

A QA2 can turn a clear feature request into a practical test plan. The work may still need review from a senior teammate, but the QA2 should not wait passively for every test case to be handed over. QA2 is the level where the person begins to own quality for normal product work.

Typical QA2 expectations:

- Design positive, negative, permission, data validation, and regression cases for ordinary feature work.
- Review acceptance criteria before implementation is complete and ask concrete questions.
- Verify fixes and decide when a defect needs additional Engineering or Product follow-up.
- Contribute to regression suites by adding, removing, or updating cases based on actual product risk.
- Create or maintain automated tests for stable, repeated workflows when automation is the right investment.
- Use Jira to keep test scope, defect status, and release blockers visible.
- Use approved GitHub access to inspect pull requests, test changes, and CI failures when repository visibility is needed.

Workflow automation testing examples for QA2 include designing coverage for a workflow with a trigger, a condition, two branches, and an external action. The QA2 should test the normal path, each branch, missing required fields, a disabled connector, a retry after transient failure, duplicate events, permission boundaries, and the run history shown to the customer. If the feature touches customer notifications, the QA2 should confirm who receives the notification, what the message says, and whether the customer can trace the workflow result.

Release risk judgment at QA2 means naming the tradeoff, not just the defect. A QA2 should be able to say, for example, "This bug does not block release because it affects only a draft workflow and has a clear workaround," or "This bug should block release because it can execute the wrong action for an active customer workflow and the customer cannot detect the problem until later." The QA2 should seek support when the decision affects major accounts, data integrity, security, or contractual commitments.

Regression strategy at QA2 means choosing coverage based on change surface. A UI-only label change may need a targeted smoke test. A change to workflow execution, permissions, connector mapping, billing events, or audit logs needs broader regression. A QA2 should understand that adding every old test to every release slows the team without improving confidence. The goal is the right signal.

Automation expectations at QA2 are practical and selective. A QA2 may automate stable smoke paths, connector mock scenarios, validation rules, or fix regressions that have repeated. They should avoid automating a volatile design before the behavior is settled. Good QA2 automation is readable, maintainable, tied to release confidence, and not dependent on one person's laptop.

Jira responsibilities at QA2 include owning the QA portion of a small project board, linking defects to the feature or release, keeping fix verification current, and making blocked tests obvious. GitHub responsibilities may include reading the pull request description, confirming that automated tests match the changed behavior, checking CI failures before release, and commenting when a missing test or migration risk should be addressed.

Customer-impact judgment at QA2 should be specific. Instead of saying "customers will be unhappy," the QA2 should identify which customer workflow is affected, whether the issue is visible, whether there is a workaround, whether data can be repaired, and whether Support can explain the behavior safely. The QA2 may ask Support or Customer Success for context, but should not expose unnecessary customer data in Jira or Slack.

Evidence that a QA2 is doing well includes independent test plans for normal work, defects that are easy for Engineering to reproduce, useful acceptance-criteria questions, regression improvements that catch real issues, and small automation contributions that reduce repeated manual effort. Evidence for movement toward QA3 includes owning a complex feature's quality strategy, mentoring QA1s, and influencing release decisions with clear risk analysis.

### QA3, Senior QA Engineer

QA3, Senior QA Engineer: Builds test strategy for complex features, balances manual and automated coverage, mentors others, and helps Product and Engineering identify risk before implementation is complete. A QA3 is trusted to say when a release is not ready and explain why.

A QA3 owns quality strategy for complex work. This includes features with multiple services, connectors, permissions, migrations, customer-visible automation behavior, or release sequencing risk. A QA3 is expected to operate independently, but not in isolation. They bring the right people into the decision early.

Typical QA3 expectations:

- Build test strategy for complex features or releases, including scope, risks, environments, data, automation, manual exploration, regression, and release evidence.
- Challenge ambiguous requirements before implementation hardens around the wrong assumption.
- Lead risk reviews with Product, Engineering, Support, and Customer Success when customer impact is plausible.
- Balance deep exploratory testing with high-value automated coverage.
- Mentor QA1 and QA2 teammates through test design, defect analysis, and release judgment.
- Identify quality problems caused by process, architecture, test data, or unclear ownership.
- Make a release recommendation and explain the evidence behind it.

Workflow automation testing examples for QA3 include planning coverage for a new approval-routing engine, a workflow import/export feature, a connector permission redesign, or a migration of run-history storage. The QA3 should identify cross-cutting risks such as old workflows created before the release, customers editing workflows during deployment, retries that execute twice, audit logs that do not match actual execution, role-based access that leaks restricted data, and dashboards that show success while a downstream action failed.

Release risk judgment at QA3 is explicit and accountable. A QA3 may recommend "ship," "ship with known risk," "ship behind a flag," "ship to beta customers only," "delay," or "rollback." The recommendation should include the defect list, affected customer paths, confidence in regression coverage, open unknowns, support readiness, monitoring or rollback signals, and the decision owner. A QA3 is trusted to say a release is not ready, but must be able to explain the reason without drama.

Regression strategy at QA3 means designing the release-level coverage model. The QA3 should know which tests protect the core workflow engine, which protect connectors, which protect permissions, which protect customer-facing screens, and which protect migration or data repair paths. They should retire obsolete cases, isolate flaky tests, and make sure the team is not confusing test volume with test confidence.

Automation expectations at QA3 include designing reliable automation patterns and reviewing automation tradeoffs. A QA3 may write tests, but the title is not measured by lines of test code. Strong QA3 automation work includes choosing stable test boundaries, mocking external systems where appropriate, protecting end-to-end smoke paths, reducing flaky failures, and making failures actionable for Engineering.

Jira responsibilities at QA3 include owning the quality plan for a complex release, making blocker status visible, and ensuring defects have useful severity and customer-impact notes. GitHub responsibilities may include reviewing test coverage in pull requests, confirming release branches or feature flags match the QA plan, and raising concern when CI status is green but meaningful product risk is untested.

Customer-impact judgment at QA3 must connect technical details to real outcomes. A QA3 should distinguish between "workflow cannot be created," "workflow runs late," "workflow runs twice," "workflow runs with the wrong data," "workflow audit history is incomplete," and "workflow failure is hidden from the customer." These are different risks with different release decisions.

Evidence that a QA3 is doing well includes complex releases with fewer late surprises, Product and Engineering using QA risk input before build decisions are final, QA1 and QA2 teammates improving through coaching, automation that becomes a trusted release signal, and release recommendations that leaders can act on. Evidence for movement toward QA4 includes improving quality across multiple teams, not just being the strongest tester on one project.

### QA4, Staff QA Engineer

QA4, Staff QA Engineer: Defines quality practices across multiple teams, improves tooling, and leads risk reviews for major launches. A QA4 makes the whole engineering organization better at preventing defects.

A QA4 operates across teams and systems. The work is less about personally testing every important release and more about making the organization better at knowing what is safe to ship. QA4 impact should be visible in practices, tooling, release confidence, incident reduction, and the judgment of other people.

Typical QA4 expectations:

- Define quality practices used by multiple product or engineering teams.
- Lead risk reviews for major launches, migrations, and customer-impacting changes.
- Improve release tooling, test data strategy, automation architecture, and defect analytics.
- Establish standards for Jira test plans, defect severity, release checklists, and regression suites.
- Coach senior QA engineers, engineers, and product managers on risk judgment.
- Identify systemic quality gaps before they become a pattern of incidents.
- Partner with Engineering leadership on CI reliability, environment strategy, observability, and rollback readiness.

Workflow automation testing examples for QA4 include creating the company-wide strategy for testing workflow execution across connectors, permissions, schedules, retries, imports, exports, audit logs, and customer notifications. A QA4 might standardize how teams simulate third-party outages, how test data is reset, how long-running workflow runs are validated, how customer-visible run history is compared to backend execution, and how release gates treat flaky or missing automation.

Release risk judgment at QA4 includes major-launch governance. The QA4 does not replace the accountable product or engineering owner, but they make the risk visible enough that the owner cannot accidentally ignore it. For a major launch, a QA4 may require a written release confidence note covering customer segmentation, rollback path, observability, support readiness, known defects, data migration verification, feature-flag plan, and the exact conditions that would stop or reverse the release.

Regression strategy at QA4 means designing a scalable system of confidence. The QA4 should help teams know which checks belong in pull request CI, nightly automation, pre-release validation, exploratory sessions, migration dry runs, customer beta validation, and post-release monitoring. The QA4 should remove duplication that wastes time and add coverage where the company has repeatedly missed risk.

Automation expectations at QA4 include architecture and leverage. A QA4 may introduce shared fixtures, service virtualization, connector simulators, test-data factories, release dashboards, or flake triage processes. The standard is not novelty. The standard is whether the tooling helps teams make better release decisions with less wasted effort.

Jira responsibilities at QA4 include defining templates and conventions that make work searchable across teams. GitHub responsibilities may include advising on required checks, test ownership, repository access patterns, and how QA participates in pull request review without slowing normal engineering flow. A QA4 should understand the security and least-privilege expectations for GitHub access.

Customer-impact judgment at QA4 is portfolio-level. The QA4 should recognize patterns such as repeated connector failures for Customer Success accounts, defect clusters in permission changes, or release pressure that consistently pushes Support into reactive work. Their work should reduce the chance that a single team's local optimism becomes a company-wide customer problem.

Evidence that a QA4 is doing well includes fewer repeated defect classes across teams, clearer release gates, reduced flaky-test noise, faster and safer release decisions, stronger QA mentoring, and tooling or practices that keep working when the QA4 is not in the room. Evidence for movement toward QA5 requires company-wide quality ownership and durable strategic impact beyond a function or product area.

### QA5, Quality Lead or Quality Architect

QA5, Quality Lead or Quality Architect: Owns company-wide quality systems, release confidence, and long-term quality investment. This title is used sparingly and requires impact beyond a single team.

QA5 is a company-level quality role. It may be a senior individual contributor role, a functional leadership role, or a hybrid depending on company need. The title is used sparingly because it requires repeated evidence that the person improves how NovaOps ships workflow automation software across the organization.

Typical QA5 expectations:

- Own the long-term quality strategy for NovaOps product delivery.
- Define how release confidence is measured, communicated, and improved across teams.
- Set investment priorities for automation, environments, test data, tooling, risk management, and quality analytics.
- Partner with Product, Engineering, Support, Customer Success, IT, and leadership on customer-impact risk.
- Make company-wide tradeoffs when speed, quality, security, cost, and customer commitments conflict.
- Build a QA culture where quality is owned by the whole delivery system, not isolated in one function.
- Develop QA4-level leaders and create durable practices that survive team changes.

Workflow automation testing examples for QA5 include setting the quality architecture for the entire workflow platform: what must be proven before a workflow-engine change reaches customers, how connector compatibility is certified, how customer data repair is validated, how feature flags and staged rollouts are governed, how production incidents feed back into regression strategy, and how teams know whether automation is giving useful confidence or just producing activity.

Release risk judgment at QA5 is strategic. A QA5 may advise on whether to delay a major customer commitment, invest in a new test environment, change the release cadence, require a release-readiness review for high-risk areas, or accept a known defect with documented mitigation. The QA5 should be able to speak in customer, technical, operational, and business terms without exaggerating or minimizing risk.

Regression strategy at QA5 is long horizon. The QA5 should ensure NovaOps has a coherent approach to regression as the product grows: core workflow engine coverage, connector coverage, permissions and identity coverage, customer-visible reporting coverage, data migration coverage, and post-release monitoring. They should notice when teams are spending more time maintaining tests than learning from them, and when underinvestment is creating silent customer risk.

Automation expectations at QA5 include investment judgment. A QA5 should know when to fund shared automation, when to simplify a brittle suite, when to add manual exploratory capacity, and when to fix product architecture that makes testing unreliable. Automation is a business tool, not a badge.

Jira and GitHub responsibilities at QA5 are governance-level. The QA5 may define standards for release evidence, test ownership, quality dashboards, required checks, repository visibility for QA, and auditability of release decisions. They should partner with IT and Engineering so access follows least privilege while still allowing QA to do real risk analysis.

Customer-impact judgment at QA5 is company-level. The QA5 should be able to evaluate how release quality affects retention, support load, enterprise trust, implementation timelines, contractual expectations, and the credibility of the NovaOps workflow automation platform. They should help leaders make hard calls with clear evidence.

Evidence that a QA5 is doing well includes durable company-wide quality systems, measurable improvement in release confidence, fewer repeated high-impact defects, better cross-functional readiness for launches, strategic automation investment, and QA leaders who can operate independently because the system around them is stronger.

## Workflow Automation Testing Examples

The following examples show the kinds of scenarios QA should consider. Not every feature needs every test. The right set depends on customer impact, release scope, and change surface.

- Trigger behavior: A workflow starts when the correct event occurs, does not start on unrelated events, handles duplicate events safely, and records why it did or did not run.
- Conditional routing: Branches evaluate the right fields, handle missing or null values, and remain understandable in run history.
- Approval steps: Approvers receive the right task, cannot approve when they lack permission, and see a clear state when an approval is reassigned, timed out, or canceled.
- External actions: A workflow updates the intended system, handles rejected requests, retries transient failures safely, and avoids double execution.
- Permissions: Users can view, edit, run, pause, and audit workflows only according to their role.
- Scheduled workflows: Time zones, daylight-saving changes, holidays, paused schedules, and edited schedules do not create surprising execution times.
- Data mapping: Field mappings preserve data types, required fields, customer identifiers, and audit history.
- Versioning: Existing active workflows keep the right behavior when a customer edits a draft or when NovaOps releases a new workflow version.
- Import and export: Imported workflows preserve permissions, connector references, validation errors, and disabled states.
- Failure visibility: Customers and internal teams can tell when a workflow failed, what step failed, and what action is needed.
- Rollback and recovery: A failed release can be reversed or mitigated without losing workflow history or executing unsafe duplicate actions.

Good workflow automation testing often combines a narrow automated check with manual exploration. For example, an automated test may prove that a workflow with a valid trigger and action completes successfully. Manual exploration may still be needed to inspect how a customer understands the failure state, whether the audit trail is useful, or whether a confusing message will create support tickets.

## Release Risk and Customer Impact

QA should describe release risk in plain language. A useful release-risk note answers these questions:

- What customer workflow or internal workflow is affected?
- How many customers or users could be affected?
- Is the issue visible to the customer, hidden until later, or visible only to Support?
- Can the customer work around it safely?
- Can NovaOps repair the data or workflow state if the issue happens?
- Does the issue affect permissions, security, billing, audit history, customer commitments, or legal obligations?
- What evidence do we have from manual testing, automation, logs, monitoring, beta use, or fix verification?
- What is still unknown?

Not every defect blocks a release. QA should avoid treating all bugs as equal. A typo in an internal label, a confusing but harmless empty state, a rare cosmetic issue, or a known limitation with a documented workaround may be acceptable. A defect that executes the wrong customer action, hides a failed workflow, exposes restricted data, corrupts configuration, breaks an existing integration, or makes rollback unsafe should receive much stronger scrutiny.

When QA recommends shipping with a known issue, the Jira record should name the mitigation. Mitigations may include a feature flag, staged rollout, release note, Support playbook, monitoring alert, temporary customer exclusion, rollback plan, or scheduled follow-up fix. A vague promise to "watch it" is not a mitigation.

## Regression Strategy

Regression strategy should be based on product risk, not habit. The purpose of regression is to catch unintended breakage in areas customers rely on. A good regression plan is neither "test everything every time" nor "trust the happy path." It chooses the smallest set of checks that gives meaningful confidence for the change.

Common regression layers at NovaOps:

- Pull request checks for unit, integration, and focused automated coverage.
- Feature-level QA for acceptance criteria, edge cases, permissions, and failure handling.
- Core workflow smoke tests for creating, running, pausing, editing, and auditing workflows.
- Connector and integration checks for systems touched by the change.
- Permission and identity checks for role-sensitive areas.
- Migration or backfill validation when existing customer data may change.
- Exploratory testing for new UX, ambiguous customer behavior, and unusual workflow combinations.
- Post-release monitoring and Support readiness for high-risk launches.

QA should keep regression suites healthy. A test that always fails and is ignored teaches the team to ignore tests. A test that covers behavior nobody supports anymore creates noise. A test that catches a repeated customer-impact defect is valuable even if it is not glamorous. When QA removes or changes a regression case, the Jira or GitHub record should explain why.

## Promotion Evidence

Promotion evidence may include better release outcomes, stronger test design, automation that reduced repeated work, clearer defect analysis, or coaching that improved another team's quality practice. See [making a career](making-a-career.md) for the promotion process.

Good QA promotion evidence is specific and tied to level expectations. A strong packet should show what changed because of the employee's work. Useful evidence may include:

- A test strategy that caught release-blocking workflow risk before launch.
- A Jira defect pattern analysis that led Engineering to fix a root cause.
- Automation that reduced repeated manual checks while improving release confidence.
- Regression improvements that caught a recurring defect class.
- A release-risk recommendation that prevented customer impact or enabled a safe staged release.
- Coaching that helped QA1 or QA2 teammates write clearer defects or better test plans.
- A GitHub review comment that identified a missing test or unsafe migration path before merge.
- A Support or Customer Success partnership that turned customer incidents into useful regression coverage.
- A cross-team quality practice that continued working after the employee moved to different work.

Promotion packets should include examples from recent work, the level being claimed, the scope of the impact, and the evidence that the impact lasted. For QA3 and above, the packet should show influence beyond personal execution. For QA4 and QA5, the packet should show system-level improvement, not only individual excellence.

## Non-Evidence

The following are not strong promotion evidence by themselves:

- Finding many low-impact bugs without improving release confidence.
- Working late during every release when the underlying process never improves.
- Being the only person who understands a brittle test suite.
- Closing a large number of easy Jira tickets without customer or quality impact.
- Running the same regression checklist faster without noticing stale or missing coverage.
- Writing automation that is flaky, unmaintained, or disconnected from release decisions.
- Saying "QA approved" without a record of what was tested and what risk remains.
- Having GitHub access or creating many comments without useful risk analysis.
- Being well liked, responsive in Slack, or present in many meetings.
- Owning a crisis that better planning would likely have prevented.

Slack praise, launch appreciation, and positive anecdotes can support a packet, but they cannot replace evidence. The packet should make clear what the employee did, why it mattered, how the result was verified, and what changed for customers or teammates.

## Realistic Edge Cases

Late defect before release: If QA finds a defect shortly before release, the right response is not automatic panic or automatic approval. QA should document the defect, affected paths, severity, workaround, fix risk, rollback implications, and recommended decision. A QA3 or above should lead the release-risk discussion when the impact is complex.

Ambiguous acceptance criteria: If Product says "the workflow should notify the right owner," QA should ask how the owner is determined, what happens when there is no owner, whether reassignment changes the recipient, and whether historical runs change. Ambiguity discovered during test execution should become a Jira comment or acceptance-criteria update.

Flaky automation: A flaky test is a quality problem, not just a nuisance. QA should identify whether the failure comes from product instability, test data, timing assumptions, environment drift, or the test itself. Re-running until green is not evidence. A flaky test can be quarantined temporarily, but the owner and follow-up must be recorded.

No GitHub access: A QA employee can still do strong QA work without GitHub access if the role does not require repository visibility. If repository context is needed, the manager and IT should approve the right level of access. QA should not ask Engineering teammates to paste sensitive code or secrets into Slack as a workaround.

Customer-specific workaround: A workaround is acceptable only when it is safe, documented, and supportable. A workaround that requires hidden admin action, customer data edits, or an unusual sequence only one engineer understands is not a strong release mitigation.

Data-sensitive testing: QA should use approved test data whenever possible. If a customer-specific issue requires customer context, use the minimum necessary information, keep it in approved systems, and avoid copying sensitive details into broad Slack channels or unrelated Jira fields.

Contractor participation: Contractors may contribute to QA or Engineering work, but access must match the approved scope and end date. A contractor in Jira does not automatically receive GitHub access. QA leads should plan test ownership so a contractor's departure does not leave release evidence or automation knowledge stranded.

Feature flags and staged rollout: A feature flag can reduce risk, but it does not remove the need to test. QA should confirm default state, enabled state, disabled state, customer targeting, rollback behavior, and what happens to workflows created while the flag was enabled.

Existing customer workflows: New behavior must be tested against both newly created workflows and existing workflows where compatibility matters. A release that works only for new workflows may still break customers who built automations months earlier.

Release pressure: "The customer needs it tomorrow" is context, not proof that the release is safe. QA should respond with options: what can be safely released, what must be fixed, what can be staged, what Support needs to know, and what risk leadership is accepting.
