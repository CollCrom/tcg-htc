# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker, and adds one label of our own.

| Label in mattpocock/skills | Label in our tracker | Meaning                                                                 |
| -------------------------- | -------------------- | ----------------------------------------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue                                 |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information                                |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent                                 |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation                                           |
| `wontfix`                  | `wontfix`            | Will not be actioned                                                    |
| (none)                     | `blocked`            | Specified, but gated on an event the body names; not on the frontier    |

A `blocked` issue is done as part of the ticket that brings the event about, so a next-ticket scan skips it. When that ticket is filed, replace the label with a native issue dependency on it (see **Blocking** in `issue-tracker.md`).

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the "Label in our tracker" column to match whatever vocabulary you actually use.
