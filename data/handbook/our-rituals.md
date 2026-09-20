---
last_updated: 2026-05-29
corpus: handbook
audience: all
---

# Our Rituals

## Why Rituals Matter

Remote-first work needs a rhythm. NovaOps rituals are meant to create context, reduce surprise, and help people feel the company moving without filling every calendar. A ritual that no longer helps should be changed or retired.

Rituals are not ceremonies for their own sake. They are recurring ways to keep decisions, customer signals, delivery risk, people operations, and recognition visible across Israel, Germany, the United Kingdom, the United States, and contractor locations. A good ritual makes the next action easier to find. A weak ritual creates calendar weight without clearer work.

NovaOps is hybrid and remote-first, so our rituals start from written context. Live discussion is still useful, especially for debate, trust, onboarding, incidents, and sensitive topics, but the default assumption is that a teammate should be able to understand what happened even if they were asleep, on leave, in another time zone, or joining the company later. For the broader collaboration model, see [how we work](how-we-work.md).

Every recurring ritual should have an owner, a cadence, a place where notes or artifacts live, and a clear reason to exist. Emma Wilson owns the weekly company update, Product and Engineering jointly own the every-second-Thursday demo, Tom Baker owns the monthly spending review, and Yael Romano owns the Customer Success customer-story review. If a ritual crosses functions, name one directly responsible person even when many leaders contribute.

Rituals should help employees and managers answer practical questions: what changed since the last update, who owns the next action, what decision was made, where it is recorded, what risk needs attention before it becomes urgent, and what can be handled async instead of adding another meeting.

## Weekly Company Update

Every Monday, Emma Wilson posts a company update in Slack. It covers customer wins, operational risks, hiring updates, upcoming holidays, and decisions that affect more than one department. Department leads reply with short notes by Tuesday. Employees are encouraged to ask questions in the thread so answers are visible to everyone.

The weekly company update is async by design. It should be readable by an engineer in Israel before focus work, a Customer Success teammate in the United Kingdom after a customer call, and an Account Executive in the United States after their morning pipeline review. Emma may post earlier or later when travel, holidays, or incidents interfere, but the update should still land on Monday whenever possible.

Department lead replies should be short, specific, and searchable. A useful reply from Liam Oconnor might name pipeline risk, a new Salesforce hygiene focus, and one win from Rachel Green or Daniel Cohen. A useful reply from Yael Romano might name customer health themes, SupportDesk escalation patterns, and one renewal risk. A useful reply from Sara Ben-David might name onboarding volume, benefits deadlines, or a policy reminder. A useful reply from Amir Haddad might name access review work, Webex license pressure, laptop fleet issues, or upcoming Okta maintenance.

Employees can ask questions directly in the company update thread. Questions that many people might have should stay public unless they involve confidential employee, customer, security, or payroll details. If the answer changes a policy, deadline, customer commitment, budget decision, or system workflow, the owner should copy the final answer into the right durable place, such as the NovaOps wiki, Jira, Salesforce, BambooHR, or a handbook page.

Examples of good company update items:

- Customer Success saw three customers ask for clearer automation audit logs; Yael Romano and Noam Sharon will bring patterns to Thursday's Product review.
- IT is prioritizing customer-facing Webex seats this week because the seat pool is tight; Lina Novak will update affected requesters.
- Finance will review recurring software spend with department leaders this month; Tom Baker needs forecasts for license expansions above normal team usage.
- People Operations is preparing preboarding for Maya Cohen and Ben Walker; managers should confirm first-week schedules and access requests.

The company update is not a place for surprise performance feedback, private HR information, unresolved security details, or customer names that should stay confidential. It is also not the place to debate every detail. If a thread grows into a decision discussion, move to the correct working channel, make the decision with the accountable owner, and return with a short summary.

## Time Zones and Core Collaboration

NovaOps operates across several workdays at once. The core collaboration window is 13:00-16:00 UTC on Tuesday through Thursday. Teams should use that window for rituals that require live cross-region participation, especially planning, demos, customer escalations, interviews, manager calibration, and decisions that need Product, Engineering, Customer Success, Sales, Finance, HR, or IT together.

