---
last_updated: 2025-12-27
corpus: manager_playbook
audience: manager
---

# Hiring

## Start With Approved Need

Hiring begins with an approved role, not an interesting candidate. A manager may notice a strong person in the market, but NovaOps does not begin recruiting until the business need, budget, location, and employment type are approved.

The department leader and Finance must approve headcount, compensation range, location assumptions, and employment type before recruiting starts. People Operations confirms the hiring process and opens the role in the approved workflow. If any of those inputs change during the search, pause and re-confirm before continuing. A role approved as a full-time employee in the United Kingdom is not automatically approved as a contractor in India, a remote employee in the United States, or a higher-level role in Germany.

Approved headcount should answer these questions before the first candidate screen:

- Is this role a new headcount, a backfill, a temporary project need, or a replacement for work currently handled by a contractor?
- Which department owns the role, and which manager will be accountable for onboarding and performance?
- What is the approved title, level, compensation range, target start date, and employment type?
- Which approved NovaOps location or time-zone band is required for the role?
- Which systems, licenses, equipment, and recurring costs will the hire need on day one?
- Which outcomes must the hire deliver in the first 6 months and first 12 months?

Finance approval is required before the role opens because hiring creates more than salary cost. A new Sales hire may need Salesforce, ZoomInfo, Webex, Slack, Notion, Okta, and equipment. A Customer Success hire may need Salesforce, Webex, SupportDesk, Slack, Notion, Okta, and customer-facing enablement. An Engineering hire may need GitHub, Jira, Slack, Notion, Okta, and possibly AWS ReadOnly or Datadog ReadOnly access. New paid seats, license expansions, equipment above USD 1,500, or recurring spend above USD 500 per month or USD 2,500 per year require Finance review through [billing review](https://billing.novaops.example). Tom Baker is the Finance Controller for spend-threshold review.

Managers should not split a role into small contractor requests to avoid headcount review. If the need is ongoing, core to the team, managed like a regular employee, or expected to convert quickly into permanent capacity, involve People Operations before deciding whether the right path is employee hiring or contractor engagement.

## Role Scorecards

Managers should write a role scorecard before interviews. The scorecard should explain the outcomes expected in the first 6 and 12 months, the skills required on day one, the skills that can be learned, and the behaviors that would make someone successful at NovaOps.

A useful scorecard is practical enough that interviewers can evaluate evidence against it. It should include:

- Mission: why the role exists and which team goal it supports.
- Scope: which customers, systems, services, accounts, or workflows the person will own.
- First 6 months: the outcomes expected after onboarding and normal ramp.
- First 12 months: the durable impact expected after the person is fully operating.
- Required skills: capabilities the person must already have on day one.
- Learnable skills: NovaOps-specific tools, product context, or process knowledge that can be learned after joining.
- Behavioral expectations: collaboration, judgment, customer care, documentation, escalation, and operating discipline.
- Decision rights: which decisions the role can make independently and which require manager, IT, Finance, or People Operations approval.
- Systems and access: the least-privilege system list the role is likely to need.
- Location and schedule: required country, time-zone overlap, travel expectations, remote or hybrid assumptions, and any customer-hour constraints.

Do not write a scorecard that is just a wish list. If every skill is marked required, the team will confuse preference with necessity and may screen out candidates who could succeed. If no outcomes are defined, the panel will over-index on charisma, familiarity, or interview polish.

## Location and Remote Constraints

NovaOps is hybrid and remote-first, with employees in Israel, Germany, the United Kingdom, and the United States. Remote-first does not mean hire-anywhere. Employment rules, payroll, benefits, tax, equipment shipping, data access, customer coverage, and time-zone overlap all matter.

Before opening a role, the manager must state the approved location assumption. Examples include:

- United States only because the Sales role needs close overlap with U.S. prospects and Liam Oconnor's Sales team.
- Israel or United Kingdom because the Customer Success role needs overlap with Yael Romano's team and EMEA customer calls.
- Germany, Israel, or United Kingdom because an Engineering role needs overlap with Product, Jira planning, and release reviews.

If a strong candidate is outside the approved location, do not make a verbal exception. Ask People Operations and Finance whether the company can employ or contract in that country, whether a different compensation range applies, whether equipment can be shipped, and whether the time-zone overlap still supports the role. A manager may say, "The role is currently approved for the United Kingdom," but should not say, "We can make any country work."

Remote roles still need working norms. The scorecard should name expected overlap windows, customer meeting expectations, travel assumptions, and whether the person must occasionally attend local office, customer, or team events. For customer-facing roles, include Webex availability and customer time zones. For Engineering, include on-call, release, incident, and design-review expectations if they apply.

## Employee Versus Contractor

Employee hiring and contractor engagement are different decisions. Use People Operations early if you are unsure which model fits.

An employee role is appropriate when NovaOps needs ongoing capacity, expects the person to own a durable part of the operating model, provides regular management and performance review, or needs the person integrated into long-term team planning. Employees go through the normal offer, onboarding, BambooHR, compensation, benefits, review, and promotion processes.

A contractor role is appropriate for bounded work with a defined scope, expected end date, limited systems access, and a clear deliverable. Contractor paperwork and classification require People Operations review. Sara Cohen handles contractor paperwork, and cross-border contractor records need HR review in Deel. Contractor access must have an end date and should use the narrowest practical permissions.

Contractors should not receive broad default employee access. Engineering contractors such as Priya Raman or Alex Kim may need GitHub Limited, Jira, Slack Guest, Okta, Notion Guest, or Datadog ReadOnly depending on the approved work. GitHub access for any contractor requires manager and IT approval with a defined end date. Do not ask IT to grant GitHub organization admin, AWS admin, or unrestricted Notion access for a contractor unless the work has been separately approved as high-risk and the access path has been reviewed.

If a contractor's scope grows, treat that as a change request. Re-confirm the statement of work, end date, budget, manager, and access. Do not quietly turn a contractor into an indefinite employee-equivalent arrangement through Slack assignments and recurring meetings.

## Structured Interviews

A good interview process is structured and respectful. Use the same core questions for candidates in the same role, take notes, and evaluate evidence against the scorecard. Do not ask questions about protected characteristics, family plans, medical history, national origin beyond work authorization requirements, age, religion, or other irrelevant personal information.

Every interview should have an assigned purpose. A panel that repeats the same friendly conversation four times is not structured. A panel that maps interviewers to competencies can make a fairer decision with fewer candidate hours.

For each role, People Operations and the hiring manager should confirm:

- Screening criteria used before the first interview.
- Interview stages and expected duration.
- Which competency each interviewer owns.
- Core questions or exercises for each stage.
- Evaluation rubric, usually tied to the scorecard.
- Who collects feedback and by when.
- What evidence would justify an additional interview.

Use consistent rubrics. A simple four-point scale is enough if it is tied to behavior: exceeds the scorecard, meets the scorecard, partially meets the scorecard, or does not meet the scorecard. Interviewers should explain their rating with evidence, not labels. "Gave a clear rollback plan for a failed migration" is useful. "Seems senior" is too vague. "Asked good discovery questions before pitching" is useful. "Good culture fit" is too vague.

Work samples should resemble the job without requiring unpaid production work. A Sales role play can test discovery, qualification, and Salesforce discipline. An Engineering exercise can test coding, system design, debugging, review habits, or product judgment. A Customer Success simulation can test customer communication, prioritization, renewal risk judgment, and escalation.

Include interviewers who can assess different parts of the role. For Engineering, that may include coding, system design, collaboration, and product judgment. For Customer Success, that may include customer communication, prioritization, Salesforce discipline, and escalation judgment. For Sales, that may include prospecting judgment, discovery, pipeline hygiene, territory planning, and handoff quality.

## Interview Notes and Candidate Privacy

Interview notes are company records. Keep them factual, job-related, and stored only in the approved recruiting workflow. Do not keep shadow candidate files in personal documents, private Slack messages, Jira tickets, GitHub issues, customer notes, or local spreadsheets.

Good notes capture evidence:

- What question or exercise was asked.
- What the candidate did or said that relates to the scorecard.
- Which requirement the evidence supports or weakens.
- What follow-up, if any, is needed.

Poor notes capture personal impressions that cannot be fairly evaluated. Avoid comments about appearance, accent, age, family status, health, disability, national origin, religion, personal finances, neighborhood, school prestige unless directly relevant to a stated requirement, or whether the candidate reminds the interviewer of someone else.

Candidate information should be shared only with people who need it for the hiring decision. Do not paste resumes, compensation expectations, interview notes, portfolio links, or take-home work into broad Slack channels or Notion pages. If an interviewer needs context, share it through the approved workflow or a restricted hiring document. If a candidate asks about privacy, route the question to People Operations.

Managers should not promise confidentiality beyond the hiring process. Candidate feedback is visible to appropriate hiring stakeholders, People Operations, and approvers. If a candidate discloses a need for accommodation, immigration support, protected leave, or another sensitive topic, pause and involve People Operations instead of trying to solve it in the interview.

## Department Examples

### Sales

A Sales hire should be approved with Liam Oconnor or the relevant Sales leader, People Operations, and Finance before sourcing begins. The scorecard should name the sales motion, territory or segment, expected pipeline contribution, Salesforce hygiene, prospecting expectations, customer handoff quality, and first 6-month outcomes.

For a Sales Development Representative, the first 6 months may include building qualified pipeline, documenting outreach in Salesforce, using ZoomInfo within approved prospecting rules, joining Webex calls when appropriate, and handing clean context to Account Executives. The interview plan might include a recruiter screen, hiring manager interview, prospecting exercise, discovery role play, and cross-functional interview with Customer Success or Sales Operations.

Sales interview evidence should include how the candidate qualifies accounts, handles rejection, writes concise follow-up, keeps Salesforce current, and escalates unusual customer or data concerns. Do not hire a candidate only because they have an impressive network if the role requires disciplined pipeline work and accurate records.

IT implications for Sales hiring usually include Okta, Slack, Notion, Salesforce, ZoomInfo, and Webex. Salesforce access is restricted to Sales and Customer Success. ZoomInfo usage is limited to Sales prospecting. If adding the hire exceeds license counts or spend thresholds, involve Finance before the start date.

### Engineering

An Engineering hire should be approved with the Engineering leader, People Operations, Finance, and IT when the role requires sensitive systems. The scorecard should name the product area, service ownership, delivery expectations, code review norms, operational judgment, documentation expectations, and first 6-month outcomes.

For a Backend Engineer, the first 6 months may include shipping scoped Jira work, writing clear GitHub pull requests, participating in design review, improving reliability, and learning NovaOps production boundaries. The interview plan might include a technical screen, coding or debugging exercise, system design interview, collaboration interview, and product judgment conversation.

Engineering interview evidence should include how the candidate explains tradeoffs, tests changes, handles review feedback, plans migrations, reasons about incidents, and documents operational risk. Avoid over-weighting puzzle performance if the job mostly requires maintainable code, clear review habits, and careful production judgment.

IT implications for Engineering hiring usually include Okta, Slack, Notion, Jira, GitHub, and role-specific access such as AWS ReadOnly or Datadog ReadOnly. AWS admin, GitHub organization admin, Datadog admin, and Okta admin access require extra review. A manager's request confirms business need; IT decides whether the access pattern is safe.

### Customer Success

A Customer Success hire should be approved with Yael Romano or the relevant CS leader, People Operations, and Finance before the role opens. The scorecard should name the account segment, customer outcomes, renewal or adoption expectations, escalation ownership, Salesforce discipline, SupportDesk usage, and Webex customer communication.

For a Customer Success Manager, the first 6 months may include taking ownership of a defined book of accounts, documenting account health in Salesforce, handling customer meetings on Webex, coordinating SupportDesk escalations, and identifying renewal risks early. The interview plan might include a hiring manager interview, customer scenario, prioritization exercise, stakeholder interview, and values-and-judgment conversation tied to the scorecard.

Customer Success interview evidence should include how the candidate communicates under pressure, distinguishes urgent from important, writes customer follow-up, updates Salesforce, uses SupportDesk context, and escalates risk without creating panic. Do not treat warmth alone as sufficient if the role requires structured account management and disciplined follow-through.

IT implications for Customer Success hiring usually include Okta, Slack, Notion, Salesforce, Webex, and SupportDesk. Webex seat limits and Salesforce access should be checked before the start date. Customer-facing access should be ready early enough for shadow calls during onboarding, but broad access should not be requested just in case.

## Decision and Offer

After interviews, the hiring manager leads a decision meeting. Discuss evidence, not vibes. If the panel disagrees, identify which requirement is uncertain and whether another interview would produce useful evidence. Do not keep interviewing because a manager is avoiding a decision.

The decision meeting should compare the candidate to the scorecard, not to an imagined perfect person. Ask:

- Which required outcomes does the evidence support?
- Which required skills are missing or uncertain?
- Which learnable gaps can onboarding reasonably cover?
- What risks would the manager need to manage in the first 90 days?
- Is the level aligned with the approved compensation range?
- Does the location and employment type match the approved role?
- Are there IT, Finance, or People Operations blockers before an offer?

If the candidate is strong but not aligned to the approved role, do not improvise a new offer. A higher level, different location, contractor conversion, special equipment commitment, or compensation change requires renewed approval. If the candidate would fit a future role, record that clearly and close the current decision cleanly.

People Operations prepares the offer. Finance must approve compensation before the offer is extended. Managers may sell the role and answer job questions, but should not negotiate outside the approved range or promise promotion timing. Managers also must not promise immigration outcomes, benefits exceptions, unusual remote arrangements, contractor conversion, equity treatment, severance, or future compensation changes without the appropriate approver.

The hiring manager can help the candidate understand the work: team goals, manager style, first 90 days, tools, customer context, engineering practices, remote norms, and what success looks like. Keep that conversation honest. Overselling the role creates onboarding and retention problems later.

## Onboarding Starts Before Acceptance

A hiring decision creates an onboarding obligation. Before the start date, the manager should draft the first 30 days, identify a buddy, request systems through IT, and prepare useful first-week work. See [onboarding](onboarding.md).

Start onboarding planning as soon as the offer is likely, not after the employee is already waiting for a laptop. The manager should prepare:

- A 30-day onboarding plan with role outcomes, first meetings, first systems, and first useful work.
- A 60-day and 90-day outline if the role has complex ramp expectations.
- A buddy or peer contact who can answer practical questions.
- Required IT requests with business need, start date, manager approval, and least-privilege access.
- Equipment and location details, including shipping constraints for remote employees.
- License or spend requests that need Finance review.
- Customer, code, account, or project context the person should read in the first week.

IT onboarding is not a formality. The hiring manager should request only the access the role requires. Use Okta, Slack, Webex, Jira, GitHub, Salesforce, BambooHR, SupportDesk, ZoomInfo, Notion, Datadog, or AWS only as the role requires. Do not request broad access just in case.

Timing matters. A new Customer Success Manager who cannot access Salesforce, Webex, or SupportDesk cannot shadow effectively. A new Backend Engineer without GitHub and Jira cannot contribute to code review or scoped tickets. A new Sales Development Representative without Salesforce and ZoomInfo cannot practice the workflow they were hired to perform. If access is delayed, adjust onboarding expectations instead of treating the new hire as slow.

## Quick Reference Facts

Hiring at NovaOps requires approved headcount before recruiting starts.

The department leader and Finance approve headcount, compensation range, location assumptions, and employment type.

People Operations confirms the hiring process and opens the role in the approved workflow.

Managers must write a role scorecard before interviews.

The role scorecard should include first 6-month outcomes, first 12-month outcomes, day-one skills, learnable skills, success behaviors, location assumptions, and systems access needs.

NovaOps is hybrid and remote-first, but employee hiring is normally planned around Israel, Germany, the United Kingdom, and the United States.

A candidate outside the approved location requires People Operations and Finance review before the manager makes commitments.

Contractors require defined scope, end date, manager, budget, and limited access.

GitHub access for contractors requires manager and IT approval with a defined end date.

Structured interviews use the same core questions for candidates in the same role.

Interviewers should evaluate evidence against the scorecard and avoid protected or irrelevant personal topics.

Interview notes should be factual, job-related, and stored only in the approved recruiting workflow.

Candidate resumes, notes, compensation expectations, and work samples should not be shared in broad Slack channels, Jira tickets, GitHub issues, or customer systems.

Finance must approve compensation before an offer is extended.

People Operations prepares the offer.

Managers may sell the role and answer job questions, but may not negotiate outside the approved range or promise promotion timing.

Onboarding planning begins before the start date and includes a 30-day plan, buddy, IT access requests, equipment, and first-week useful work.
