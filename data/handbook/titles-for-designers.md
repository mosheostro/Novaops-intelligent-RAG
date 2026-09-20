---
last_updated: 2025-06-05
corpus: handbook
audience: all
---

# Titles for Designers

## Design at NovaOps

Designers at NovaOps shape how customers build, monitor, and improve workflow automation. Good design here is not decoration after requirements are finished. It is product judgment, systems thinking, customer empathy, and the ability to make complex operations feel understandable.

Design titles measure scope and influence. A designer can grow by becoming a stronger individual contributor, by leading larger product areas, or eventually by managing people. Management is not required for senior design impact.

Design sits in Product and works daily with Product Management, Engineering, QA, Customer Success, Support, Sales, and Operations. The same ladder applies to product design, interaction design, UX design, design systems work, and research-heavy product design. Some designers may spend most of a cycle on customer workflow mapping, while others spend more time on Figma components, Jira acceptance criteria, or launch validation. The title is based on scope, judgment, and durable impact, not on which tool was open most often.

NovaOps is a hybrid and remote-first company, so design work must survive async review. A strong designer leaves enough context that a teammate in another location can understand the customer problem, the chosen tradeoff, the known risks, and what Engineering should build next. This does not mean every decision needs a long document. It means the important design reasoning is findable in the right place.

## Tools and Working Surfaces

Product designers usually work in Figma, Miro, Jira, Slack, Notion, Okta, and approved customer research spaces. Jira is the shared execution record for Product, Engineering, QA, and release planning. Figma is the source of truth for design artifacts, prototypes, component variants, and annotated flows. Notion is used for durable context such as research summaries, decision memos, glossary entries, and pattern guidance.

Figma contains internal product and workflow information, so designers should keep sharing narrow. Guest access, contractor access, and seat expansion must follow the approval rules in [our internal systems](our-internal-systems.md). A designer may invite a customer to a moderated prototype only when the file is scoped for that session, sensitive data has been removed, and the Product Manager or manager has approved the research plan.

Designers do not need to be Jira administrators to do strong work. They do need to make sure design intent is visible where Engineering and QA are already working. A Figma link in a Jira ticket is not enough by itself if the ticket does not name the scenario, acceptance criteria, unresolved questions, and launch risks.

## Levels

### D1, Associate Product Designer

A D1 works on well-scoped tasks, learns the product and customer domain, and produces usable flows with close guidance. A D1 should show curiosity, craft care, and willingness to test assumptions.

Expected scope: A D1 usually works inside an existing pattern, feature, or workflow step. Examples include refining an empty state for a failed automation run, designing a confirmation dialog for a schedule change, improving the wording of a permission error, or adding a variant to an existing component. The work should have a clear owner, clear review path, and limited product risk.

Customer and workflow understanding: A D1 should learn the vocabulary of workflow automation, including triggers, actions, branches, approvals, retries, audit logs, permissions, integrations, and run history. They are not expected to define a whole automation model alone. They are expected to ask what the user is trying to accomplish, what could go wrong, and how the UI should behave when the workflow has no data, invalid data, partial data, or a permission conflict.

Product and Engineering collaboration: A D1 should bring questions early instead of waiting for a polished mock. They should be able to explain a simple design choice to a Product Manager, ask Engineering whether a state is technically possible, and update their Figma file when feedback changes the direction. They should learn how QA reads design artifacts and should include enough state coverage that QA does not have to guess.

Figma and Jira handoff: A D1 handoff should include current screens, changed screens, basic interaction notes, empty states, loading states, error states, and responsive behavior when relevant. In Jira, a D1 should link to the correct Figma frame or page, state whether the design is ready for build, and call out any open question. They should not leave engineers to infer final copy from old comments or abandoned frames.

Accessibility: A D1 should apply known accessibility basics with review. This includes visible focus states, clear labels, keyboard reachable controls, readable contrast, non-color-only status indicators, sensible tab order, and error copy that explains how to recover. If the pattern is uncertain, the D1 should ask for review rather than silently copying an inaccessible pattern.

Research and validation: A D1 may help prepare prototypes, take notes in moderated sessions, summarize usability issues, or compare a design against support tickets. A good D1 distinguishes what was observed from what they assume. For example, "two users missed the retry control in the run detail page" is stronger than "the page is confusing."

