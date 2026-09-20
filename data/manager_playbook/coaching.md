---
last_updated: 2025-05-10
corpus: manager_playbook
audience: manager
---

# Coaching

## What Coaching Is

Coaching is helping an employee improve judgment and capability while they still own the work. It is different from taking over, giving vague encouragement, or waiting until a formal review. Good coaching is specific, timely, and connected to the role expectations.

At NovaOps, coaching is normal for everyone. A high performer may need coaching on broader influence. A new employee may need coaching on product context. An employee at risk may need coaching as part of a correction plan. The tone changes, but the habit of clarity stays the same.

Coaching is active management. It turns a real work moment into practice, reflection, and a next attempt. It should leave the employee with more ownership, not less. The manager's job is to clarify the standard, make the gap visible, provide support, and inspect progress. The employee's job is to engage, practice, surface blockers, and carry the work forward.

Coaching belongs in everyday work. Use it in 1:1s, after customer calls, during project planning, after GitHub review, after Salesforce account review, after SupportDesk escalation review, during onboarding, after a missed handoff, or when someone is ready for broader scope. Do not save coaching for February or August performance reviews. Formal reviews should summarize what the employee has already heard.

Coaching is not a secret performance file. If the topic is ordinary development, keep shared action notes where they help the employee. If the topic may become formal performance management, involve People Operations and move the relevant documentation into the approved process. See [performance management](performance-management-model.md), [giving feedback](giving-feedback.md), and [underperformance and terminations](underperformance-and-terminations.md).

## A Simple Coaching Loop

Start with the work, not the personality. Describe the situation, the behavior or decision, and the effect. Then ask for the employee's view. You may learn that the problem is unclear priority, missing access, a dependency, or a skill gap.

Agree on the next practice step. A practice step should be observable: draft the customer update before sending it, write the test plan before implementation starts, prepare the next Salesforce renewal review with a senior teammate, or lead the next Jira planning discussion. Set a follow-up date.

After the follow-up, name what changed. If the employee improved, say exactly what improved. If the issue remains, make the gap explicit and decide whether the next step is more coaching, clearer expectations, or formal performance management.

A useful loop has five parts:

- Observe the work: use evidence from Jira, GitHub, Salesforce, SupportDesk, BambooHR workflow notes, customer notes, project plans, Webex conversations, or agreed deliverables.
- Name the gap or growth edge: connect the example to role expectations, customer impact, quality, reliability, collaboration, or judgment.
- Ask for the employee's view: listen for missing context, unclear decision rights, access blockers, workload conflict, skill gaps, or disagreement about the standard.
- Choose the practice: pick a small next action that can be attempted soon and reviewed fairly.
- Follow up: inspect the next attempt, say what changed, and decide the next step.

Managers should usually coach close to the work. If a renewal call went poorly on Tuesday, review it that week. If a GitHub pull request missed rollback planning, discuss it before the next similar pull request. If an HR workflow created confusion for a new hire, review the next BambooHR task before it is marked complete. The point is not speed for its own sake; the point is that memory, evidence, and practice are still fresh.

Use one coaching theme at a time when possible. An employee may have several growth areas, but a coaching conversation that covers every flaw becomes noise. Choose the theme that most affects the role now. If the same employee has missed Salesforce notes, unclear customer follow-up, and weak escalation judgment, the first coaching plan may focus on renewal-risk ownership rather than all possible communication issues.

## Diagnosing the Gap

Before choosing the coaching step, diagnose what kind of gap you are seeing. Different gaps need different support.

A skill gap means the employee does not yet know how to do the work. They may need a template, training, pairing, examples, review, or more repetitions. A new Sales Development Representative may not know how to qualify an account in Salesforce. A Backend Engineer may not know NovaOps' expected test-plan format. An HR Coordinator may not know which BambooHR fields are sensitive. A skill gap is usually coachable through instruction and practice.

A judgment gap means the employee can complete tasks but is making weak tradeoffs. They may overcommit to a customer, skip escalation, accept unclear requirements, approve access too casually, or miss the downstream effect of their decision. Judgment gaps need more reflection: what options did you consider, what risk did you discount, who needed context, and what would have changed your decision?

A context gap means the employee is missing background that others assume is obvious. This often happens with new hires, employees who moved roles, contractors, remote employees outside the main time zone, or employees returning from leave. Context gaps should be fixed by the manager and team, not treated as low effort.

An expectation gap means the standard was not clear. If the manager never explained what good looks like, the next step is not blame. Write the expectation, show examples, and agree how future work will be judged.

