---
last_updated: 2024-06-05
corpus: handbook
audience: all
---

# Titles for Support

## Support and Customer Success

Support at NovaOps sits inside Customer Success. The team helps customers use workflow automation safely and effectively, turns recurring pain into product feedback, and protects trust during incidents. Support titles recognize customer judgment, product fluency, written clarity, and the ability to solve problems without creating new ones.

Support work includes reactive support cases, proactive customer health work, onboarding help, renewal-risk discovery, incident communication, and the translation of customer pain into useful Product and Engineering signal. Some employees carry "Support" titles and spend most of the day in SupportDesk. Others carry "Customer Success" titles and split time among Salesforce account work, Webex customer conversations, SupportDesk follow-up, and internal coordination. The ladder below applies when the work is primarily customer-facing problem solving inside Customer Success.

Support employees usually work in Salesforce, Slack, Webex, Jira, SupportDesk, and approved customer communication channels. Access is granted by role and reviewed when someone changes teams. Salesforce is used for account context, contacts, renewal risk, contract-sensitive notes, and customer health. SupportDesk is used for support cases, customer-visible updates, internal notes, tags, severity, and handoff history. Jira is used when a customer issue needs Product, Engineering, QA, or release work. Webex is used for live customer calls when written support will not resolve confusion quickly enough or when trust needs a human conversation. Slack is for internal coordination, but durable decisions should be copied into Salesforce, SupportDesk, Jira, or the NovaOps wiki according to the subject.

Support employees should understand the difference between helping, promising, and committing the company. A support employee may explain documented behavior, collect evidence, route a case, propose a workaround, and set a next update time. A support employee should not promise a release date, offer contractual concessions, approve billing changes, disclose security details beyond approved language, or guarantee a root cause before Engineering has confirmed it. When in doubt, preserve trust by saying what is known, what is being checked, who owns the next step, and when the customer will hear back.

## Tools and Records

Support quality depends on leaving a record that the next person can trust. A customer should not have to repeat the same story because the previous support note was vague, and an engineer should not have to reconstruct a defect from a chat summary. The default expectation is that SupportDesk contains the support case record, Salesforce contains account and relationship context, Jira contains product work, and Webex is summarized afterward when it changes the case.

Use SupportDesk for the customer-facing ticket, severity, timestamps, troubleshooting evidence, internal notes, attachments that are approved for support handling, and the final resolution. Public replies should be clear, calm, and specific about the next step. Internal notes should separate facts from guesses. A note such as "customer says workflow paused after approval step, observed on tenant demo-421, started after 2026-06-18 release, logs attached in Jira" is useful. A note such as "customer angry, probably bug" is not enough.

Use Salesforce when the issue affects customer health, renewal risk, executive relationships, onboarding milestones, expansion discussions, or named account ownership. Salesforce should not become a duplicate support thread. Link or reference the SupportDesk case, summarize the customer impact, and name the business risk. For example, Rachel Stein may update Salesforce when a recurring automation failure threatens a renewal conversation, while keeping the troubleshooting detail in SupportDesk and Jira.

Use Jira when the case requires Product, Engineering, QA, documentation, or release tracking. A good Jira escalation includes the customer impact, reproduction steps, affected workflow, expected behavior, actual behavior, severity, known workaround, relevant SupportDesk case, and a clear request. Do not create a vague Jira issue for every unhappy customer. Escalate when there is evidence of a defect, unclear product behavior that needs a product decision, documentation that is creating repeat cases, or a customer-impacting gap that the support team cannot resolve alone.

Use Webex when live conversation is the right tool: a new admin needs guided setup, an executive sponsor needs reassurance during an incident, a customer is confused after several written replies, or a sensitive renewal-risk conversation would be harmed by a long email chain. After the call, summarize the outcome in the system of record. If a Webex call produces a product decision, a customer commitment, a new risk, or a workaround, the summary belongs in SupportDesk, Salesforce, or Jira before the next handoff.

