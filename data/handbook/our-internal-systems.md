---
last_updated: 2025-11-02
corpus: handbook
audience: all
---

# Our Internal Systems

## System Map

NovaOps uses a small core stack. Okta is the front door for SSO and MFA. Slack is for quick coordination. Jira tracks planned work and cross-team delivery. GitHub stores source code and engineering review. BambooHR is HR self-service and employee records. Webex is for video meetings. Salesforce is the CRM for Sales and Customer Success. AWS hosts approved production and internal cloud resources.

Internal service entry points use NovaOps domains: [Okta](https://okta.novaops.example), [Slack launch](https://slack.novaops.example), [Jira](https://jira.novaops.example), [GitHub](https://github.novaops.example), [BambooHR](https://bamboohr.novaops.example), [Webex](https://webex.novaops.example), [Salesforce](https://salesforce.novaops.example), [AWS access](https://aws.novaops.example), [system status](https://status.novaops.example), and [billing review](https://billing.novaops.example).

## Access Requests

Access starts with role need. Your manager confirms the business reason. IT confirms the security and license impact. Finance reviews requests that create new paid spend above USD 500 per month or USD 2,500 per year. Submit requests through [the IT request portal](https://it.novaops.example).

Standard access is provisioned during onboarding. Privileged access is different: AWS admin, GitHub organization admin, Okta admin, Salesforce admin, and BambooHR administrator rights require manager approval, IT approval, and a named end date or review date. Contractor GitHub access requires explicit manager and IT approval even when the contractor is already in Jira or Slack.

For ordinary employee requests, the request should include the system name, the business reason, the expected duration, and whether customer, employee, source-code, or billing data will be visible. A request that says "same as Rachel" is not enough, because NovaOps has duplicate first names and similar roles. Use full names and email addresses when referring to access examples, such as rachel.green@novaops.example for Sales or rachel.stein@novaops.example for Customer Success.

IT may approve a narrower access level than the one requested. For example, an engineer who asks for AWS Admin may receive AWS ReadOnly while Omar Weiss confirms the production need. A Product Manager who asks for Salesforce export rights may receive view access only if the request is for customer context rather than account operations. Managers should explain the work need, not prescribe the permission bit unless they own the system.

Requests that create extra license cost are not automatically urgent. Webex is the common example: the contract has been tight enough that customer-facing roles take priority when seats are limited. If a Webex request is blocked by seat availability, the requester should still be able to use Slack, Jira, and written customer notes while IT and Finance decide whether to reclaim or expand seats.

## Department Rules

Salesforce is limited to Sales, Customer Success, and approved operational support roles. GitHub is limited to Engineering, QA, Product roles that need code visibility, and approved contractors. BambooHR employee self-service is available to all employees, but HR records beyond your own profile are limited to People Operations. AWS access is granted by least privilege; read-only access is still reviewed.

Slack guest accounts must have a business owner and an expiration date. Webex licenses are assigned by role need; customer-facing roles have priority when license seats are tight.

Jira is broadly available to Product, Engineering, QA, Customer Success, and operations roles that participate in delivery work. Project administrator rights are restricted because they can silently over-grant access to boards, automation rules, and customer-related issue fields. If you need a Jira project role changed, ask the project owner first and then submit the IT request with the project key.

GitHub access is more sensitive than Jira access. Full-time engineers normally receive organization membership during onboarding. Contractors such as priya.raman.contractor@novaops.example and alex.kim.contractor@novaops.example receive limited GitHub access only after manager approval, IT approval, repository scope review, and a defined end date. Contractors should not be added to broad teams just to make one repository visible.

BambooHR has two very different access models. Employee self-service lets you see and update your own details, request time off, and view HR tasks assigned to you. HR access lets a user view sensitive employment records, and is limited to People Operations roles such as Sara Ben-David, Sara Cohen, and Maya Rosen. A manager who needs an employment document should ask People Operations for the specific workflow rather than requesting broad BambooHR access.

Salesforce access follows customer responsibility. Account Executives, Sales Operations, Customer Success Managers, Customer Success Specialists, and approved leaders may receive Salesforce roles. Engineering and Product usually receive customer context through Jira, SupportDesk, or curated notes, not direct Salesforce access. Export permissions are restricted and may require a data handling review.

AWS is approved by least privilege and reviewed more often than collaboration tools. AWS ReadOnly still exposes operational details, customer identifiers, infrastructure names, and cost signals. AWS Admin requires manager approval, IT approval, and a review date. Production break-glass access is time-boxed and should be removed when the incident or maintenance task ends.

## Known Messy Cases

The source of truth is not always perfectly clean. If a system record and a manager note disagree, use the workflow owner to resolve it rather than guessing. Noam Sharon moved from Customer Success to Product, and some records may still show an older Customer Success manager. Access for Noam should be based on the current Product role and the current approval chain, not stale manager data.

Some system owners in the operational database are intentionally imperfect. Figma ownership may appear as Engineering even though Product Design uses it heavily. SupportDesk may appear under IT even though Customer Success uses agent seats. These mismatches are not permission to bypass review. They are signs that the request should name the business owner, system owner, and approver separately.

Duplicate names require extra care. NovaOps has Maya Cohen and Maya Rosen, Sara Ben-David and Sara Cohen, Rachel Green and Rachel Stein, and two Daniels. Access requests, HR questions, and ticket comments should use full names and email addresses. IT will return a request that identifies only "Daniel" or "Rachel" when the requested system contains confidential or restricted data.

Guests and contractors are another common source of drift. Slack guest accounts must have a business owner and an expiration date. Notion guests should be limited to the pages they need. Jira access for contractors should match the project scope. GitHub access for contractors must be reviewed separately even if Slack and Jira are already approved.

## Reviews and Removal

Access reviews happen quarterly for restricted systems and twice per year for internal systems. IT leads the review for Okta, Slack, Webex, GitHub, Jira, AWS, and device tooling. People Operations leads the review for BambooHR. Sales Operations and Customer Success leaders help review Salesforce. Finance reviews billing-facing systems and paid license growth.

Managers are expected to respond to access review questions within five business days. If a manager does not respond, IT may remove the access or downgrade it to a safer role. This is not a punishment; stale access is a security and cost risk.

When someone changes roles, the old access should be removed before new access is added unless there is a documented transition period. A Sales employee moving to Product should not keep Salesforce export permissions by default. A contractor whose statement of work ends should lose GitHub, Jira, Slack guest, and related system access on the end date unless a renewed agreement is already in place.

## Security Expectations

Do not share accounts, API keys, passwords, MFA codes, or exported customer data. Use Okta for login whenever available. If a system is not in Okta, ask IT before creating a new account. New systems or paid tools require approval before company data is added.

For more on equipment and device security, see [managing work devices](managing-work-devices.md).

If you receive access by mistake, report it instead of using it. If you can see another employee's HR record, a customer export you do not need, a GitHub repository outside your project, or an AWS account you do not recognize, open an IT ticket and notify your manager. Accidental access does not create authorization.

New tools must not be adopted with company data simply because they are free. Free trials can still create data retention, customer confidentiality, and security review obligations. If a team wants a new tool, submit the business reason, data type, expected users, cost after trial, and whether Okta SSO is available. Finance will review cost thresholds; IT will review security; the department leader will decide whether the tool should become part of the standard stack.
