---
last_updated: 2024-09-30
corpus: manager_playbook
audience: manager
---

# Giving Feedback

## Feedback Is Part of the Work

Feedback at NovaOps should be timely, specific, and useful. It is not saved up for performance reviews. It is not a manager's private verdict. It is information that helps someone repeat effective behavior or change behavior that is hurting the work.

Give feedback close to the event when possible. Waiting too long makes details fuzzy and can make a small issue feel like a secret case file. If emotions are high, wait until you can be clear and fair, but do not avoid the conversation.

Managers are expected to give feedback as part of ordinary operating rhythm: in 1:1s, after customer calls, after Jira planning, after GitHub reviews, after Salesforce renewal reviews, after Webex meetings, and after team incidents. Feedback should not arrive only in February or August performance reviews. A formal review should summarize feedback the employee has already heard, not reveal a surprise.

Feedback is different from coaching, recognition, and formal performance management, although the topics overlap. Feedback names a behavior and its impact. Coaching helps the employee practice a better approach. Recognition makes strong work visible and repeatable. Formal performance management creates a documented plan when a serious gap may put the job at risk. A manager may move between these modes, but should know which mode they are using. See [coaching](coaching.md), [recognition](recognition.md), and [performance management](performance-management-model.md).

The manager owns clarity. If a report has to guess whether a Slack comment was praise, a warning, or a passing preference, the manager has not been clear enough. Say the work behavior, the impact, and what should happen next.

## Feedback Principles

Use feedback to improve work, not to win an argument. Good feedback helps the employee answer four questions:

- What specific situation are we discussing?
- What behavior, decision, or work product did I observe?
- What impact did it have on a customer, teammate, project, risk, timeline, or quality bar?
- What should be repeated, changed, or tried next?

Keep feedback connected to role expectations. For Engineering, useful evidence may include Jira delivery, GitHub pull requests, review quality, incident notes, test plans, production risk, or cross-team handoffs. For Sales and Customer Success, useful evidence may include Salesforce account notes, renewal risk summaries, Webex customer calls, SupportDesk escalations, customer follow-up, and forecast hygiene. For Product and Design, useful evidence may include Jira clarity, customer context, tradeoff decisions, Figma or Miro collaboration, and stakeholder alignment. For IT, HR, and Finance, useful evidence may include ticket follow-through, access approval accuracy, sensitive record handling, spend controls, and documentation quality.

Feedback should be fair and current. Do not collect small frustrations for months and deliver them as one heavy message. If the behavior matters, address it. If it does not matter, do not save it for ammunition.

Feedback should also be proportionate. A small wording issue in a Slack update does not need the same weight as a repeated failure to update Salesforce before renewal calls. A first-time missed Jira detail for a new employee may need coaching. A repeated security-sensitive access mistake may need People Operations and IT involvement.

## Make It Concrete

Start with the situation, the behavior or choice, and the effect. For example: in yesterday's renewal call, you answered the customer's security question before Omar finished explaining the risk, and the customer left with conflicting answers. That is more useful than saying someone needs to communicate better.

Then ask for the employee's view. Feedback is not a cross-examination; it is a working conversation. You may discover missing context, unclear ownership, a training gap, or a disagreement worth resolving.

End with what should happen next. Good next steps are observable: send a recap, pair with a senior teammate, use a review checklist, draft a plan before a customer call, or pause before committing to a date.

Concrete feedback uses facts the employee can recognize. "You are careless" is not concrete. "The GitHub pull request merged without the rollback note we agreed on, and the on-call engineer had to reconstruct the plan during the incident review" is concrete. "You are not customer-oriented" is not concrete. "The Salesforce renewal note did not include the customer's security concern or the next Webex date, so Rachel Green could not prepare the follow-up" is concrete.

If you cannot describe the behavior without a personality label, keep preparing. The problem may still be real, but the feedback is not ready.

## Feedback Models

NovaOps does not require one script for every manager. The following models are approved patterns because they keep feedback specific and action-oriented.

### Situation, Behavior, Impact, Next Step

Use Situation, Behavior, Impact, Next Step for most feedback. This model is useful because it separates the event from the person.

Situation: "In Monday's Webex renewal call with the customer."

Behavior: "You committed to a Friday answer before Engineering had reviewed the Jira dependency."

Impact: "The customer now expects a date we may not be able to meet, and Customer Success has to reset expectations."

Next step: "Before the next customer commitment, write the dependency and owner in Salesforce, then confirm with Engineering in Jira."