The core window is not a rule that everyone must be online for every minute. It is the shared overlap we protect so remote-first work remains humane. An employee in Israel or Germany should not have to mirror a United States calendar all week. A United States employee should not be expected to start before dawn because a topic could have been handled async. A contractor such as Priya Raman in India may need recordings, notes, or alternate handoffs when the main live discussion lands late in their day.

Daylight-saving time creates messy edges. The United Kingdom, Germany, Israel, and the United States do not always change clocks on the same date. When the clocks shift, meeting owners should check whether a recurring ritual has become unreasonable for one region. If a meeting moves outside reasonable hours for a required participant, either move it, rotate the inconvenience, or make the required input async.

Local holidays matter. The Monday company update should name upcoming holidays when they affect staffing, support coverage, payroll timing, release plans, or customer-facing work. Managers should watch for holiday clusters across countries instead of assuming that one region's normal week is normal for everyone.

When a ritual must happen outside the core window, the owner should explain why, keep the attendee list narrow, and provide notes afterward. Valid reasons include production incidents, customer incidents, security response, payroll blockers, legal deadlines, customer executive meetings, and a one-time schedule constraint with a specific decision at stake. "This was the only open slot" is not a strong reason for a recurring meeting.

## Async Updates

Async updates are a ritual, not a lack of ritual. They keep work moving when teammates are in different locations or on different schedules. A good async update includes the current state, the next step, the owner, the decision needed, and the real deadline. It should be possible to read the update and know whether to act, wait, ask a question, or escalate.

Use Slack for short-lived coordination and quick visibility. Use Jira for planned work, cross-team delivery, bugs, release tasks, and Engineering or Product ownership. Use GitHub for code review and technical decisions attached to code. Use Salesforce for customer and revenue workflows. Use SupportDesk for customer support cases. Use BambooHR for HR workflows. Use the NovaOps wiki or handbook for decisions and guidance that need to outlive a thread. For system boundaries, see [our internal systems](our-internal-systems.md).

An async ritual may be daily, twice weekly, or event-based. Teams should choose the lightest cadence that keeps risk visible. Engineering pods may post end-of-day Jira notes during a launch week and relax the cadence after release. Customer Success may post customer escalation summaries during a renewal push. HR may post onboarding checkpoint updates during the week before a new employee starts. Finance may post month-end reminders while invoices and approvals are in flight.

Useful async update format:

```text
State: What is true now?
Owner: Who is directly responsible?
Next step: What will happen next?
Decision or blocker: What needs attention?
Deadline: What date or customer event makes this matter?
Artifact: Where should people look for details?
```

Example: "State: Webex license seat request for Rachel Stein is blocked by seat availability. Owner: Lina Novak. Next step: IT will check reclaim candidates and Finance will confirm whether expansion is approved. Decision or blocker: customer-facing meetings this week need priority. Deadline: before Rachel's onboarding call on Thursday. Artifact: IT ticket and Salesforce account note."

Async updates should not hide urgency. If a production incident, customer incident, payroll blocker, or security issue needs immediate attention, use the escalation path and name the owner, severity, working channel, and next update time. After the urgent moment passes, move the facts back into durable systems so the history is not trapped in a live call.

## Team Planning

Teams plan work in weekly or biweekly cycles depending on the department. Engineering and Product plan in Jira. Sales and Customer Success review Salesforce pipeline, renewals, and customer health. HR, IT, and Finance use team boards for operational work and compliance deadlines.

Planning should name the outcome, owner, due date, and dependency. If a plan only lists activities, it is not finished yet.

Planning is where a team turns goals into commitments and tradeoffs. It is not a ritual for reading every ticket aloud. The owner should send context before the meeting whenever possible: proposed priorities, known constraints, customer deadlines, staffing gaps, and decisions needed. People who cannot attend should still be able to comment before the plan is final.

Engineering and Product planning should connect Jira work to customer or operational outcomes. Noam Sharon may bring the product problem, David Miller may bring design constraints, Daniel Levi may raise backend reliability or AWS risk, and contractors such as Priya Raman or Alex Kim may own scoped implementation work. A good Jira plan names the release target, the customer workflow affected, the test or review path, and the risk if scope changes.