Customer-facing employees should be careful with seat-limited tools. Webex seats are prioritized for customer-facing work when licenses are tight. SupportDesk agent seats are shared between Customer Success and IT, so requests for extra agent access should name the role need and manager approval. Salesforce access is restricted to Sales, Customer Success, and approved operational support roles. See [our internal systems](our-internal-systems.md) for access and approval rules.

## Levels

### S1, Support Specialist

An S1 Support Specialist handles defined customer questions, follows playbooks, documents cases clearly, and escalates when a problem may involve product defects, security, billing, or contractual commitments. S1 work is expected to be reliable inside a bounded area. The person should not need reminders to update the customer, capture evidence, or ask for help when the case leaves the playbook.

An S1 can answer common questions about workflow setup, user invitations, basic automation behavior, notification timing, and known configuration limits. They can guide a customer through a documented SupportDesk article, confirm the account context in Salesforce when they have access, and schedule or join a Webex call when a more senior teammate asks them to help with setup. They should know when a question is simple and when it only looks simple.

Strong S1 behavior includes:

- Writing SupportDesk replies that are polite, plain, and specific.
- Reproducing simple customer reports before escalating.
- Including screenshots, timestamps, workflow names, tenant names, and exact error text when available.
- Tagging the case correctly so trends can be found later.
- Checking Salesforce for account owner and customer tier before giving timing expectations.
- Asking a senior teammate before giving advice that might affect security, billing, legal terms, or a renewal.
- Updating the customer before the promised time, even when the update is "we are still investigating."

An S1 is not expected to design cross-team escalation paths or own difficult executive conversations alone. The judgment expected at S1 is early recognition. If a customer says data may be exposed, a payment is blocked, an executive sponsor is threatening churn, or a production workflow stopped for many users, the S1 should not try to solve quietly. They should preserve evidence, alert the right owner, and keep the customer informed with approved language.

Maya Cohen, when ramping as a Customer Success Manager, may perform S1 support activities during onboarding: shadow SupportDesk cases, write draft replies for review, learn how Salesforce records customer health, and join Webex calls with a buddy. That early work can be useful evidence of product learning, but it does not by itself establish S2 or S3 scope.

### S2, Customer Support Specialist

An S2 Customer Support Specialist owns a broader queue, explains product behavior clearly, identifies patterns, and partners with Engineering or Product through Jira when customer issues need deeper investigation. S2 is the first level where independent ownership matters. The employee should be able to manage a normal support day without a senior teammate deciding every next step.

An S2 can handle ambiguous cases where the answer is not obvious but the risk is still contained. Examples include a customer who changed a workflow and now sees unexpected approvals, a new admin who cannot tell whether a rule failed or was misconfigured, or several customers reporting confusion after the same release note. The S2 should gather evidence, test reasonable hypotheses, avoid overclaiming, and decide whether the issue is a support answer, a documentation gap, a product bug, or an account-health concern.

Strong S2 behavior includes:

- Owning the customer communication plan for routine and moderate cases.
- Connecting multiple SupportDesk cases into a pattern before the queue becomes noisy.
- Creating Jira issues with reproduction steps and customer impact when a product investigation is needed.
- Updating Salesforce when a support issue creates renewal risk, onboarding risk, or sponsor concern.
- Knowing when a Webex call will reduce confusion and when it will waste customer time.
- Coordinating with IT when access or tool limits affect support delivery.
- Explaining product behavior in customer language without blaming Product, Engineering, or the customer.

Rachel Stein's Customer Success Specialist role is an example of S2-shaped work when she owns a queue, keeps Salesforce and SupportDesk aligned, and handles normal customer conversations independently. If Rachel has a Webex license issue while supporting customers, strong S2 judgment means she names the customer impact, uses approved fallback channels where possible, and routes the license problem through IT instead of letting customer follow-up disappear.