Design systems: A D1 should use existing components before creating new ones. When a component does not fit, they should document the gap and ask whether the need is local or reusable. A D1 is not expected to own design system strategy, but they are expected to avoid one-off styling that makes the product harder to maintain.

Promotion signal toward D2: D1 evidence often shows improving independence. Strong examples include taking a small workflow state from vague request to usable design, catching an accessibility issue before build, preparing a clean Jira handoff, or showing that a proposed UI created confusion in a quick test and then fixing it.

### D2, Product Designer

A D2 owns design for features or small product areas. A D2 can gather context, create options, partner with Product and Engineering, and deliver clear interaction specs without needing every step assigned.

Expected scope: A D2 can own a bounded feature from discovery through release. Examples include designing the workflow template picker, a role-based approval step, a retry configuration panel, a new run-history filter, or a dashboard section for failed automations. The feature may touch several screens, but the boundaries should be known and the business goal should be clear.

Customer and workflow understanding: A D2 should model the user's job, not only the screen. Before designing an approval workflow, for example, they should know who requests approval, who approves, what happens when the approver is unavailable, whether the system records an audit trail, and how the customer recovers from a rejected or expired step. They should identify the primary path and the edge paths that matter most.

Product and Engineering collaboration: A D2 should work with Product to define the problem, success metric, and release slice. They should work with Engineering to understand technical constraints early enough to shape the design. A D2 is expected to present options, name tradeoffs, and recommend a direction. When Engineering says a design is expensive, a D2 should be able to explore alternatives without reducing the user experience to the easiest implementation.

Figma and Jira handoff: A D2 should maintain a clear Figma page structure for the project, label current designs, archive outdated explorations, and mark which flows are ready for Engineering. Jira tickets should include design links, acceptance criteria, state coverage, copy source, analytics or event needs when relevant, and known dependencies. If scope changes, the D2 should update both the design artifact and the ticket conversation.

Accessibility: A D2 should design accessible interactions without needing basic reminders. For workflow automation, this includes keyboard operation for builders and tables, status text that does not rely on color alone, clear focus behavior in side panels, accessible names for icon-only actions, and error summaries for multi-step forms. If a design uses drag and drop, the D2 should provide an alternate keyboard or list-based path.

Research and validation: A D2 can plan lightweight research for a feature. This might include reviewing support cases, interviewing internal Support or Customer Success teammates, testing a prototype with three to five target users, or comparing behavior before and after release. They should explain the limits of the evidence. A small usability test can reveal problems, but it does not prove a market-wide conclusion.

Design systems: A D2 should contribute variants, usage notes, or component bug reports when feature work exposes a pattern gap. They should coordinate with the design systems owner before creating new components. If a one-off pattern is necessary, the D2 should say why and set a review point so it does not become an accidental standard.

Promotion signal toward D3: D2 evidence should show reliable ownership of a product problem, not only attractive screens. Strong examples include shipping a feature that reduced workflow setup errors, using research to simplify a confusing automation step, defining complete state coverage for Engineering and QA, or creating a reusable pattern that other designers adopted.

### D3, Senior Product Designer

A D3 leads ambiguous projects, frames customer problems, identifies tradeoffs, and raises the quality of product decisions. A D3 brings research, workflow modeling, and design systems thinking into planning rather than waiting for a ticket.

Expected scope: A D3 can own a complex feature, a product area, or a cross-functional initiative where the solution is not obvious. Examples include redesigning automation run diagnostics, reworking the workflow builder's branching model, improving onboarding for customers migrating from manual processes, or creating a permissions experience that balances self-service with admin control.

Customer and workflow understanding: A D3 should be able to map end-to-end workflows across roles. In NovaOps terms, that might mean the person who creates an automation, the manager who approves it, the admin who controls integration access, the teammate who receives the notification, and the Support agent who helps when it fails. A D3 should expose hidden complexity and then decide which complexity the product should absorb.

Product and Engineering collaboration: A D3 is expected to improve the quality of planning. They should help Product decide whether a project is solving the right customer problem, help Engineering sequence work around technical risk, and help QA identify the states that need release confidence. A D3 should be comfortable saying that a requested feature is premature, too narrow, or solving a symptom rather than a workflow problem.