Sales planning should connect Salesforce activity to pipeline quality, forecast risk, next customer action, and account ownership. Liam Oconnor should not need to ask "who owns this deal?" in every review. Rachel Green, Daniel Cohen, and Ben Walker should be able to see whether the next action is a call, a proposal, an executive follow-up, a data cleanup task, or a handoff to Customer Success.

Customer Success planning should connect Salesforce, SupportDesk, and customer health. Yael Romano should be able to tell which accounts need executive attention, which renewals need a product answer, and which customer issues should become Jira work. Rachel Stein or Maya Cohen may own follow-ups with customers, but the plan should also name when Engineering, Product, or Sales is needed.

HR, IT, and Finance planning should make operational risk visible before it becomes a scramble. Sara Ben-David, Sara Cohen, and Maya Rosen use HR planning to track onboarding, contractor paperwork, policy updates, benefits deadlines, and employee lifecycle work. Amir Haddad, Lina Novak, and Omar Weiss use IT planning to track access reviews, laptop logistics, Webex and Slack administration, AWS or GitHub risk, and security maintenance. Tom Baker uses Finance planning to track budget deadlines, approval thresholds, renewal timing, and spending reviews.

Messy planning exceptions are expected. A customer escalation may force Product to interrupt roadmap work. A security concern may change an Engineering sprint. A new hire start date may depend on laptop shipping or Okta provisioning. A renewal may require Sales, Customer Success, Finance, and Legal context on short notice. When this happens, update the plan instead of pretending the old plan still describes reality. The revised plan should name what moved, why it moved, who approved the tradeoff, and when it will be reviewed again.

## Standups, Huddles, and Checkpoints

NovaOps does not require every team to hold a daily standup. Some teams benefit from a brief live checkpoint, while others work better with written updates. The test is whether the ritual reduces coordination cost. If people leave a standup and still have to reconstruct status from Slack, Jira, or Salesforce, the ritual needs adjustment.

Live huddles should usually be 15 minutes or less and focused on blockers, priority changes, and handoffs. They are not a place to solve every problem. If a blocker needs deeper discussion, the owner should spin out a smaller Webex call or async thread with the right people.

Written standups should include enough context to be useful across time zones. "Yesterday: tickets. Today: more tickets. Blocked: none" is not useful. "Closed Jira NOVA-421 after Daniel Levi's GitHub review; today I am testing the SupportDesk sync; blocked on a Salesforce field mapping from Daniel Cohen" gives the next person something to act on.

During launch weeks, teams may add temporary checkpoints. For example, Product and Engineering may run a daily release readiness note while Noam Sharon, David Miller, Daniel Levi, and QA contributors prepare a customer-facing workflow change. Customer Success may add a daily escalation review when Yael Romano is coordinating several accounts through the same product issue. Temporary rituals should have an end date.

## Demos and Reviews

Every second Thursday, Product and Engineering run a 45-minute demo over Webex. Demos should show working software, customer workflow improvements, operational automation, or useful internal tooling. Slides are fine for context; the center of the ritual is showing the thing.

Customer Success runs a monthly customer-story review. Sales runs a monthly win/loss review. Finance runs a monthly spending review with department leaders. These reviews are not status theater; they are places to make better decisions.

The Product and Engineering demo should make work visible before it disappears into release notes. The demo owner should publish the agenda before the meeting, keep the session to 45 minutes, and leave time for questions. A strong demo might show a new automation flow, a reliability fix, a design prototype connected to a customer problem, a SupportDesk improvement, or an internal tool that reduces manual work.

Demo presenters should use real enough scenarios to make the work understandable without exposing confidential customer data. If the demo requires production data, anonymize it or use a safe test account. If a demo involves restricted systems such as AWS, Salesforce, GitHub, or BambooHR, the presenter should avoid showing secrets, private employee information, exported customer lists, or credentials.

Good demo examples:

- Noam Sharon walks through the product problem and the decision that changed scope.
- David Miller shows the before and after of a workflow design and names the rejected tradeoff.
- Daniel Levi shows how a backend change reduces retry failures or improves observability.
- Priya Raman shows a frontend improvement within the repository scope approved for her contractor work.
- Alex Kim shows a data integration validation path without exposing raw customer data.
- Rachel Stein explains how the change will reduce support confusion for Customer Success.

The monthly customer-story review is owned by Customer Success. It should bring the voice of the customer into Product, Engineering, Sales, and Operations. The point is not to celebrate only happy stories. A useful customer story may describe a confused onboarding, a renewal saved by fast follow-up, a feature gap, an incident handled well, or a pattern that should become roadmap input. Yael Romano should make sure the review produces at least one of the following: a Jira follow-up, a Salesforce note, a SupportDesk process change, a product decision, or a clear "no action" with a reason.

The monthly Sales win/loss review is owned by Sales. It should help NovaOps learn from deals rather than replay them. Liam Oconnor, Rachel Green, Daniel Cohen, and Sales Development teammates should look for patterns in buyer objections, competitor mentions, implementation concerns, pricing friction, and handoff quality. Win/loss notes belong in Salesforce and should be summarized without exposing confidential customer material in broad channels.

The monthly Finance spending review is owned by Tom Baker with department leaders. It should cover planned spend, renewal surprises, license growth, vendor risk, and budget tradeoffs. Webex, Slack guest accounts, GitHub contractor seats, AWS usage, and Salesforce licensing can all create cost or security risk if no one reviews the trend. The spending review is a decision ritual: it should end with approved spend, denied spend, more information requested, or a named owner to resolve the question.

Reviews should produce decisions, not just impressions. If a review surfaces an action, assign an owner and due date before the meeting ends. If the action affects a customer, add it to Salesforce or SupportDesk. If it affects delivery, add it to Jira or GitHub. If it affects budget, confirm the Finance path. If it affects policy or employee records, involve People Operations and use the right HR system.

## Customer-Facing Rhythms

Customer-facing rituals connect Sales, Customer Success, Product, Engineering, Finance, and Operations around the customer experience. They should make account ownership, customer health, implementation risk, renewal timing, and product feedback visible before a customer has to repeat the same concern to three NovaOps teams.

Sales pipeline reviews should focus on forecast quality and next actions. Liam Oconnor owns the Sales manager view, but Account Executives and Sales Operations keep the data useful. Rachel Green should be able to rely on Salesforce to show account stage, next meeting, decision maker, close risk, and needed help. Daniel Cohen should use Sales Operations rituals to catch missing fields, duplicate records, and handoff gaps before they distort the forecast.

Customer Success health reviews should focus on adoption, support patterns, renewal risk, and customer trust. Yael Romano owns the director view, but Customer Success Managers and Specialists bring the evidence. Rachel Stein should connect SupportDesk cases to account health. Maya Cohen, after onboarding into the Customer Success Manager role, should learn the rhythm for renewal notes, executive sponsor updates, and product feedback loops.

Customer handoffs from Sales to Customer Success should be explicit. A good handoff includes the customer goal, promised scope, open risks, decision makers, timeline, integration notes, and any support expectations. If Sales promised a customer-facing Webex walkthrough, the owner should make sure the required teammate has Webex access or a backup presenter. If Product or Engineering needs customer context, use curated notes rather than granting broad Salesforce access by default.

Executive customer meetings are allowed to override normal calendars when the business need is real, but the preparation should still be remote-first. The owner should share the agenda, customer context, decision needed, speaking roles, and follow-up owner. After the meeting, the owner should post a summary in Salesforce or the appropriate customer workspace and tag only the people who need to act.

Customer escalations are not won by adding everyone to a channel. They are handled by naming the accountable owner, the customer impact, the next update time, and the decision needed. A severe customer escalation might involve Yael Romano for customer communication, Noam Sharon for product tradeoffs, Daniel Levi or Omar Weiss for technical diagnosis, and Emma Wilson if an executive decision is needed. Keep the working group tight and the update path clear.

## Incidents and Urgent Exceptions