An access or tool blocker means the employee cannot reasonably do the work because a system, permission, device, data source, or vendor license is missing. Coaching should surface the blocker and assign ownership for removing it. Do not frame missing Webex, Salesforce, GitHub, Jira, BambooHR, SupportDesk, AWS, Datadog, Okta, or device access as a performance problem unless the employee failed to request, use, or protect access after clear direction.

A motivation or ownership gap means the employee has the access and skill but is not reliably owning agreed outcomes. Coach directly, document the pattern, and move toward formal performance management if the gap is serious or repeated.

## Skill Gaps Versus Judgment Gaps

Managers often blur skill and judgment. Separating them makes coaching fairer and faster.

For skill gaps, teach the method. Give examples and practice. Say, "For the next two customer updates, draft the note first. Include the customer ask, the owner, the date, the risk, and the next action. I will review the first one before it goes out." This works when the employee needs a repeatable pattern.

For judgment gaps, inspect the decision process. Say, "Before you commit a date to the customer, pause and name the dependency, the confidence level, and who has to agree. Bring me the next two risky commitments before you send them, and be ready to explain the tradeoff." This works when the employee knows the mechanics but is choosing poorly under ambiguity.

For mixed gaps, use both. A Customer Success Specialist may need a Salesforce renewal checklist and better escalation judgment. A Systems Administrator may know Okta technically but need coaching on when admin access requires extra review. A Sales Operations Specialist may know the export workflow but need stronger judgment about customer data handling. Keep the coaching plan explicit so the employee knows whether they are practicing execution, decision-making, or both.

Do not use "judgment" as a vague label. Name the decision and effect. "Your judgment is weak" is not useful. "You gave the customer a timeline before Engineering confirmed the Jira dependency, which made the renewal risk look lower than it was" gives the employee something to work on.

## Access and Tool Blockers

NovaOps work often depends on systems. Coaching should reveal whether the employee can actually do the job with the access they have.

If an employee says they are blocked, ask for specifics:

- Which system is missing or failing?
- What exact work cannot be completed without it?
- Who owns the request: the employee, manager, IT, People Operations, Finance, or another approver?
- Is there safe alternate work while the blocker is resolved?
- When will you check again?

For access, route the work correctly. IT owns Okta, MFA, laptop, device management, privileged access, Webex administration, Slack administration, GitHub organization administration, AWS access, and security review. People Operations owns BambooHR employment workflows, leave, accommodations, and sensitive HR records. Finance owns spend thresholds and recurring vendor cost review. Managers approve business need, but they do not bypass risk, cost, or employment-process review.

Examples:

- If a Sales or Customer Success employee cannot update Salesforce because access is pending, the manager should confirm the business need and route the access request. The employee can shadow calls, draft account notes, and learn customer context while the request is open.
- If an engineer cannot merge a GitHub pull request because contractor access is pending, the manager should work with IT and keep the work limited to approved Jira planning, architecture review, or pairing until access is safe.
- If an IT employee lacks admin rights for a high-risk task, the manager should not coach them to work around Okta or AWS controls. The coaching point may be how to explain the approval path and set expectations with the requester.
- If an HR employee cannot complete a BambooHR workflow because the profile or field permission is wrong, the manager should fix the workflow with People Operations before judging completion speed.

Document blockers as blockers. "Salesforce pending IT approval until Friday" is different from "employee missed renewal note." "Webex license unavailable" is different from "employee failed to attend customer call." When the blocker clears, reset the expectation and follow up on actual performance.

## Coaching Plans

A coaching plan is a lightweight written agreement for development. It is not automatically a correction plan. Use a coaching plan when the growth area matters enough to track over several weeks but is still appropriate for normal management.

A coaching plan should include:

- The growth area or gap.
- The role expectation it connects to.
- Two or three concrete examples.
- The practice steps.
- The support offered.
- The evidence you will review.
- The follow-up cadence.
- The date you will decide whether the plan is working.

Keep the plan short enough that the employee can use it. A two-page coaching plan that no one reads is less useful than six clear bullets. Store shared notes in the normal team or 1:1 workflow when the topic is development. Do not keep sensitive medical, leave, or protected details in manager notes. If the coaching plan may become formal performance management, ask People Operations where the documentation should live.

Example coaching plan language:

"For the next four weeks, the growth area is renewal-risk ownership. The expectation is that every red or yellow account has a current Salesforce note, a named owner, and a next customer action. You will prepare the Thursday renewal review with Yael, draft the account notes before the meeting, and send me the three highest-risk accounts by Wednesday noon. I will review the first two drafts and then spot-check the next two. We will review progress in Friday 1:1s."

Another example:

"For the next three Jira tickets, the growth area is implementation planning. Before coding starts, write the acceptance criteria, test plan, migration or rollout risk, and rollback plan in the ticket or linked pull request. Pair with a senior teammate on the first ticket. We will review whether the pull request is easier to review and whether follow-up bugs decrease."

Coaching plans should not promise promotion, compensation, role change, or permanent schedule changes. They can support growth toward those topics, but formal decisions follow the relevant process.

## Department Examples

Coaching should sound different by role while still following the same loop.

Engineering coaching often uses Jira, GitHub, Datadog, AWS, incident notes, and architecture decisions. Coach on writing acceptance criteria before implementation, adding test and rollback plans to pull requests, asking for design review before touching a risky service, reducing review churn, and escalating production risk early. A strong Engineering coaching step is observable: "For the next two backend changes, include the migration plan, test evidence, rollback plan, and known risk before requesting review."

Sales coaching often uses Salesforce, ZoomInfo, Webex call notes, pipeline hygiene, and forecast commitments. Coach on qualification, discovery, next-step clarity, discount discipline, and not promising terms or timelines without approval. A useful Sales practice step is: "Before the next pipeline review, update Salesforce for each late-stage opportunity with decision criteria, economic buyer, next meeting date, risk, and forecast category."

Customer Success coaching often uses Salesforce, SupportDesk, Webex, customer health notes, escalation records, and renewal plans. Coach on customer follow-up, renewal-risk ownership, expectation setting, escalation timing, and closing the loop after support issues. A good CS practice step is: "Draft the customer recap within one business day after each Webex call, including owner, date, risk, and next action, and ask a senior teammate to review the first two."

Operations coaching at NovaOps may sit in Sales Operations, Finance, HR operations, IT operations, or cross-functional workflows. Coach on handoffs, recurring checklists, data quality, vendor or spend process, and making hidden operational work visible. A Sales Operations example is: "For the next Salesforce import, write the source, fields changed, validation check, and rollback owner before running the import." A Finance or business-operations example is: "Before approving a recurring tool request, identify whether the monthly or annual spend threshold requires Finance review."

HR coaching often uses BambooHR, Deel, SecureSign, onboarding checklists, employment records, and People Operations workflows. Coach on confidentiality, precise employee records, contractor paperwork, new-hire coordination, and knowing when a manager question belongs with People Operations. A practical HR coaching step is: "For the next three onboarding workflows, confirm legal name, preferred name, location, employment type, start date, manager, department, and required systems before marking the BambooHR task complete."

IT coaching often uses Okta, MFA, Webex Admin, Slack Admin, GitHub administration, AWS, Datadog, SupportDesk, and laptop fleet records. Coach on ticket triage, risk-based access review, clear requester communication, and not over-granting permissions to move faster. A useful IT practice step is: "For the next five access tickets, write the business need, system, requested permission level, risk review, approver, and expiration date before granting access."

For all departments, coach the employee on the actual work artifact. Do not only say "communicate better." Review the Salesforce note, the Jira ticket, the GitHub pull request, the BambooHR task, the SupportDesk response, the Webex recap, the access request, or the written plan.

## Coaching in Remote and Hybrid Work

NovaOps is hybrid and remote-first across Israel, Germany, the United Kingdom, the United States, and occasional contractor locations. Remote coaching requires more deliberate context because managers cannot rely on hallway signals.

Use Webex for coaching conversations that need nuance, especially when the topic involves performance, conflict, customer impact, role expectations, or a sensitive misunderstanding. Slack is fine for scheduling, quick acknowledgments, and simple follow-up, but difficult coaching should not happen only in a chat thread.

Write the decision or practice step after the conversation. Remote employees should not have to infer the manager's meaning from tone or memory. A short written follow-up might say: "We agreed that for the next two renewal calls, you will draft the customer recap before sending it, include owner/date/risk/next action, and bring it to Friday's 1:1 for review." This protects both clarity and fairness.

Be thoughtful about time zones. Do not always place the inconvenience on the employee in another country. Rotate early and late meetings when needed. If coaching requires quick review of work, agree on a review window that works in the employee's local day.

Remote coaching should include visible context. Link the Jira ticket, GitHub pull request, Salesforce record, SupportDesk case, BambooHR task, or wiki page that anchors the discussion. Avoid vague messages like "let's talk about your communication" with no example. A remote employee receiving that message may spend hours guessing what is wrong.

Remote does not mean low-touch. A new employee, an employee in a new role, an L1-L2 report, a contractor with narrow scope, or an employee returning from leave may need weekly 30-60 minute 1:1s and more frequent coaching until the work is stable. See [1:1s](1-1s.md) and [onboarding](onboarding.md).