Figma and Jira handoff: A D3 should create design artifacts that support parallel work. This may include service diagrams, state matrices, permission tables, migration notes, interaction prototypes, and staged release plans. Jira handoff at this level should make dependencies and decision history visible. If implementation needs to be split across tickets, the D3 should help define slices that remain coherent for the user.

Accessibility: A D3 should design for accessibility as part of product quality, not a late checklist. They should identify patterns that create systemic barriers, such as canvas-only workflow editing, small hit targets in dense tables, status colors without labels, or keyboard traps in nested panels. A D3 should work with Engineering to choose accessible primitives and with QA to define accessibility checks for the release.

Research and validation: A D3 can select the right research method for ambiguity. They may combine customer interviews, task analysis, prototype testing, product usage data, Support patterns, sales call notes, and post-launch behavior. They should know when more research is needed and when the team has enough signal to make a reversible decision. They should turn research into product choices, not just a slide deck.

Design systems: A D3 should think in patterns. If three product areas solve approvals differently, the D3 should identify whether the differences are legitimate or accidental. They should help the design systems owner define reusable patterns for forms, tables, status indicators, modals, side panels, audit trails, and workflow nodes. Their design work should reduce future design and engineering rework.

Promotion signal toward D4: D3 evidence should show impact beyond a single feature. Strong examples include reframing a roadmap item around a clearer customer job, creating a workflow model that aligned Product and Engineering, preventing an expensive build through early validation, improving a design system pattern used by multiple teams, or mentoring another designer through a complex project.

### D4, Staff Product Designer

A D4 works across teams, shapes product direction, and creates reusable patterns that reduce design and engineering rework. A D4 is expected to influence roadmaps and mentor designers without taking over their work.

Expected scope: A D4 leads design across a major product area or multiple teams. Examples include establishing the design direction for workflow automation authoring, creating a shared model for integrations and permissions, coordinating a cross-team redesign of monitoring and alerting, or defining how NovaOps should handle human approvals across the product. The D4 is accountable for the coherence of the customer experience, even when individual tickets are owned by others.

Customer and workflow understanding: A D4 should understand customer operations at a system level. They should be able to compare different customer segments, identify which workflows are common enough to standardize, and know where local customization is necessary. A D4 should recognize when a design pattern that works for a small team breaks down for an enterprise admin, a distributed support team, or a customer with strict audit needs.

Product and Engineering collaboration: A D4 should influence roadmap quality before projects are committed. They should bring product strategy, research, technical feasibility, and customer evidence into the same conversation. They are expected to challenge vague initiatives, clarify sequencing, and help leaders choose between competing bets. A D4 does not need authority over Engineering to influence Engineering decisions; they earn influence by making tradeoffs clearer.

Figma and Jira handoff: A D4 should establish handoff norms that make multiple teams faster. This may include standard Figma page structures, decision logs, Jira design-readiness criteria, accessibility annotation conventions, component contribution rules, or templates for state matrices and permission tables. They should not personally clean up every file. Their job is to create practices that other designers and engineers can use.

Accessibility: A D4 should address accessibility across patterns and systems. They may sponsor improvements to keyboard navigation in the workflow builder, define a status-language standard, align table behavior across product areas, or make sure new design system components include accessible states before adoption. A D4 should also help leaders understand accessibility risk when schedule pressure rises.

Research and validation: A D4 should build a research agenda for a product area. They should connect customer discovery, roadmap planning, release validation, and post-launch learning. They may coach designers on research quality, identify unanswered customer questions, and make sure the company does not confuse internal opinion with customer evidence.

Design systems: A D4 may be the design systems owner or a senior contributor to the system. At this level, design systems work includes governance, adoption, contribution paths, quality standards, documentation, and coordination with frontend architecture. A D4 should know when a component should be generalized and when premature generalization would slow the team.

Promotion signal toward D5: D4 evidence should show cross-team leverage and durable direction. Strong examples include a product-area strategy that changed roadmap choices, a design system investment that reduced repeated engineering work, a research program that changed company understanding of customer workflows, or mentoring that raised the quality of multiple designers' work.

### D5, Principal Designer

A D5 sets design strategy for major product bets and represents the customer experience at the company level. This title requires repeated evidence of broad, durable impact.