Incidents are one of the few times NovaOps intentionally breaks normal rhythm. Production incidents, customer incidents, security issues, payroll blockers, and access problems that prevent customer commitments may require faster response, narrower decision rights, and meetings outside the usual collaboration window.

An incident ritual begins when the first accountable owner names the issue clearly. The first update should include severity, customer or employee impact, owner, working channel, next update time, and whether a live Webex bridge is needed. If the incident touches AWS, GitHub, Okta, Webex, Slack, Salesforce, BambooHR, or customer data, involve the right system owner or approver rather than guessing.

Example incident roles:

- Omar Weiss may lead cloud or AWS diagnosis when production infrastructure is involved.
- Amir Haddad may coordinate IT risk, privileged access, or SaaS administrator actions.
- Lina Novak may handle Webex, Slack, MFA, and first-line employee access issues.
- Daniel Levi may investigate backend behavior or prepare a GitHub fix.
- Yael Romano may own customer communication when Customer Success accounts are affected.
- Tom Baker may need to approve urgent spend if the fix requires an unplanned vendor or license action.
- Sara Ben-David may advise if the issue affects employee records, payroll, leave, or sensitive HR data.

Incident meetings should be small, direct, and documented. Do not invite a large audience because people are anxious. Invite the people who can diagnose, decide, communicate, or remove a blocker. Observers can follow written updates. If a decision is made live, the note taker should capture the decision, owner, time, tradeoff, and follow-up artifact.

Post-incident reviews should happen after major incidents, customer-visible incidents, security events, payroll blockers, and messy cross-functional failures. The review should ask what happened, what impact occurred, what signals were missed, what worked, what will change, who owns the change, and when the change will be checked. The purpose is learning and repair, not blame theater.

Some incidents reveal that an ordinary ritual is broken. If a Webex license shortage repeatedly blocks customer calls, the monthly spending review and IT planning rituals should address license forecasting. If customer escalations repeatedly lack product ownership, the customer-story review and Product planning rituals should change. If access mistakes recur for contractors, access review and onboarding rituals should become more explicit.

## People Operations and Onboarding Rituals

People Operations rituals help employees start, grow, change roles, and leave with fewer surprises. Sara Ben-David owns the People Operations lead view. Sara Cohen handles contractor paperwork. Maya Rosen coordinates many HR tasks and employee workflows. These rituals often involve private information, so they should be documented in the appropriate HR system rather than public Slack channels.

Preboarding starts before the employee's first day. The manager and People Operations should confirm the start date, role, manager, location, employment type, required systems, laptop or equipment needs, first-week schedule, and onboarding buddy. IT should receive access requests early enough to avoid first-day scrambling. For Maya Cohen, that means Customer Success systems such as Salesforce, Webex, Slack, Notion, Okta, BambooHR Employee Self-Service, and SupportDesk. For Ben Walker, that means Sales systems such as Salesforce, ZoomInfo, Webex, Slack, Notion, Okta, and the right onboarding tasks.

First-week rituals should mix context, setup, and one small real contribution. A new Customer Success teammate might shadow a Webex customer call, update a Salesforce note, and review a SupportDesk pattern. A new Sales teammate might review account qualification examples and practice a handoff note. A new engineer might review a small GitHub pull request and pick up a low-risk Jira ticket. Avoid filling the first week with eight hours a day of reading.

Manager, HR, and IT rituals must use full names when there is any chance of confusion. NovaOps has Maya Cohen and Maya Rosen, Sara Ben-David and Sara Cohen, Rachel Green and Rachel Stein, Daniel Levi and Daniel Cohen. Access requests, onboarding checklists, HR tasks, and recognition notes should use full names and email addresses when the system or topic is sensitive.

Role changes need their own ritual. When Noam Sharon moved from Customer Success to Product, access, manager context, team planning, customer workflows, and performance expectations needed to be revisited. A transfer ritual should name the effective date, current manager, new manager, systems to remove, systems to add, customer or project handoffs, and first 30 to 60 days of ramp.