This model works for positive feedback too. "In the GitHub review for the billing API change, you asked for a rollback plan before approval. That prevented a risky deploy and gave the on-call team a usable runbook. Keep making the operational risk explicit in reviews."

### Ask, Tell, Ask

Use Ask, Tell, Ask when the employee may have context you do not have. Ask for their view, tell them the feedback, then ask what next step they will take.

Ask: "How do you think the Webex customer escalation went?"

Tell: "I saw strong empathy, and I also saw the action owner stay unclear. The customer left without knowing whether SupportDesk or Customer Success would respond first."

Ask: "What should we change in the next escalation so the owner is named before the call ends?"

This model is especially useful for remote teams because managers may see only the artifact, not the whole sequence of events. It prevents the manager from assuming intent when the issue may be unclear priority, missing access, or a hidden dependency.

### Start, Stop, Continue

Use Start, Stop, Continue when feedback covers a pattern rather than one event. It works well in 1:1s, quarterly development conversations, and team retrospectives.

Start: "Start adding the customer risk level to Salesforce before renewal review."

Stop: "Stop using Slack as the only place to record renewal commitments."

Continue: "Continue sending concise Webex recaps the same day."

This model should still include examples. Do not say "stop being reactive." Say "stop waiting until the renewal meeting to surface a missing security answer when the question appeared in Salesforce two days earlier."

### Feedforward

Use feedforward when the past issue is clear and the main value is practicing the next version of the work. Feedforward sounds like: "For the next Jira planning session, bring the acceptance criteria, dependency owner, and test plan before we estimate." It does not erase the past. It makes the future standard observable.

Feedforward is useful for new hires, employees taking on stretch scope, and employees returning to a skill after a gap. It is not a substitute for formal performance management when the gap is repeated, serious, or job-threatening.

## Positive Feedback

Positive feedback should be just as specific as corrective feedback. Name the behavior and the impact: the Jira breakdown helped Engineering estimate the work, the Salesforce note saved the renewal team from re-asking the customer, or the GitHub review caught a reliability issue before release.

Public praise is welcome when the employee is comfortable with it. Private praise can matter even more, especially for quiet operational work.

Specific positive feedback helps people repeat the work. "Great job" is kind but incomplete. "Your Jira ticket split the migration into schema, backfill, and rollback tasks, which let Engineering estimate each risk separately" tells the employee what to keep doing. "Thanks for the Salesforce update" is pleasant. "Your Salesforce note captured the customer's procurement blocker, security concern, and next Webex date, which kept Sales and Customer Success aligned" is useful.

Positive feedback should include work that is often invisible. Praise the person who prevented a customer escalation, cleaned up an unclear SupportDesk handoff, caught a risky GitHub permission, improved a runbook, clarified a Jira dependency, or documented a Webex decision. If managers praise only dramatic rescues, employees will learn that quiet prevention does not count.

Use Slack for public praise when the work is appropriate to share and the employee is comfortable being named publicly. Keep customer-sensitive, employee-sensitive, security-sensitive, or compensation-related details out of public channels. A safe Slack recognition note might say: "Lina resolved the Webex license blocker before the onboarding call and documented the fix for the team." A poor public note would include private employee access details, customer confidential terms, or a medical reason for urgency.

Private positive feedback belongs in 1:1s, direct Slack messages, Webex follow-ups, or written notes. Some employees dislike public attention. Others do work where confidentiality prevents public celebration. The manager should adapt the channel without making the work disappear.

Positive feedback is also part of development. Tell high performers what was strong enough to expand. For example: "The way you handled the Jira tradeoff with Product showed senior-level judgment. Next time, I want you to lead that dependency conversation without me in the room."

## Corrective Feedback

Corrective feedback should be direct, respectful, and early. Direct does not mean harsh. Respectful does not mean vague. The employee should leave knowing what happened, why it matters, and what needs to change.

Use corrective feedback when a behavior, decision, or work product is below the needed standard but the situation is still appropriate for ordinary management. Examples include an incomplete Jira ticket, a confusing customer recap, a missed Salesforce update, a GitHub review that skips agreed risk checks, a Slack thread that creates confusion, or a Webex meeting where next steps are not assigned.

Corrective feedback should not sound like a final verdict unless a final decision has actually been made. Do not imply that a job is in jeopardy unless People Operations has reviewed the situation and the manager is prepared to explain the formal process. Do not soften a serious issue so much that the employee cannot tell it is serious.