Expected scope: A D5 works on company-level product experience, not just a large personal project. Examples include setting the long-term design strategy for NovaOps workflow automation, defining the experience principles for AI-assisted operations, shaping the platform model for permissions and auditability, or leading design strategy for a major enterprise expansion. The work may span Product, Engineering, Customer Success, Sales, Support, IT, and leadership.

Customer and workflow understanding: A D5 should understand the patterns beneath individual customer requests. They should be able to explain how workflow automation changes accountability, trust, approval behavior, operational risk, and customer adoption. A D5 should help the company see where product complexity is necessary and where it is a sign that the product strategy is unclear.

Product and Engineering collaboration: A D5 is expected to influence executive and department-level decisions. They should bring design judgment into company bets before requirements are frozen. They should help Product understand customer behavior, help Engineering understand experience risk, and help leaders choose a coherent direction when different teams optimize for different local goals.

Figma and Jira handoff: A D5 is usually not the person writing every ticket, but their strategy must still become buildable. They should ensure that major design bets are translated into principles, patterns, milestones, governance, and decision rights. If teams cannot tell how a strategic direction changes their Jira work, the D5 has not finished the job.

Accessibility: A D5 should treat accessibility as part of NovaOps' product promise. They should identify where company-level bets could exclude users, increase operational risk, or create inaccessible dependencies. They should make sure accessibility standards are included in product strategy, design systems, and launch criteria, not delegated only to late QA checks.

Research and validation: A D5 should shape how NovaOps learns. They may sponsor strategic research, synthesize evidence across teams, identify blind spots in customer understanding, and decide which assumptions deserve investment. They should be clear about confidence levels. A principal designer can make bold recommendations, but they should not present speculation as evidence.

Design systems: A D5 should use design systems as strategic leverage. This may mean defining a coherent product language across automation authoring, monitoring, approvals, billing-sensitive actions, and administrative controls. It may also mean deciding what should not be systematized yet because the product direction is still changing.

Evidence at D5: D5 promotion or calibration requires repeated proof that the designer improved company-level outcomes. Strong evidence includes design strategy that shaped major product bets, durable patterns adopted across teams, measurable improvement in customer success or product comprehension, clearer executive decision-making, and a track record of making other senior leaders and designers more effective.

## Workflow Automation Design Examples

Workflow automation design at NovaOps often involves more than drawing a happy path. Designers should consider who starts the workflow, what data is required, what systems are involved, what permissions apply, how failures appear, and how a customer knows the automation can be trusted.

Common examples include:

- Automation setup: A customer creates a workflow from a template, changes trigger conditions, maps fields, and decides whether the workflow runs immediately or waits for approval.
- Human approval: A request routes to a manager or admin, handles delegation when the approver is unavailable, records the decision, and tells the requester what changed.
- Failure recovery: A run fails because an integration token expired, a required field is missing, or an external system rejects a request. The design should explain the failure, identify who can fix it, and provide a safe retry path.
- Audit and compliance: A customer needs to know who changed a workflow, when it changed, what ran, and whether sensitive actions were approved. The design should preserve trust without burying the user in logs.
- Monitoring: A team needs to see which automations are healthy, which are noisy, which are paused, and which failures matter. The design should help users prioritize action rather than create another dashboard nobody reads.
- Permissions: An admin may allow one team to build workflows but restrict production activation, integration credentials, billing-sensitive actions, or customer-data export. The design should make restrictions understandable without exposing unnecessary internal implementation.

At D1 and D2, these examples usually appear as feature-specific design details. At D3, they become workflow models and tradeoff decisions. At D4 and D5, they become product-area patterns and company-level design strategy.

## Product and Engineering Collaboration

Product, Design, and Engineering share responsibility for product quality. Product usually owns business priority, customer problem framing, and launch goals. Design owns the customer experience, interaction model, research quality, and design tradeoffs. Engineering owns technical architecture, implementation quality, reliability, security, and operational feasibility. In healthy work, these responsibilities overlap enough for good debate but remain clear enough for decisions.

Designers should involve Product and Engineering early when a project affects workflow logic, data models, permissions, integrations, automation reliability, customer migration, or release sequencing. A designer should not wait until the final mock to learn that the workflow engine cannot support a proposed branch condition. Engineering should not wait until implementation to ask what happens when a run has partial failure. Product should not wait until launch to decide what success means.