## Coaching High Performers

High performers still need coaching. The topic may be leverage rather than remediation.

Coach high performers on scaling their judgment through others, writing clearer decision records, mentoring without taking over, influencing outside their home function, making risk visible earlier, and choosing which work not to do. A high-performing engineer may need coaching on reviewing pull requests in a way that develops the author. A high-performing Account Executive may need coaching on forecast discipline and cross-functional handoff. A high-performing HR or IT teammate may need coaching on documenting repeatable processes instead of being the only person who knows how something works.

Do not let strong output excuse harmful patterns. If a high performer creates confusion, interrupts teammates, bypasses process, or burns out the team, coach the behavior directly. Strong results do not remove the responsibility to collaborate well.

High-performer coaching can connect to recognition, expanded scope, or promotion readiness, but coaching is not a promise. If the employee asks whether a coaching plan guarantees promotion, say no. Promotion follows the promotion process, calibration, and Finance review. Coaching can help build the evidence.

## Coaching New Employees and Role Changes

New employees and employees who change roles need coaching on language, systems, and judgment that long-tenured employees may take for granted. During the first few months, use coaching to make implicit standards explicit.

A new Customer Success Manager may need to learn how Salesforce account notes, SupportDesk cases, Webex customer calls, renewal risk, and escalation paths fit together. A new engineer may need to learn how Jira planning, GitHub review, test evidence, Datadog signals, and production boundaries fit together. A Product employee moving from Customer Success may need coaching on how customer anecdotes become product evidence rather than immediate commitments.

For role changes, reset expectations. Do not assume prior success transfers automatically. A person who was excellent in Customer Success may still be Growing in Product. A strong individual contributor may be new to manager judgment. A contractor may be expert technically but need coaching on NovaOps security, access, and documentation norms.

Use coaching to check whether onboarding worked. If the employee is missing basic context, fix the onboarding gap. If the employee had clear onboarding and still misses agreed standards, coach the specific behavior and document follow-up.

## When Coaching Becomes Formal Performance Management

Coaching becomes formal performance management when the gap is serious, repeated, or could affect continued employment if not corrected. Managers should involve People Operations early, before telling the employee that their job is in jeopardy and before using phrases like formal warning, correction plan, performance plan, final warning, or at risk in a formal sense.

Move toward formal performance management when:

- The same gap continues after clear coaching and follow-up.
- The employee cannot meet core role expectations without the manager rewriting or redoing the work.
- The work creates repeated customer harm, operational risk, security risk, payroll or HR-process risk, production risk, or material missed commitments.
- The employee does not engage with the coaching plan.
- The manager believes continued employment may be at risk.
- The issue may involve misconduct, harassment, discrimination, fraud, security violation, protected leave, accommodation, or another sensitive process.

Before moving formal, check the basics. Was the expectation written? Did the employee have required access? Were priorities stable enough to judge the work? Did the manager provide timely feedback? Was the employee newly onboarded, returning from leave, or moved into a different role? Is the problem individual performance, or did the team create an impossible workflow?

If formal performance management is appropriate, People Operations helps design the correction plan. A correction plan should include the gap, expected standard, measurable benchmarks, support offered, timeline, check-in cadence, and consequences if the gap is not corrected. Most plans run 30 to 60 days, but People Operations confirms the right timeline for the situation.

Do not soften a serious message by calling it "just coaching" if the job may be in jeopardy. That creates surprise later. Also do not escalate every normal learning gap into a threat. Use People Operations to distinguish coaching, expectation clarification, correction planning, and possible termination.

## Documentation and Evidence

Coaching documentation should be factual, brief, and useful. Good notes capture the work example, expected standard, employee context, agreed practice, support offered, and follow-up date.

Strong evidence includes recent work artifacts: Jira tickets, GitHub pull requests, incident notes, Salesforce updates, customer communications, SupportDesk cases, BambooHR workflow status, access requests, project plans, and written follow-ups. Weak evidence includes personality labels, vague complaints, hearsay, surprise feedback, or frustration that the employee works differently from the manager.

Use full names and role context when confusion is possible. NovaOps has duplicate first names. Do not write "Daniel missed the access step" if the context could refer to Daniel Levi in Engineering or Daniel Cohen in Sales Operations. Use the full name, role, system, and work example.

Keep sensitive content in the right place. Do not store medical details, protected leave details, harassment allegations, immigration information, payroll details, or personal family information in a private coaching note. Route those matters to People Operations or the appropriate owner.

If you send a written follow-up to the employee, keep it direct and usable:

"In today's 1:1 we reviewed the delayed Jira handoff for the billing API work. The expectation is that dependencies are named before sprint commitment. For the next two planning meetings, you will bring a dependency list and risk rating before the team estimates. I will review the first list by Wednesday."

That note is better than "Please be more proactive."

## Coaching Without Creating Dependence

Do not turn coaching into constant pre-approval. The goal is better independent judgment. Ask questions that reveal thinking: what options did you consider, what risk worries you most, what customer impact matters, what would make this reversible, and where do you need a decision from me.

Managers should avoid becoming the hidden owner of every deliverable. If the employee must send every customer email, pull request, access ticket, or HR workflow to the manager forever, the coaching is not building capability. Use temporary review only when it has a clear purpose and end point.

Good coaching questions include:

- What outcome are you trying to protect?
- What are the realistic options?
- What evidence do you have?
- What is the risk if you are wrong?
- Who else needs to know before this moves?
- Which part is reversible?
- What would make you escalate?
- What does done look like?
- Which system should hold the source of truth?

Set decision rights explicitly. Say when the employee can act independently, when they should inform you, and when they need approval. For example: "You can update routine Salesforce notes independently. Inform me about red renewal risks. Get approval before offering a non-standard commercial commitment." Or: "You can merge low-risk internal fixes after review and tests pass. Escalate migrations, permission changes, customer-visible changes, or anything with rollback risk."

For repeated performance gaps, move to [underperformance and terminations](underperformance-and-terminations.md) early. Coaching is not a substitute for a clear correction plan when the job may be in jeopardy.

## What Good Follow-Up Sounds Like

Follow-up closes the loop. Without it, coaching becomes advice. Good follow-up names the evidence and the next decision.

If the employee improved, be specific: "The last two renewal notes were stronger. Each had the customer ask, owner, risk, and next action. The next step is to do that without draft review for the next three accounts."

If the employee partially improved, name both sides: "The Jira tickets now include clearer acceptance criteria, but the test plan is still missing before implementation starts. For the next sprint, the test plan must be written before coding begins."

If the issue remains, be direct: "We agreed that customer recaps would go out within one business day. Three of the last four were late and two had no owner. This is now a repeated gap. I am going to talk with People Operations about the right next step."

If the original diagnosis was wrong, say so. "We treated this as a skill gap, but the last two examples show the template is understood and the issue is follow-through. We need to address ownership directly." Or: "I thought this was a performance issue, but Webex access and missing customer context were real blockers. I am fixing those before judging the next attempt."

## Retrieval Facts

Coaching at NovaOps means helping an employee improve judgment and capability while they still own the work.

Good coaching is specific, timely, connected to role expectations, and based on real work evidence.

The NovaOps coaching loop is: observe the work, name the gap or growth edge, ask for the employee's view, choose an observable practice step, and follow up.

Managers should check for unclear priorities, missing access, dependencies, context gaps, skill gaps, judgment gaps, and ownership gaps before deciding the coaching step.

Skill gaps usually need instruction, templates, pairing, examples, and practice.

Judgment gaps usually need decision review, tradeoff discussion, risk framing, and clearer escalation rules.

Access and tool blockers should be documented as blockers, not treated as performance gaps until the employee has the required access and clear expectations.

Engineering coaching may use Jira, GitHub, Datadog, AWS, pull requests, incident notes, test plans, rollback plans, and architecture decisions.

Sales coaching may use Salesforce, ZoomInfo, Webex call notes, pipeline hygiene, forecast commitments, qualification, and next-step clarity.

Customer Success coaching may use Salesforce, SupportDesk, Webex, customer health notes, escalation records, and renewal plans.

Operations coaching may use Salesforce imports, vendor review, spend thresholds, recurring checklists, cross-functional handoffs, data quality, and workflow evidence.

HR coaching may use BambooHR, Deel, SecureSign, onboarding checklists, employment records, contractor paperwork, and People Operations workflows.

IT coaching may use Okta, MFA, Webex Admin, Slack Admin, GitHub administration, AWS, Datadog, SupportDesk, access tickets, and laptop fleet records.

Remote coaching should usually use Webex for nuance, written follow-up for clarity, and fair scheduling across time zones.

Coaching becomes formal performance management when the gap is serious, repeated, could affect continued employment, or creates customer, operational, security, HR, payroll, production, or policy risk.

People Operations should be involved before a manager tells an employee that their job is in jeopardy or uses formal warning, correction plan, performance plan, final warning, or similar process language.

A coaching plan is a lightweight development agreement; a correction plan is a formal performance-management step reviewed by People Operations.