A useful corrective feedback structure is:

- State the purpose: "I want to talk about the renewal handoff from yesterday."
- Name the facts: "The Salesforce note did not include the discount request, security question, or next Webex owner."
- Explain impact: "Sales and Customer Success prepared different answers, and the customer received conflicting follow-up."
- Ask for context: "What happened from your view?"
- Set the next step: "For the next two renewals, update Salesforce before the internal handoff and tag the account owner in Slack only after the CRM note is complete."
- Confirm follow-up: "We will review the next renewal note in our 1:1 on Tuesday."

If the employee disagrees, listen for facts. They may show that the manager missed an update, the expectation was unclear, the employee lacked access, or another owner changed the plan. If the employee gives useful new information, revise the feedback. If the new information does not change the impact, acknowledge it and keep the expectation clear.

## Examples by System and Team

The best examples name the system of record, the work behavior, and the consequence. Managers should adapt these examples to the actual role and evidence.

Jira example for Engineering or Product: "In the payments migration epic, the Jira acceptance criteria did not identify the billing API dependency or the rollback condition. That caused Engineering to estimate the work as smaller than it was. For the next planning session, include dependencies, acceptance criteria, test owner, and rollback notes before the ticket is estimated."

GitHub example for Engineering: "In the GitHub pull request for the customer import change, you approved the code before the migration test plan was added. The deploy was delayed when the release owner found the gap. In the next two reviews, do not approve until the test plan, rollback plan, and risk note are present."

Salesforce example for Sales or Customer Success: "The Salesforce account note after the Webex call listed the renewal amount but not the procurement blocker or the customer's security question. That meant the next owner had to re-ask the customer. Going forward, renewal notes should include decision maker, risk, next step, owner, and date."

Webex example for customer calls: "On the Webex call, you summarized the customer's concern clearly and paused before answering the security question. That helped Omar provide the right technical risk language and kept the customer from receiving conflicting answers. Keep using that pause when a specialist owns the answer."

Slack example for cross-functional coordination: "The Slack thread asked Engineering for an answer by end of day, but it did not link the Jira ticket or name the customer deadline. People responded to different versions of the problem. Next time, post the Jira link, customer deadline, decision needed, and owner in the first message."

SupportDesk example for Customer Success and IT: "The SupportDesk escalation was reassigned twice without a customer-facing update. The customer had no clear owner for 24 hours. The next escalation should have one internal owner, one customer update, and a timestamped handoff."

BambooHR or People Operations example for managers: "Do not put sensitive medical or protected-leave details in a private feedback note. If the employee raises leave, accommodation, harassment, discrimination, or medical information, route the details to People Operations and keep manager notes limited to work coverage and next steps."

## Remote and Hybrid Delivery

NovaOps is hybrid and remote-first, with employees in Israel, Germany, the United Kingdom, the United States, and contractors in other locations. Remote feedback needs more intentional channel choice because tone and timing are easier to misread.

Use Webex or an in-person conversation for feedback that is sensitive, corrective, emotional, connected to trust, connected to performance risk, or likely to require discussion. Slack is appropriate for quick praise, small clarifications, lightweight follow-up, and written recaps. Slack is not the right primary channel for serious corrective feedback, formal warnings, compensation disappointment, leave questions, conflict, or anything that could affect continued employment.

Do not drop hard feedback at the end of the employee's local day unless timing truly requires it. If a manager in the United States needs to give corrective feedback to a report in Israel, schedule a reasonable overlap whenever possible. If the topic is urgent, explain the urgency and still make time for conversation.

For remote delivery, be explicit about the meeting purpose without creating unnecessary alarm. A useful invite title is "Renewal handoff feedback" or "Jira planning follow-up." A mysterious invite with no context can create anxiety. Do not use a vague title to disguise a formal performance or termination conversation; those processes require People Operations guidance.

Video is helpful for nuance, but do not force video as a test of seriousness. Some employees process feedback better by listening, taking notes, and responding after a pause. The standard is clarity and respect, not camera compliance.

After a Webex feedback conversation, send a short written recap when the topic includes a specific commitment, repeated gap, cross-team dependency, customer risk, or follow-up date. The recap should be factual: what was discussed, what expectation applies, what next step was agreed, and when you will check in.

## Documentation

Not every piece of feedback needs a formal file. Everyday feedback may live in the work system where the work happens: a Jira comment, a GitHub review, a Salesforce note, a SupportDesk handoff, a Slack recap, or a shared 1:1 action note. The goal is to make the work clear, not to create a hidden case file.