Good collaboration artifacts include:

- A problem statement that names the customer job and the business goal.
- A workflow map showing roles, triggers, actions, approvals, failure modes, and recovery paths.
- A design option comparison that explains tradeoffs, not only preference.
- A risk list that separates user risk, technical risk, privacy or security risk, release risk, and support risk.
- A decision log that records why a direction was chosen and what was rejected.
- A release slice that is small enough to build but still valuable and coherent for customers.

Designers should disagree clearly and constructively. If a Product Manager asks for a shortcut that would create customer confusion, the designer should explain the risk and offer alternatives. If Engineering identifies a costly interaction, the designer should understand the constraint and explore simpler paths. If QA finds a missing state, the designer should update the model and handoff. Senior designers are expected to make this kind of collaboration easier for everyone around them.

## Figma and Jira Handoff

A good handoff helps Engineering and QA build the intended experience without turning design into a mystery hunt. The designer should keep Figma and Jira aligned during discovery, build, and release. If the Figma file says one thing and the Jira ticket says another, the team should pause and resolve the mismatch before implementation continues.

Figma handoff should usually include:

- Current flow, proposed flow, and any retired explorations clearly separated.
- Screens for default, loading, empty, error, disabled, success, and permission-limited states.
- Notes for interactions, validation rules, focus behavior, keyboard behavior, and responsive behavior.
- Copy that is final enough for build or clearly marked as draft.
- Component names, variants, and design system references when relevant.
- Accessibility annotations for focus order, labels, status announcements, contrast concerns, and non-color indicators.
- Data assumptions, such as which fields are required, optional, delayed, or unavailable.
- Edge cases that Product, Engineering, QA, Support, or customers are likely to encounter.

Jira handoff should usually include:

- A direct Figma link to the ready-for-build frame or prototype.
- The customer scenario and expected outcome.
- Acceptance criteria that name visible behavior and important states.
- Open questions, dependencies, and decisions still needed.
- Links to relevant research, product requirements, or decision notes when they exist.
- QA considerations, especially for permissions, failure recovery, audit logs, integrations, and accessibility.
- A note when design is intentionally partial because the work is being released behind a flag, to a beta group, or in a staged rollout.

Designers should keep old explorations findable but not confusing. Archive pages, labels, or file sections are better than deleting useful history or leaving five unlabeled "final" frames. When scope changes, update the handoff. A stale design file is not harmless; it can cause rework, QA defects, and customer-facing inconsistency.

## Accessibility Expectations

Accessibility is part of design quality at every level. It is not only a compliance issue and it is not only an Engineering task. Designers should make sure NovaOps can be used by people with different visual, motor, cognitive, and assistive technology needs.

Baseline expectations include clear headings, meaningful labels, readable contrast, visible focus states, keyboard navigation, predictable tab order, non-color-only meaning, accessible error messages, resizable layouts, and interactions that do not require precise pointer movement when an equivalent alternative is possible. Dense workflow tools need particular care because they often combine tables, panels, icons, drag and drop, code-like expressions, status colors, and live updates.

For workflow automation, designers should pay special attention to:

- Builders: A user should not need a mouse-only canvas to understand or edit a workflow. Provide list, panel, or structured alternatives where needed.
- Status: Failed, paused, running, completed, and needs-attention states should use text and icons, not color alone.
- Errors: Error messages should identify the problem, the affected step, who can fix it, and whether retry is safe.
- Time-sensitive work: Session timeouts, expiring approvals, and delayed integration responses should give users enough context to recover.
- Permissions: Disabled or hidden controls should explain permission limits when it is safe to do so.
- Motion: Animated workflow runs should not be the only way to understand progress.

D1 and D2 designers are expected to apply these practices to their own work. D3 designers should identify accessibility risks in complex projects. D4 and D5 designers should improve patterns, systems, and planning so accessibility is built into the product instead of rediscovered ticket by ticket.

## Research Expectations

Research at NovaOps should help the team make better decisions about customer workflows. It can be formal or lightweight, but it should be honest about what it proves. A five-person usability test can reveal usability problems. It cannot prove every customer segment will behave the same way. A Support pattern can reveal recurring confusion. It cannot replace speaking to users when the team is making a major product bet.

