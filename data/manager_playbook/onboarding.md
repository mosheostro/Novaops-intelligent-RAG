---
last_updated: 2026-01-28
corpus: manager_playbook
audience: manager
---

# Onboarding

## Manager Ownership

People Operations and IT create the rails, but the manager owns the employee's onboarding experience. A new hire should know why the role exists, what success looks like, whom to meet, which systems matter, and what useful work they can start with.

Before the start date, prepare a 30-day plan, request access, choose a buddy, schedule the first week, and confirm the laptop shipment. Use Okta, Slack, Webex, Jira, GitHub, Salesforce, BambooHR, or AWS only as the role requires. Do not request broad access just in case.

Manager ownership starts when the offer is accepted, not when the employee appears in Slack. People Operations owns the BambooHR profile, employment packet, and compliance tasks. IT owns laptop shipment, Okta, MFA, device management, and baseline system provisioning. The manager owns role clarity, first-week calendar, buddy assignment, first outcomes, and the list of people the new hire should meet.

For a preboarding employee such as Maya Cohen, the Customer Success manager should confirm Salesforce, Webex, Slack, BambooHR self-service, SupportDesk viewer, and the customer-shadowing plan before the start date. For Ben Walker in Sales, the manager should confirm Salesforce, Webex, Slack, and prospecting-system access, but should not request unnecessary Engineering tools. For contractors such as Priya Raman or Alex Kim, scope and end date matter: GitHub access must be limited, approved by IT, and tied to the statement of work.

Do not treat onboarding as a checklist race. Marking a task complete in BambooHR or an internal onboarding plan should mean the employee can actually use the system or complete the step. If Webex is blocked by a license issue, say it is blocked. If GitHub is pending IT approval, say it is pending. False green checkmarks create confusion and make the employee feel like they are the problem.

## Preboarding Checklist

At least 10 business days before the start date, the manager should complete a preboarding review with People Operations and IT. Confirm the legal name, preferred name, work email, location, employment type, start date, manager, department, and required systems. Because NovaOps has duplicate first names, use full names and email addresses in access requests.

The manager should prepare:

- A first-week calendar with Webex links.
- A buddy or point person who is not the manager.
- A 30-day outcome plan.
- A list of required systems and why each is needed.
- A small first contribution that is safe and real.
- A written explanation of team rituals, decision records, and where work lives.

If the new hire is remote, confirm the shipping address and equipment bundle early. If the hire is outside the modeled core locations, involve People Operations before assuming standard payroll, benefits, or equipment timing.

## First Week

The first week should combine company context, team context, system setup, and one small real contribution. Avoid eight hours a day of reading. A Customer Success hire might shadow a Webex customer call and update a Salesforce note. An engineer might review a small GitHub pull request and pick up a low-risk Jira ticket.

Hold at least two manager check-ins in the first week. Ask what is confusing, what access is missing, and which names or acronyms need explanation.

Day one should include a manager welcome, Okta and MFA confirmation, Slack and Webex setup, BambooHR self-service check, team intro, and a clear explanation of the week. Do not let the new employee spend the entire first day discovering missing access. If access is delayed, tell them what is delayed, who owns it, and what they can do meanwhile.

By the end of week one, the employee should know the manager's expectations for communication, how priorities are set, where decisions are written, and how to ask for help. They should also know which tools are authoritative: Jira for planned product work, GitHub for code review, Salesforce for customer account work, BambooHR for HR workflows, and Slack for short-lived coordination.

Role examples help. A Backend Engineer can review service architecture, pair on a small bug, and learn deployment boundaries before owning production changes. A Product Designer can review the design system, sit in on customer workflow review, and learn how Figma decisions become Jira work. A Customer Success Manager can shadow renewal calls, read customer health notes, and practice a Salesforce account update. An IT Support Specialist can triage a low-risk ticket with Lina Novak before touching Okta admin tasks.

## First 30, 60, and 90 Days

By day 30, the employee should understand the team, tools, and first outcomes. By day 60, they should own normal work with support. By day 90, you should be able to discuss performance against the role expectations and adjust the growth plan.