An S2 should not create unnecessary escalations to look responsive. Sending every confusing case to Engineering without evidence slows everyone down and damages credibility. An S2 should also not hide repeated confusion by answering each ticket separately. If five customers misunderstand the same automation setting, the stronger move is to flag the pattern, improve the article or template, and ask Product whether the behavior itself needs to be clearer.

### S3, Senior Support Specialist or Customer Success Manager

An S3 Senior Support Specialist or Customer Success Manager handles complex accounts, coaches teammates, manages difficult conversations, and turns customer feedback into useful internal signal. A senior support employee can balance empathy with boundaries. S3 is the level where the company trusts the employee to protect the customer relationship while also protecting NovaOps from bad commitments.

An S3 can own complicated customer situations: a workflow automation failure affecting an important business process, an onboarding account that is losing confidence, a renewal at risk because of repeated support friction, or a defect where the workaround is inconvenient but safer than waiting for a release. The S3 should make the customer feel heard without promising what the company cannot yet deliver.

Strong S3 behavior includes:

- Leading difficult customer conversations with a clear agenda, evidence, and next update time.
- Coaching S1 and S2 teammates on case framing, customer tone, and escalation quality.
- Deciding when a case needs Jira, when it needs Salesforce attention, and when it can be resolved in SupportDesk.
- Translating messy customer frustration into specific Product or Engineering questions.
- Proposing safe workarounds and naming their limits.
- Keeping Sales informed when a case affects a renewal or expansion conversation.
- Helping Product distinguish one loud customer preference from a broader product problem.
- Writing internal summaries that leaders can use without attending every call.

A Customer Success Manager such as Maya Cohen may become S3 when she can own customer health and complex support outcomes, not merely when she has many customer meetings. For example, if Maya guides a customer through a troubled launch, coordinates a SupportDesk case, opens a precise Jira issue for an automation defect, updates Salesforce with renewal risk, and keeps the customer informed without overpromising, that is S3-shaped evidence. If she only attends Webex calls while a senior teammate makes all decisions, that is useful participation but not yet S3 ownership.

S3 judgment includes saying no well. A customer may ask for a private roadmap guarantee, a custom billing concession, a shortcut around approval rules, or direct Engineering access for every question. The S3 should acknowledge the need, offer the supported path, and involve the right owner when the request crosses authority. Saying "I cannot promise that today, but I can confirm the decision owner and next update by Thursday" is often stronger than saying yes and repairing the damage later.

### S4, Support Lead or Senior Customer Success Manager

An S4 Support Lead or Senior Customer Success Manager owns support quality for a segment, improves processes, and coordinates with Sales, Product, and Engineering on customer health. This level may include people management, but can also be senior individual contribution. S4 work is measured by the system getting better, not by the lead personally rescuing every difficult case.

An S4 might own support quality for enterprise onboarding, workflow automation incidents, renewal-risk accounts, or a customer segment. They should know the health of the queue, the recurring failure modes, the customers who need proactive attention, and the internal teams that must change behavior. They should be able to run a support retrospective, revise escalation criteria, improve templates, and negotiate priorities across Customer Success, Sales, Product, Engineering, QA, IT, and Finance when needed.

Strong S4 behavior includes:

- Setting quality standards for SupportDesk case notes, customer replies, and escalation evidence.
- Creating playbooks for common but risky situations, such as suspected security issues or release-related workflow failures.
- Reviewing Jira escalation quality and helping Support avoid weak or duplicate product requests.
- Building account-health views in Salesforce or operating reports that show risk earlier.
- Partnering with Sales on renewal-risk language without letting revenue pressure distort the support facts.
- Coordinating Webex-heavy customer recovery plans while preserving written records.
- Improving onboarding, handoff, and access processes for the support team.
- Coaching managers or senior ICs on support judgment and customer trust.