Useful research sources include customer interviews, moderated prototype tests, unmoderated task attempts, Support and Customer Success patterns, sales discovery notes, product analytics, onboarding observations, internal expert interviews, and post-launch retrospectives. Designers should protect customer and employee data in research artifacts. Use realistic synthetic examples in Figma when possible, and avoid copying sensitive customer information into design files.

Good research outputs are decision-oriented. They should answer questions such as:

- What job is the customer trying to complete?
- Which step of the workflow is most confusing or risky?
- Which user role has authority to make the decision?
- What does the customer expect the automation to do when something fails?
- Which assumption did we validate, weaken, or disprove?
- What should Product, Engineering, QA, Support, or Sales do differently because of what we learned?

At D1, research contribution may be note taking and synthesis with guidance. At D2, it includes planning and running small studies for a bounded feature. At D3, it includes choosing methods for ambiguous product questions. At D4, it includes building a research agenda across a product area. At D5, it includes shaping how the company learns before major product bets.

## Design Systems Expectations

The design system exists to make NovaOps more coherent, accessible, and efficient. It is not a visual polish library. It should help teams build workflow automation experiences that behave consistently across setup, monitoring, approvals, admin controls, audit history, billing-sensitive actions, and integrations.

Designers should prefer existing components and patterns. When a new need appears, the designer should decide whether it is a local exception, a missing variant, or a new reusable pattern. Good design system contribution includes the component purpose, anatomy, states, accessibility behavior, copy guidance, examples, non-examples, and implementation considerations.

Common design system areas for NovaOps include:

- Forms for triggers, actions, filters, approvals, schedules, and integration settings.
- Tables for runs, logs, users, approvals, and template lists.
- Status indicators for running, paused, failed, completed, draft, disabled, and needs attention.
- Side panels for details, configuration, review, and error recovery.
- Modals and confirmations for destructive or billing-sensitive actions.
- Workflow nodes, connectors, branch conditions, and retry controls.
- Empty states that teach next action without becoming marketing copy.
- Audit trails and event histories that can be scanned under pressure.

A design system contribution is only strong if it is adopted or clearly prepares the team for adoption. A beautiful component in Figma that Engineering cannot build, QA cannot test, or designers cannot understand is not yet a durable contribution.

## Promotion Evidence

Promotion evidence includes better customer outcomes, clearer product strategy, improved design systems, stronger collaboration, and decisions that reduced confusion for customers or teammates. See [making a career](making-a-career.md) for cycle timing.

Strong designer promotion evidence should connect design work to outcomes. Good packets include the customer problem, the design choices considered, tradeoffs rejected, shipped or adopted work, and what changed because of the designer's judgment. Evidence may include Figma artifacts, Jira tickets, research summaries, customer quotes captured through approved channels, launch retrospectives, design system adoption, accessibility improvements, QA findings avoided, or Product and Engineering peer input.

Examples of strong evidence:

- A workflow builder change reduced setup errors because the designer identified where users misunderstood branch conditions and created a clearer model.
- A run-diagnostics redesign helped Support and customers identify failed integration steps faster, reducing repeated escalations.
- A research synthesis changed the roadmap by showing that customers needed approval visibility before advanced automation templates.
- A design system contribution standardized status behavior across multiple product areas and reduced repeated Engineering questions.
- A handoff practice improved QA coverage by making permission, empty, error, and loading states explicit.
- A designer mentored another designer through a difficult product area while leaving clear ownership with that person.
- A designer challenged a requested feature, showed the risk, and helped the team choose a smaller release that still solved the customer problem.

Good evidence should include before and after when possible. "Customers were confused" is weaker than "in five onboarding calls, admins could not tell whether a workflow was active; after the change, customers correctly identified draft, active, and paused states in validation sessions." Metrics are helpful but not required for every design decision. When quantitative data is unavailable, the packet should use specific qualitative evidence and explain its limits.

## Non-Evidence

Non-evidence is work or behavior that may be real effort but does not show readiness for a higher design title by itself. A promotion packet should not rely on:

- Number of Figma frames created.
- Number of meetings attended.
- Personal taste or visual polish without customer or product impact.
- Being the only person who remembers how a confusing file works.
- Working late to rescue a project whose risks were not raised earlier.
- Being liked by teammates without examples of stronger outcomes.
- Repeating a known pattern without improving the customer experience or team process.
- Creating a large strategy deck that did not change decisions or action.
- Owning a crisis that the designer's own missed state coverage helped create.
- Copying another product's pattern without showing why it fits NovaOps customers.
- Winning an argument with Product or Engineering without improving the decision.

Slack praise, attractive prototypes, and executive visibility can support a packet, but they cannot replace concrete evidence. A single heroic launch can count if it shows next-level judgment, but the packet must explain what repeated after the launch ended.

## Realistic Edge Cases

Canceled projects: A canceled project can still be evidence if the designer showed next-level judgment before cancellation. For example, a D3 candidate may have uncovered that a planned automation feature would not solve the customer workflow and helped Product cancel or reshape the project. The packet should explain what decision changed and what waste or risk was avoided.

Partial launches: If a feature launched behind a flag, in beta, or to one customer segment, evidence should be scoped honestly. Do not claim broad customer impact from a limited rollout. It is still useful evidence if the designer defined the release slice, validated the risky states, and created a path to broader launch.

Inherited designs: Designers often inherit old flows, messy files, or decisions made before they joined the project. Evidence should separate what the designer inherited from what they changed. Cleaning up a file is helpful, but the stronger evidence is usually the decision clarity, pattern improvement, or customer outcome that cleanup enabled.

Manager or team changes: If a designer changed managers or teams during a cycle, the promotion packet should identify which evidence came from which context. The current manager should consult the previous manager when needed and should avoid treating lost context as a design gap.

Conflicting Product and Engineering feedback: When Product wants a richer experience and Engineering wants a simpler build, the designer should make tradeoffs visible. A good outcome may be a staged design: the first release handles the common workflow safely, and a later release adds advanced configuration. The designer should document what was deferred and what customer risk remains.

Accessibility versus schedule pressure: Schedule pressure does not erase accessibility expectations. If the team must defer an accessibility improvement, the designer should name the risk, agree on a mitigation, and create follow-up work. Avoid vague notes such as "accessibility later." Name the specific issue, such as keyboard access to branch editing or screen reader labeling for run status.

Research with small samples: Small samples are common in B2B work. They are acceptable when the designer is clear about confidence. Three customer sessions can be enough to identify a confusing workflow step. They are not enough to claim that all enterprise customers prefer one configuration model.

Figma and Jira mismatch: If Engineering built from an outdated frame because the file was unclear, the designer should help fix the immediate problem and then improve the handoff process. The lesson may be a clearer ready-for-build page, a decision log, or a Jira update habit.

Design system exceptions: Sometimes a feature needs a one-off pattern because the existing system does not support the workflow. The designer should document why the exception exists, how it behaves, and whether it should become reusable. Exceptions become risky when nobody can tell whether they are intentional.

Customer-specific requests: Sales, Support, or Customer Success may bring a request from an important customer. Designers should respect the signal without assuming the requested solution is the right product answer. The designer should ask what workflow pain sits underneath the request, whether other customers share it, and whether the proposed design creates long-term complexity.

Contractor or guest collaboration: Contractors may help with frontend implementation or research operations, but designers remain responsible for design quality and secure sharing. Figma and Jira access should follow the approval process in [our internal systems](our-internal-systems.md), and files shared with guests should avoid unrelated product or customer information.

Internal tools versus customer-facing work: Internal workflow tools matter, but promotion evidence should still show scope and impact. A small internal cleanup is usually D1 or D2 evidence. A cross-functional internal workflow that reduces onboarding errors, improves auditability, and creates reusable patterns may be stronger evidence.

## What Good Looks Like

Good design work at NovaOps makes complex operations understandable without hiding important risk. It helps customers know what will happen, what already happened, what failed, who can fix it, and whether the system can be trusted. It helps Product choose valuable problems, helps Engineering build coherent solutions, helps QA test the right states, and helps Support explain the product clearly.

The best designers here are not only screen makers. They are sense-makers. They understand the customer's workflow, protect the quality of the product, make tradeoffs visible, and leave the system easier for the next person to improve.
