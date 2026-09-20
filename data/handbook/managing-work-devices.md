---
last_updated: 2024-11-23
corpus: handbook
audience: all
---

# Managing Work Devices

## Company-Owned Equipment

NovaOps provides the equipment required to do your job securely. Most full-time employees receive a company-owned laptop, charger, headset, and basic accessories. Remote employees may request an external monitor, keyboard, mouse, dock, or chair through [the IT request portal](https://it.novaops.example). IT keeps the equipment record, serial number, assigned owner, country, and shipping status in the laptop fleet system.

Company devices are for NovaOps work. Reasonable personal use is allowed, but do not store personal archives, family photos, tax records, side-project source code, customer exports, payroll files, or another employer's data on a NovaOps laptop. Devices may be remotely managed, patched, encrypted, inventoried, locked, and wiped by IT. Equipment is assigned to a person; do not swap assets unless IT updates the fleet record.

## Lifecycle and Setup

New hires normally receive their laptop before day one when address, country, and start date are confirmed early. People Operations confirms the start date in BambooHR; IT provisions Okta, Slack, Webex, the laptop, and role access described in [getting started](getting-started.md). If a laptop is delayed, IT may issue a loaner, but Salesforce, GitHub, BambooHR, and AWS still require a managed device unless IT grants a specific exception.

During first setup, sign in through Okta, turn on MFA, confirm disk encryption, and let management enrollment finish. The first hour can be slow while tools install. If setup is stuck for more than two hours, file a ticket with the asset tag, country, and a screenshot of the last visible error.

IT tracks three device states: assigned, loaner, and in repair. Loaners must be returned when the repair or replacement is complete. Standard laptop refresh is every three years. Early replacement requires manager approval and IT confirmation that repair would not be cost-effective.

## Security, Admin Rights, and Software

Use Okta MFA, keep disk encryption enabled, and install updates within five business days unless IT announces a shorter security deadline. Do not disable endpoint protection, share your laptop account, or let family members use the device. Restricted systems such as Salesforce, GitHub, BambooHR, and AWS must not be accessed from unmanaged personal devices unless IT grants a specific exception.

Lock your screen when stepping away. Do not leave a laptop unattended or in checked luggage. Keep security keys separate from the laptop when practical.

Local administrator rights are not standard. Some Engineering and IT roles may need elevated rights for development tooling, troubleshooting, or local virtualization. Admin rights require manager approval, IT approval, and a review date. IT may remove them after the reason expires or if the device falls behind on controls.

Software installs should come from IT-approved catalogs, managed app stores, or approved vendor sites. Free trials and browser extensions count as software if they touch company data. New paid tools, AI plugins, backup utilities, screen recorders, database clients, and page-reading extensions require approval before company data is added. Work should live in approved systems: GitHub for source code, Jira for planned work, Salesforce for customer records, BambooHR for HR records, and AWS for cloud resources.

## Lost, Stolen, or Compromised Devices

If a device is lost, stolen, exposed to malware, or possibly accessed by someone else, notify IT immediately at amir.haddad@novaops.example or through [the IT request portal](https://it.novaops.example). Fast reporting matters more than perfect detail. Report the asset tag if known, city and country, approximate time, lock state, and anything lost with it.

For theft, file a local police report where practical and upload the report number to the IT ticket. IT may lock or wipe the device, rotate Okta sessions, revoke security keys, reset passwords, and ask whether customer data or source code was involved. If you later find the device, tell IT before using it.

Malware, suspicious pop-ups, unexpected MFA prompts, unknown browser extensions, or sudden recovery-key prompts are reportable. Disconnect from Wi-Fi if IT asks, but do not wipe or reinstall the laptop yourself.

## Repairs, Replacements, and Shipping

IT replaces failing equipment when repair is not practical. If the laptop will not boot, the battery is swollen, the keyboard fails, the screen flickers, or video calls remain unusable after troubleshooting, open a ticket. Include the model, asset tag, country, and shipping address.

Purchases above USD 1,500 require Finance review by Tom Baker before the order is placed. Do not split one purchase to avoid review, and do not buy a laptop personally expecting reimbursement. Accessories under USD 150 may be reimbursed with manager approval and a receipt. Avoidable misuse, repeated loss, or ignored shipping instructions may require manager review before replacement.

NovaOps works across Israel, Germany, the United Kingdom, and the United States, and shipping rules are not identical. Give IT the country, city, postal code, courier phone, and building notes. Israel shipments may require a courier call. Germany shipments may require handoff or pickup. United Kingdom shipments may need customs time. United States returns can usually use prepaid labels, but employees must use IT's exact label.

Do not personally ship a NovaOps laptop across borders unless IT confirms the route, customs description, declared value, and return label. Batteries, docks, monitors, and security keys may need separate packaging. If customs asks for an invoice or importer information, send it to IT; do not invent a value or call the laptop a gift.

## Contractors and Leaving NovaOps

Contractors receive only the equipment and access needed for the engagement. A contractor may be issued a NovaOps laptop for source code, customer data, production-like data, or systems requiring a managed endpoint. Contractor equipment must be requested by the contract owner or manager and approved by IT before shipping. Contractor GitHub access and privileged access follow [our internal systems](our-internal-systems.md).

Contractors must return NovaOps equipment at the end of the engagement, during a long work pause, or earlier if requested. The default return deadline is five business days from the contract end date unless the written agreement or People Operations sets a different local process. Contractors must not pass equipment to a replacement contractor, subcontractor, teammate, or client contact. Managers confirm return plans before final invoice approval.

When employment or a contract ends, IT sends return instructions and a prepaid shipping label where available. You must return your laptop, charger, security keys, and company accessories within five business days of your last working day unless People Operations approves a different local process.

Before returning the laptop, save personal files elsewhere and make sure NovaOps work is in the correct company systems. Do not delete company records, source code, customer notes, Jira tickets, Slack messages, or shared files, and do not factory reset the device. For a normal planned departure, IT disables Okta access on the agreed schedule, often at the end of the last working day. For involuntary, security-sensitive, or no-transition departures, access may be disabled earlier. See [severance](severance.md) for separation pay and unused vacation treatment.