Contractor rituals require extra care because access and end dates are part of the work. Priya Raman and Alex Kim should have scoped Jira work, limited GitHub access when approved, Slack or Notion guest access only where needed, and clear end dates tied to their agreements. Contractor rituals should include periodic checks that access still matches the statement of work.

## Recognition

We recognize work close to where it happened. Public praise in Slack is encouraged when the employee is comfortable with it. Managers should also give private thanks, especially for quiet operational work that prevents problems. See [benefits and perks](benefits-and-perks.md) for the referral bonus and learning budget.

Recognition is a ritual because it teaches the company what good work looks like. It should be specific enough that someone else can repeat the behavior. "Great job" is kind but thin. "Lina Novak resolved the Webex license issue before the customer onboarding call and documented the workaround for Customer Success" teaches more. "Daniel Levi caught a reliability risk in review before release" teaches more. "Sara Cohen cleaned up contractor paperwork before it delayed access" teaches more.

Public recognition belongs near the work when the employee is comfortable being named. A Slack thread, demo, team review, or company update can be a good place. Private recognition may be better when the work involved confidential customer information, employee details, security risk, payroll, or a person who dislikes public attention. Managers should ask and observe preferences rather than assuming everyone wants the same kind of praise.

Recognition should include quiet operational work. Preventing a problem is often less visible than rescuing one. Amir Haddad tightening an access review, Omar Weiss reducing AWS risk, Tom Baker catching unplanned spend before renewal, Maya Rosen preparing onboarding tasks early, or Daniel Cohen cleaning Salesforce data before a forecast review may prevent confusion that no one else sees. Managers should look for this work and name its impact.

Recognition should not reward unhealthy patterns. Do not praise weekend work as the default, constant availability, skipping time off, or creating a crisis and then fixing it dramatically. If someone helped during a true incident, thank them and then repair the system so the same heroics are less likely next time.

Recognition can feed growth conversations, but it does not replace evidence. Slack praise may support a performance review or promotion packet when it points to real outcomes, but managers still need examples from work systems such as Jira, GitHub, Salesforce, SupportDesk, customer notes, launch retrospectives, or operating checklists.

## Meeting Hygiene

Every live ritual should have a clear owner, purpose, and output. Default Webex meetings to 25 or 50 minutes when possible so people have time to switch context and write notes. If the last two sessions of a recurring meeting produced no decisions, no learning, no useful handoffs, and no relationship value, the owner should shorten, cancel, or redesign it.

Meeting invitations should make the expected role clear. Required participants are needed for the decision or work. Optional participants may benefit from context. People should not be invited just in case, especially across time zones. If a required decision maker cannot attend, the owner should either move the meeting or collect the decision async before finalizing.

Meeting notes should be short and useful. Capture decisions, owners, due dates, links to artifacts, and open questions. Do not write a transcript unless the situation requires one. Do not put private employee information, medical details, sensitive security findings, or confidential customer material in broad notes.

Use Webex when live nuance matters. Use Slack when quick coordination is enough. Use Jira, GitHub, Salesforce, SupportDesk, BambooHR, the team board, or the wiki when the artifact needs history. The ritual is not complete until the result is in the place where future teammates will look for it.

## Changing or Retiring a Ritual

Any employee may question a ritual that is no longer helping. Start with curiosity: what was the ritual meant to solve, what has changed, who still depends on it, and what would break if it stopped? Do not remove a ritual quietly when another team uses it for planning, customer communication, access, payroll, or budget timing.

To change a ritual, the owner should propose the new cadence, audience, artifact, and review date. For example, a weekly live status meeting might become an async Tuesday update plus a monthly decision review. A broad customer escalation meeting might become a small incident bridge plus written updates. A team standup might become three written updates per week during normal work and daily check-ins only during launch week.

Retiring a ritual is healthy when the work has changed. A temporary launch checkpoint should end after the launch. An incident bridge should close after the incident and retro actions are assigned. A contractor onboarding sync should end when access, scope, and first deliverables are stable. A recurring review that no longer informs decisions should be redesigned or stopped.

The best NovaOps rituals make work easier to understand, decisions easier to find, customers easier to support, and people easier to trust. If a ritual is doing that, protect it. If it is not, improve it.