An S4 is expected to manage edge cases calmly. If SupportDesk shows a spike in similar automation failures after a release, the S4 should gather the pattern, align with Engineering and Product through Jira, decide customer update timing, and make sure Salesforce reflects real account risk. If Webex seats are over the limit and customer-facing calls are being blocked, the S4 should work with IT and Finance through the normal approval path rather than asking teammates to share accounts or move customer conversations into unapproved tools.

S4 scope can include people management, but people management alone does not make the level. A manager who approves schedules but does not improve support quality is not operating at S4. A senior individual contributor who redesigns escalation flow, reduces repeat cases, and improves customer trust across a segment may be operating at S4 even without direct reports.

### S5, Customer Success Director

An S5 Customer Success Director sets strategy for customer retention, support quality, and escalation management across the function. Yael Romano's Customer Success Director role is an example of this kind of scope. S5 work is about how Customer Success operates as a function: what support quality means, how escalation risk is governed, how customer trust is protected, and how customer feedback changes the company.

An S5 should be able to answer questions such as: which support problems are putting revenue or trust at risk, where the team is underinvesting, which tools or processes are creating hidden cost, what Product needs to hear from customers, and which escalation rules prevent panic without slowing urgent response. The S5 sets direction, but also makes sure the direction can be used by S1 through S4 employees in real cases.

Strong S5 behavior includes:

- Defining support and customer-health strategy across segments.
- Setting escalation standards with Sales, Product, Engineering, IT, Finance, and company leadership.
- Owning customer communication principles for major incidents and repeated product pain.
- Using Salesforce, SupportDesk, Jira, and customer feedback to identify systemic risk.
- Deciding where to invest in staffing, tooling, documentation, automation, or training.
- Making tradeoffs between short-term customer recovery and long-term product or process health.
- Representing Customer Success in company-level planning without turning every customer request into a roadmap commitment.
- Ensuring promotions, calibration, and growth expectations are fair across Support and Customer Success roles.

Yael Romano may approve or guide high-risk escalations, but S5 success does not mean every hard customer call waits for Yael. A strong S5 creates a system where S2 employees can handle normal queue ownership, S3 employees can own complex accounts, and S4 employees can improve segment quality. If every customer concern must be personally rescued by the director, the support system is too fragile.

S5 also owns boundary clarity. Customer Success should influence Product, not become unofficial Product Management. Customer Success should partner with Sales, not promise discounts or contract terms without the right owner. Customer Success should coordinate with IT on SupportDesk and Webex access, not bypass access rules. Customer trust is built when the company is consistent about who can make which commitment.

## Escalation Judgment

Escalation is a judgment call, not a reflex. The purpose is to get the right owner involved at the right time with enough evidence to act. Under-escalation leaves customers exposed. Over-escalation teaches internal teams to ignore support signals. Strong support employees learn to tell the difference.

Escalate quickly when a case may involve security, privacy, billing, contractual commitments, production incidents, data integrity, broad customer impact, executive sponsor risk, or a customer commitment that NovaOps may not be able to meet. Escalate with evidence when a product defect is likely, when the same confusion repeats across customers, when the documented behavior conflicts with customer need, or when a workaround creates meaningful risk.

Do not escalate just because the customer is loud, the account is large, the support employee is uncomfortable, or the answer is not immediately known. Those facts may influence urgency, but they do not replace evidence. A loud customer with a configuration mistake still deserves calm help, not a fake emergency. A small customer with a possible data issue deserves immediate attention, even if the account is not large.

A useful escalation includes:

- Customer name and account owner.
- SupportDesk case link or case identifier.
- Salesforce account context when relevant.
- Customer impact and business consequence.
- Severity and why that severity was chosen.
- Reproduction steps, timestamps, workflow names, screenshots, or logs when available.
- Known workaround and its limits.
- Customer-facing promise already made, if any.
- Requested decision or action.
- Next customer update time.

Realistic edge cases include:

- A customer says "data was exposed" but provides no details. Treat this as potentially serious, preserve the SupportDesk record, avoid speculation, and involve the security or incident path. Do not promise breach conclusions.
- A customer demands a release date for a fix. Support may share approved status and next update timing, but Product or Engineering owns release commitments.
- A Sales teammate asks Support to mark a case resolved before a renewal call. Support may summarize progress in Salesforce, but should not hide unresolved customer impact.
- A customer asks for a Webex recording to include sensitive workflow details. Confirm the approved handling path before recording or sharing.
- A Product Manager wants direct access to every support case. Share relevant SupportDesk or Jira context according to access rules; do not broaden access without approval.
- A Jira issue is closed as "works as designed" but customers keep opening cases. Support should not reopen the same ticket repeatedly without new evidence; the stronger move is to summarize the pattern and ask Product whether the design or documentation should change.
- A SupportDesk owner field says IT even though Customer Success owns the support process. Use the business owner and approval path described in [our internal systems](our-internal-systems.md), and do not treat database messiness as permission to bypass review.

## Customer Trust

Customer trust is not the same as customer happiness in the moment. A customer may be unhappy because the answer is no, because a bug takes time, or because a workaround is inconvenient. Support protects trust by being accurate, timely, respectful, and consistent.

Strong customer trust behaviors include acknowledging the customer's goal, naming what is known, avoiding blame, setting the next update time, and following through. When the answer changes, explain what changed. When NovaOps caused the problem, say so in approved language and focus on repair. When the customer caused the issue, avoid making them feel foolish; explain the safer configuration and how to prevent recurrence.

Support should use plain language. Customers should not need to understand NovaOps org structure to understand their case. "Engineering is investigating an issue with approval-step evaluation and we will update you by 15:00 UTC tomorrow" is better than "ENG is checking the backend thing." "This is not a supported configuration because it can skip required approvals" is better than "we cannot do that."

Trust also depends on boundaries. Do not promise private roadmap items, unofficial discounts, special security terms, permanent workaround support, or immediate executive involvement unless the correct owner has approved it. Do not tell a customer that Product or Engineering "refused" to help. If an internal decision disappoints the customer, explain the supported path and next option.

Support employees should be careful with customer evidence. Use approved systems, do not move confidential customer data into personal notes, and do not paste sensitive customer details into broad Slack channels. If a screenshot, export, recording, or log contains sensitive data, ask for the approved handling path before sharing it. This is part of support professionalism, not an administrative detail.

## Promotion Evidence

Strong support evidence includes faster resolution of the right issues, better customer trust, fewer repeat escalations, clearer internal documentation, and product feedback that leads to improvement. Managers should look for judgment under pressure, not just ticket volume. A support employee who prevents recurring customer confusion may create more value than one who closes the most simple cases.

Promotions follow the process in [making a career](making-a-career.md). Evidence should include customer outcomes, collaboration examples, and the way the employee strengthened the support system for others. A good promotion packet should map examples to the next level rather than listing every case the employee touched.

Useful evidence can include:

- SupportDesk cases showing clear communication, evidence quality, and appropriate ownership.
- Salesforce updates showing account-health judgment, renewal-risk clarity, or customer recovery.
- Jira issues that led to product fixes, documentation improvements, or better release decisions.
- Webex call summaries that turned confusing live conversations into durable next steps.
- Customer feedback that mentions clarity, trust, recovery, or confidence rather than only friendliness.
- Reduced repeat cases because the employee improved a template, article, workflow, or product signal.
- Better escalation quality, such as fewer duplicate Jira issues and faster Engineering triage.
- Coaching that made S1 or S2 teammates more independent.
- Cross-functional examples where Support influenced Product, Engineering, Sales, IT, or Finance with evidence.
- Judgment under pressure, especially when the employee avoided overpromising.