Document feedback when any of the following are true:

- The issue is repeated.
- The issue affects customer trust, security, privacy, finance, legal risk, or production reliability.
- The feedback creates a measurable follow-up commitment.
- The employee disagrees with material facts and the disagreement needs review.
- The topic may become part of performance management.
- People Operations, IT, Finance, or Legal needs to be involved.

Good documentation is factual, short, and tied to evidence. Write: "On 2026-06-18, the Salesforce renewal note for Acme did not include the security question or next owner. We agreed that future renewal notes will include risk, owner, and date before the internal handoff." Do not write: "This shows poor judgment and low ownership." If the pattern later matters, the facts will be more useful than the manager's frustration.

Use the right system of record. Jira is for work planning and delivery. GitHub is for code review and source-control discussion. Salesforce is for customer and revenue account context. SupportDesk is for support and IT tickets. Slack is for coordination and lightweight written follow-up. BambooHR or the People Operations workflow is for formal performance documentation, reviews, employee relations, and sensitive HR records.

Do not keep private shadow files that contain sensitive employee details. Manager notes should be minimal and factual. Medical details, protected leave details, accommodation details, harassment or discrimination reports, payroll issues, immigration concerns, and termination planning belong with People Operations, not in a personal document.

## When to Involve People Operations

Involve People Operations early when feedback touches employment risk, fairness, protected topics, or formal process. Early involvement does not mean the employee is automatically in trouble. It means the manager is using the right process.

Contact People Operations before telling an employee their job is at risk, before using phrases like formal warning, correction plan, performance plan, final warning, or job in jeopardy, and before implying consequences that could affect employment. People Operations should review any correction plan before delivery.

Involve People Operations immediately if feedback intersects with harassment, discrimination, retaliation, protected leave, medical information, accommodations, pay, promotion disputes, termination, immigration, threats, safety, or serious misconduct. If the issue also involves access, security, confidential data, GitHub permissions, Salesforce exports, AWS, Okta, or customer data, involve IT or Legal as directed by People Operations.

Involve People Operations when the manager is unsure whether the issue is performance, conduct, leave, role clarity, manager conflict, or a process failure. For example, missed Salesforce updates after clear coaching may be a performance issue. Missed updates because the employee never had Salesforce access may be an access and onboarding failure. Repeated late customer follow-up after the employee disclosed a medical restriction may require People Operations guidance before the manager evaluates the work.

Sara Ben-David owns People Operations policy. Sara Cohen supports HR operations. Maya Rosen coordinates HR workflows in the United States. Managers may ask People Operations for help drafting fair examples, reviewing documentation, and deciding whether the next step is coaching, clearer expectations, a correction plan, or another process.

## Avoid Personality Labels

Feedback should describe work behavior, not diagnose character. Avoid labels such as careless, lazy, defensive, negative, emotional, not strategic, bad attitude, low ownership, difficult, abrasive, immature, or not a culture fit unless you can replace them with observable behavior and impact.

Translate labels into facts:

- Instead of "careless," say "the GitHub pull request did not include the agreed test plan, and the missing step delayed release review."
- Instead of "defensive," say "when Priya raised the Jira dependency, you interrupted twice and did not answer the dependency question."
- Instead of "not strategic," say "the roadmap proposal listed features but did not identify customer segment, renewal impact, engineering dependency, or success measure."
- Instead of "bad attitude," say "in the Slack thread, you wrote that Customer Success should 'figure it out' without answering the Webex scheduling question or naming an owner."
- Instead of "low ownership," say "the Salesforce follow-up was still unassigned two business days after the customer call, even though you agreed to own the next step."
- Instead of "poor communication," say "the Webex recap did not include decision, owner, due date, or open risk, so three teammates asked for clarification."

Personality labels are weak evidence and can create fairness problems. They are also hard for an employee to act on. Most employees can change a follow-up habit, a review checklist, a meeting structure, or a customer-note standard. They cannot usefully act on a manager's private diagnosis of their personality.

## Feedback in 1:1s

1:1s are the most common place for feedback, but managers should not hide urgent feedback until the next scheduled meeting if the impact is immediate. Use the 1:1 for patterns, development, and follow-up. Use a timely Webex call or direct message for something that needs same-day correction.

Bring examples from work systems. "Let's talk about the last three Jira tickets and what made estimation hard" is better than "I feel like planning is messy." "I want to review the last two Salesforce renewal notes and agree on the standard" is better than "You need to be more buttoned up."