Document milestones in a shared onboarding plan. If the employee is struggling, address it early with coaching rather than waiting for day 90.

A good 30-day plan names learning goals and work outcomes. For example, "understand the Customer Success renewal workflow" is a learning goal; "own two low-risk renewal notes in Salesforce with review" is a work outcome. For Engineering, "learn the service boundaries" is a learning goal; "merge one small GitHub pull request with tests and a rollback note" is a work outcome.

At day 30, ask: does the employee know where work lives, who approves what, what customer or internal outcome matters, and which systems still block them? At day 60, ask: can the employee own normal work with support, make basic tradeoffs, and ask for help with enough context? At day 90, ask: is the employee meeting the expectations for the role and level, and what should the next growth focus be?

If onboarding is going poorly, separate causes. Missing access is different from weak judgment. Unclear scope is different from low effort. A manager who failed to provide context should fix the context before framing the issue as performance. If the employee is still below expectations after clear support and feedback, use [coaching](coaching.md) and, if needed, [performance management](performance-management-model.md).

## Manager 1:1 Cadence During Onboarding

New employees should have a 30-60 minute 1:1 every week for the first few months. This is not optional just because the employee seems independent. New hires are learning language, norms, hidden dependencies, and the difference between what NovaOps says is important and what actually gets attention.

Use early 1:1s to ask what is confusing, which system is hard to use, which person they are unsure how to approach, and what work feels under-explained. Use later 1:1s to discuss judgment, feedback, customer impact, and title expectations. Once the employee is well onboarded and performing, cadence can drop to about once a month if both people agree.

## Access and Tooling During Onboarding

Managers should request only the access needed for the role. New employees often assume more access means more trust, but at NovaOps it usually means more risk. A Customer Success Manager does not need GitHub by default. An engineer does not need Salesforce export permissions by default. A contractor does not need broad Slack channels or GitHub organization membership by default.

If a system is delayed, give the employee useful work that does not require that system. If Webex is blocked by license availability, the employee can read customer notes and join Slack discussions while IT resolves it. If GitHub is pending, an engineer can review architecture docs and Jira tickets. If Salesforce is pending, a Sales or CS employee can shadow calls and learn account terminology.

## Returning From Leave

For a report returning from parental, family, or medical leave, start planning at least two weeks before the return date if the employee is comfortable engaging. Ask about schedule constraints, knowledge gaps, and preferred ramp. Do not ask for medical details.

Create a re-entry plan for the first 30 and 60 days. Keep the first two weeks lighter where possible: fewer new projects, more context refresh, and clear backup coverage. A returning employee should not be penalized for needing to rebuild context after approved leave.

Return-from-leave onboarding is not the same as new-hire onboarding, but it deserves the same care. The employee already knows NovaOps, yet the company may have changed while they were away: new Jira priorities, Salesforce account changes, GitHub repository changes, customer escalations, team reorganizations, new policies, or new managers. Summarize what changed before assigning urgent work.

Ask the employee how they want to receive context. Some people want a written digest first; others prefer a Webex walkthrough. Do not force the employee to tell a personal story about the leave. Keep the conversation about work re-entry, schedule constraints, coverage, and what support would help.

For parental leave returns, plan for practical needs such as schedule predictability, reduced meeting load at first, and backup coverage for customer calls or incidents. For medical leave returns, coordinate with People Operations before discussing accommodations. For any protected leave, do not treat the ramp as a performance problem.

## Onboarding Anti-Patterns

Avoid these common failures:

- A beautiful onboarding checklist with no real work.
- Broad access requests "just in case."
- A first week made entirely of recorded videos.
- No manager 1:1 until week three.
- A buddy who does not know they are the buddy.
- Asking the new employee to discover all missing access themselves.
- Treating contractor onboarding as informal because the engagement is temporary.
- Waiting until day 90 to mention concerns that were visible in week two.

The best onboarding feels structured but not sterile. It gives the employee enough context to move, enough work to feel useful, and enough manager contact to surface confusion before it hardens.