For S1 to S2, evidence should show independent queue ownership, clearer explanations, good case hygiene, and the ability to identify patterns. For S2 to S3, evidence should show complex account ownership, difficult customer conversations, useful coaching, and stronger cross-functional judgment. For S3 to S4, evidence should show segment-level quality improvement, process ownership, and leverage beyond the employee's own accounts. For S4 to S5, evidence should show function-level strategy, durable escalation systems, and measurable improvement in customer trust, retention, or support quality.

Promotion evidence should separate activity from impact. "Handled 400 tickets" is incomplete. "Reduced repeat onboarding tickets by changing the admin setup guide, creating a SupportDesk macro, and opening a Jira request for confusing copy" is stronger. "Joined many customer calls" is incomplete. "Led three at-risk customer recovery plans, kept Salesforce risk current, and prevented unsupported roadmap commitments while restoring executive trust" is stronger.

Managers should include the hard parts. A promotion packet is more credible when it names the ambiguity, risk, or tradeoff. If Rachel Stein resolved a Webex-related customer follow-up problem, the packet should explain how she protected the customer experience despite the tool constraint. If Maya Cohen owned a troubled onboarding account, the packet should describe what decisions she made, what help she asked for, and what changed for the customer. If Yael Romano sponsors an S4 promotion, the evidence should show that the employee improved support quality beyond their personal relationships with customers.

## What Does Not Count

Some work is useful but not promotion evidence by itself. This section is not meant to dismiss effort. It helps managers and employees avoid confusing motion with level.

Weak or incomplete evidence includes:

- Closing many simple cases without improving customer outcomes or support quality.
- Being friendly in Webex calls while someone else owns the hard decisions.
- Staying online late as a habit instead of improving escalation paths or coverage.
- Escalating everything to Engineering to look urgent.
- Avoiding escalation until the customer loses trust.
- Writing long internal updates that do not name the decision, owner, evidence, or next step.
- Receiving Slack praise that is not tied to customer impact or level expectations.
- Owning a crisis that the employee helped create through poor handoff, overpromising, or missing evidence.
- Becoming the only person who knows how to handle a case type instead of documenting and teaching it.
- Pushing for a customer exception that violates access, billing, security, or contract boundaries.
- Creating duplicate Salesforce, SupportDesk, and Jira records that disagree with each other.

A customer saying "thank you" is good, but it does not automatically prove seniority. A customer being angry does not automatically prove the support employee did anything wrong. The question is whether the employee used the right judgment for the level: clear facts, appropriate urgency, honest communication, durable records, and better outcomes over time.

## Role Examples

Rachel Stein is a Customer Success Specialist in the United Kingdom. Examples that fit her role include owning SupportDesk cases for active customers, using Salesforce to understand account context, joining Webex calls to resolve confusion, and opening Jira issues when customer evidence points to a product or documentation problem. If Rachel notices three customers struggling with the same automation rule, strong work is to connect the pattern, improve the support response, and escalate the product question with evidence.

Maya Cohen is a Customer Success Manager in Israel during preboarding and early ramp. Examples that fit her role include learning SupportDesk workflows, shadowing customer calls, keeping Salesforce account notes clean, and gradually owning onboarding risks. As she grows, stronger evidence would include leading a customer through a complex launch, coordinating a support escalation, and maintaining trust without making commitments outside her authority.

Yael Romano is the Customer Success Director. Examples that fit her scope include setting escalation standards, approving support-quality investments, aligning with Product and Engineering on customer-risk themes, and making sure SupportDesk, Salesforce, Webex, and Jira are used consistently. Yael should be involved in high-risk customer strategy, but the support ladder is healthier when her team can resolve ordinary and moderately complex cases without waiting for director intervention.

Support and Customer Success titles should reflect actual work. A person with a customer-facing title who mostly performs internal operations may fit the [operations ladder](titles-for-ops.md) better. A person embedded in release testing may fit the [QA ladder](titles-for-QA.md). A person doing product discovery may contribute useful customer insight, but Product title expectations are different from Support title expectations. When the ladder choice is unclear, the manager should explain which outcomes the employee owns and which title guide best matches the evidence.