End the 1:1 feedback topic with an action. Actions may include a checklist, a paired review, a draft before sending, a revised Jira ticket, a Salesforce note update, a GitHub review standard, a Webex meeting plan, or a follow-up date. Without an action, the employee may hear the feedback as a general complaint.

For brand-new reports, feedback should be more frequent and instructional. New employees are still learning NovaOps systems and norms. For experienced employees, feedback may focus more on judgment, cross-team influence, and consistency. In both cases, do not assume silence means understanding. Ask the employee to summarize the next step if the topic is important.

## Feedback Across Differences

NovaOps teams work across locations, departments, employment types, and communication styles. Managers should keep feedback consistent without pretending everyone needs the same delivery.

Check whether the standard was clear and equally applied. If a senior engineer receives gentle coaching for missing a GitHub review standard, a contractor should not receive harsher feedback for the same first-time miss. If a remote employee is criticized for not knowing hallway context, the manager should first ask whether the context was documented in Jira, Salesforce, Notion, or Slack.

Do not make feedback about accent, communication style, timezone, caregiving schedule, disability, age, nationality, or personality. If the work issue is clarity, name the work artifact: "the customer recap did not include decision, owner, and date." If the issue is availability, name the working agreement: "we need a posted overlap window for renewal escalations." If the issue may relate to accommodation, leave, medical information, or protected status, involve People Operations.

Feedback should not require employees to perform emotion for the manager. An employee may be quiet, surprised, or thoughtful after receiving feedback. That is not automatically resistance. Focus on whether they understand the expectation and follow through.

## Team and Peer Feedback

Managers often hear feedback about a report from peers, customers, or cross-functional partners. Treat that input as a signal to verify, not as a verdict to forward anonymously.

Do not say, "People are saying you are hard to work with." Say, "In the Slack thread about the billing dependency, the question from Product was not answered, and the final decision stayed unclear. I want to talk about how you handled that handoff." If the feedback comes from a customer, use the customer-facing artifact where possible: Webex recap, Salesforce note, SupportDesk ticket, or renewal email summary.

Anonymous feedback may be appropriate in formal review calibration or People Operations investigations, but ordinary management feedback should be grounded in examples the employee can understand. Do not ask peers to collect complaints in Slack. Do not share private performance details with the team to justify a manager decision.

When feedback involves conflict between two employees, focus on future working agreements: who owns which decision, which channel to use, what must be documented, and how disagreement gets escalated. See [navigating difficult conversations](navigating-difficult-conversations.md).

## Difficult Feedback

If feedback points to a serious or repeated gap, document it and follow up. If the employee's job may become at risk, involve People Operations before implying consequences. See [performance management](performance-management-model.md) and [underperformance and terminations](underperformance-and-terminations.md).

Serious feedback should be delivered in a real conversation, usually Webex or in person. Do not use a long Slack message to deliver feedback that could affect trust, performance standing, role scope, compensation, promotion, or continued employment. Use Slack afterward only for a factual recap when appropriate.

Prepare before difficult feedback. Write down the specific examples, the standard, the impact, what you want to ask, and what next step you expect. Check whether you are angry, embarrassed, or trying to prove a point. If so, wait until you can be direct and fair.

During the conversation, do not over-talk. State the issue, give the example, explain impact, ask for the employee's view, and set next steps. The employee may be upset or defensive. Acknowledge the reaction without changing the facts: "I understand this is frustrating. The expectation is still that Salesforce renewal risks are documented before the handoff."

If the employee raises new facts that could change the feedback, pause. New facts may include missing system access, approved leave, a medical restriction, harassment or discrimination concerns, conflicting instructions, or evidence that the manager's example is wrong. Pausing is better than forcing a conclusion that may no longer be fair.

## Feedback Checklist

Before giving feedback, managers should be able to answer:

- What exact situation am I discussing?
- What behavior, decision, or artifact did I observe?
- What was the impact on customer, team, project, quality, risk, or timeline?
- Is this positive feedback, corrective feedback, coaching, or formal performance management?
- Is the channel appropriate for the sensitivity of the topic?
- What should the employee repeat or change?
- What follow-up date or evidence will show whether the feedback worked?
- Does People Operations, IT, Finance, or Legal need to be involved?

If you cannot answer these questions, keep preparing. If the issue is urgent, prepare quickly and ask for help. Clarity is part of the manager's job.
