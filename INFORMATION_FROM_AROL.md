# Project Q2 — Multi-Agent AI Framework for Industrial Fleet Management and Autonomous Troubleshooting

## Overview

This repository contains the synthetic dataset developed for **Project Q2**, a collaboration between **Politecnico di Torino** and **AROL S.p.A.**. The dataset simulates the information ecosystem of an industrial machinery manufacturer and its customers, providing a realistic environment for developing and evaluating AI-powered fleet management and autonomous troubleshooting solutions.

The objective of the project is to design a conversational AI platform capable of assisting plant operators through a coordinated ecosystem of specialized AI agents that can reason over heterogeneous data sources including:

- Technical documentation
- Machine telemetry
- Alarm history
- Maintenance records
- Commercial and contractual information

---

## Dataset Files

- `AROL_Q2_synthetic_fleet_dataset.xlsx` — the dataset, one sheet per business or technical domain
- `manuals/` — one use-and-maintenance manual per machine in the fleet

---

## How This Dataset Was Designed

Two deliberate choices are worth knowing about before you start.

**You are given more than one kind of data.** The package contains both **structured data** (the relational sheets of the workbook) and **unstructured documents** (the PDF manuals). This is intentional: answering a realistic question often requires both, and the two are reached in completely different ways: a query over tables on one side, document retrieval on the other. Part of what is being assessed is your ability to make the assistant work across heterogeneous sources, and to orchestrate the components that handle them so that the right source is consulted for the right question.

**The dataset was customized for this project.** Rather than handing over raw industrial exports full of noise, duplication and irrelevant fields, we prepared a dataset that is internally consistent and scoped to what the project needs. The intent is that the difficulty of the work lies in the design of your system, not in months of data cleaning. It is still realistic: values, relationships and terminology follow how these machines actually operate, and it still contains cases that require care.

If anything about the data or the project is unclear, or you think you have found an inconsistency, **contact us** — see [Contacts](#contacts). Asking is expected and it is faster than guessing.

---

## Dataset Structure

### 1. Companies

Contains synthetic customer organizations operating industrial production plants.

| Field       | Description               |
| ----------- | ------------------------- |
| companyId   | Unique company identifier |
| companyName | Customer company name     |
| country     | Country                   |
| city        | Operating city            |
| sector      | Industrial sector         |
| currency    | Commercial currency       |
| locale      | Regional settings         |

**Purpose.** Represents the customer base served by AROL and provides organizational context for machines, users, quotes, and service activities.

### 2. Users

Contains personnel associated with customer companies.

| Field      | Description                                    |
| ---------- | ---------------------------------------------- |
| userId     | Unique user identifier                         |
| companyId  | Associated company                             |
| firstName  | First name                                     |
| lastName   | Last name                                      |
| email      | Contact email                                  |
| jobTitle   | Professional role                              |
| visibility | Data access scope, see **Access Model** below   |

All users are considered active accounts.

**Purpose.** Used for user management, permission simulation, service ownership, and chatbot interactions.

### 3. MachineModels

Contains specifications of industrial machine models.

| Field             | Description                                                             |
| ----------------- | ----------------------------------------------------------------------- |
| modelId           | Unique model identifier                                                 |
| modelCode         | Machine model code                                                      |
| description       | Model description                                                       |
| primitiveDiameter | Pitch diameter of the closure carousel, in mm. Empty where not declared |
| nominalHeads      | Number of closure heads                                                 |
| containerType     | Supported container type                                                |
| capType           | Supported cap type                                                      |
| industrySegment   | Target industry                                                         |
| notes             | Additional technical notes                                              |

**Purpose.** Represents the engineering knowledge base used by AI agents during troubleshooting and diagnostic workflows.

### 4. Machines

Contains the installed fleet of machines deployed at customer locations.

| Field                | Description                                                        |
| -------------------- | ------------------------------------------------------------------ |
| machineId            | Unique machine identifier                                          |
| companyId            | Owning company                                                     |
| modelId              | Installed machine model                                            |
| serialNumber         | Manufacturer serial number, also the key to the machine manual     |
| deliveryDate         | Date the machine was delivered to the customer site                |
| plantLocation        | Production plant and line                                          |
| configurationProfile | As-built configuration of this specific machine                    |
| plcFamily            | Control architecture                                               |
| softwareVersion      | Control software version, where the machine has its own            |

**Purpose.** Acts as the central entity that connects telemetry, alarms, maintenance history, and business information.

### 5. Quotes

Represents commercial quotations issued to customers.

**Purpose.** Provides visibility into the sales lifecycle and commercial history preceding machine purchases or service activities.

### 6. QuoteRevisions

Tracks historical modifications made to quotations.

**Purpose.** Allows AI agents to retrieve previous commercial proposals and revision history.

### 7. QuoteLines

Contains detailed quotation items. Each line links to a **revision** through `quoteRevisionId`, not to a quote directly: there is no `quoteId` here, so reaching a quote from its lines goes through `QuoteRevisions`.

**Purpose.** Provides granular information about products, options, and services included in each quotation.

### 8. Orders

Represents confirmed customer orders generated from approved quotations.

**Purpose.** Links commercial activity to production, installation, and maintenance workflows.

### 9. OrderLines

Contains individual order items.

**Purpose.** Allows detailed analysis of purchased machines, spare parts, and services.

### 10. TelemetrySnapshots

Contains simulated IoT telemetry generated by industrial machines.

| Field             | Description            |
| ----------------- | ---------------------- |
| telemetryId       | Snapshot identifier    |
| machineId         | Machine reference      |
| timestamp         | Measurement timestamp  |
| operationalStatus | Machine status         |
| productionRateBph | Production rate        |
| uptimePercentage  | Availability indicator |
| alarmCount        | Active alarm count     |
| temperatureC      | Operating temperature  |
| energyKwh         | Energy consumption     |
| healthNote        | Diagnostic annotation  |

**Purpose.** Primary data source for telemetry analysis, enabling predictive analysis, health monitoring, and autonomous diagnostics.

### 11. Alarms

Contains machine alarm events.

| Field       | Description       |
| ----------- | ----------------- |
| alarmId     | Alarm identifier  |
| machineId   | Machine reference |
| timestamp   | Alarm timestamp   |
| alarmCode   | Alarm code        |
| severity    | Alarm severity    |
| alarmStatus | Current status    |

**Purpose.** Supports troubleshooting workflows and machine health evaluation.

### 12. MaintenanceTickets

Contains service and maintenance activities.

| Field        | Description          |
| ------------ | -------------------- |
| ticketId     | Ticket identifier    |
| machineId    | Machine reference    |
| alarmId      | Related alarm        |
| ticketType   | Type of intervention |
| ticketStatus | Current status       |
| priority     | Service priority     |
| createdDate  | Creation date        |
| ownerRole    | Responsible role     |

**Purpose.** Represents the service management lifecycle and enables maintenance analytics.

---

## Access Model

Access is controlled by two independent checks. Both must pass before any data is returned.

1. **`companyId`** — the tenant boundary. A user only ever reaches rows belonging to their own company. This is never crossed, at any visibility level.
2. **`visibility`** — narrows *what kind* of data the user sees inside their own company.

For this purpose the data splits into three domains:

- **Machine identity and documentation** — `Machines`, `MachineModels`, and the machine manuals in `manuals/`.
- **Operational data** — `TelemetrySnapshots`, `Alarms`, `MaintenanceTickets`.
- **Commercial data** — `Quotes`, `QuoteRevisions`, `QuoteLines`, `Orders`, `OrderLines`.

**Machine identity and documentation is visible to every user**, for the machines their own company owns. The other two domains are restricted:

| visibility   | Machines, models and manuals | Telemetry, alarms, maintenance | Quotes and orders |
| ------------ | ---------------------------- | ------------------------------ | ----------------- |
| `full`       | yes                          | yes                            | yes               |
| `technician` | yes                          | yes                            | no                |
| `commercial` | yes                          | no                             | yes               |

Every user may also read their own `Companies` row and their own `Users` row.

So any user can ask what a machine is, how it is configured and what its manual says. Only a `technician` can ask how it is currently running, what alarms it has raised or what maintenance it has had. Only a `commercial` user can ask what it cost or what has been quoted and ordered for it.

A request that falls outside a user's scope must be declined explicitly. It must never be answered from another company's data, and never returned as an empty result as though no data existed.

---

## Machine Documentation

The `manuals/` folder contains one use-and-maintenance manual per machine.

Manuals are **machine-specific, not model-specific**: each one documents a single physical machine as it was built. The file name contains the serial number, so `Machines.serialNumber` is the join key between the workbook and the documentation:

```text
manuals/<serialNumber>_manual_EN.pdf
```

For example, machine `MCH-0004` has serial number `17478` and is documented by `manuals/17478_manual_EN.pdf`.

Every machine in the fleet has a manual, and every manual corresponds to a machine in the fleet.

---

## Reading the Data Correctly

A few conventions are not obvious from the column names. Everything else is left for you to discover by exploring the data.

### Time reference

You have two choices:

1. Treat **2026-08-05** as "today" when reasoning about open items, overdue work and expiry dates. In this way you can use the dataset as is, without any time travel.
2. Re-base all timestamps to the current date (or add some data) if you want to simulate a live system. This is not required, but it is still a valid approach. Pay attention: if you change dates that are referenced by other dates, the risk is having inconsistent data and your chatbot may give wrong answers.

### Two machines of the same model are not interchangeable

Machines that share a `modelId` can differ substantially in how they were built and configured, including their nominal production rate, supply voltage and installed options.

Nominal production rate, installed power, supply voltage and closure head type have no dedicated column. They are recorded per machine in **`Machines.configurationProfile`**. Read that field, not `MachineModels`, before judging whether a telemetry reading is normal for a given machine.

### Where telemetry and alarms come from

The fleet is monitored by IoT sensor nodes fitted to each machine. The nodes stream measurements to the platform, and a computing layer evaluates that stream and raises an alarm when it detects a problem condition.

`TelemetrySnapshots` is the measurement stream, aggregated per hour. `Alarms` is the output of the evaluation layer. Both are produced by the platform, not read from a machine display, which is why alarms exist for machines that have no operator panel of their own.

### Alarm codes

Alarm codes have the form `ALnnn_MNEMONIC`, for example `AL017_LOW_AIR_PRESSURE`.

The code identifies a **physical problem condition** on the machine, and the mnemonic is its short textual description. To resolve an alarm, use that description to search the manual of the machine that raised it: the technical data, mechanical and troubleshooting sections describe the cause and the remedy for that condition on that specific machine.

The catalogue of codes is common to the whole fleet, but a machine only raises conditions its own configuration can physically produce. `severity` is assigned by the monitoring platform, not taken from the manuals, and is fixed per code.

### Telemetry

- Each row summarises a one-hour interval for one machine.
- `uptimePercentage` is the share of the interval spent actually producing. It is `0` whenever the machine is not producing, so it measures productive time and not equipment health.
- `productionRateBph` is `0` whenever the machine is not producing, and never exceeds that machine's own nominal rate.
- `alarmCount` counts the alarms raised by that machine during that interval and agrees with the `Alarms` sheet for the same machine and hour.

### Quotes and orders

- `Quotes` has no status column. The lifecycle state lives on `QuoteRevisions.revisionStatus`.
- Revisions are numbered from `1`. The highest `revisionNumber` of a quote is the current one; earlier revisions are superseded.
- `QuoteLines` belong to a revision, so comparing two revisions means comparing their line sets.
- `QuoteLines.price` is already net of the parent revision's `discountRate`. Do not apply the discount a second time.
- `OrderLines` tracks fulfilment only: it carries no item, quantity or price. The content of an order comes from the quote lines of the approved revision.

### Controlled vocabularies

| Column                                | Values                                                                                                   |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `Users.visibility`                    | `full`, `technician`, `commercial`                                                                       |
| `Machines.plcFamily`                  | `SIEMENS-SIMATIC-S7`, `LINE-PLC-INTEGRATED`, `HARDWIRED-CONTROL-PANEL`                                   |
| `QuoteRevisions.revisionStatus`       | `Draft`, `Submitted`, `Superseded`, `Approved`, `Rejected`, `Expired`                                     |
| `Orders.orderStatus`                  | `Confirmed`, `In production`, `Delivered`, `Closed`                                                      |
| `Orders.shipmentStatus`               | `In production`, `Ready for shipment`, `Delivered`, `Installed`                                          |
| `OrderLines.fulfillmentStatus`        | `Manufacturing`, `Ready for shipment`, `Delivered`                                                       |
| `TelemetrySnapshots.operationalStatus`| `Running`, `Alarm`, `Idle`, `Stopped`, `Maintenance`, `Size change`                                       |
| `Alarms.severity`                     | `Critical`, `High`, `Medium`, `Low`                                                                      |
| `Alarms.alarmStatus`                  | `Open`, `Acknowledged`, `Resolved`                                                                       |
| `MaintenanceTickets.ticketType`        | `Remote troubleshooting`, `On-site service`, `Spare parts request`, `Scheduled maintenance`, `Overhaul`, `Size change assistance` |
| `MaintenanceTickets.ticketStatus`      | `Open`, `In progress`, `Waiting for parts`, `Resolved`, `Closed`                                          |
| `MaintenanceTickets.priority`          | `Critical`, `High`, `Medium`, `Low`                                                                      |
| `MaintenanceTickets.ownerRole`         | `Line Operator`, `Maintenance Man`, `Plant Maintenance Manager`, `AROL Technical Service`                 |

---

## Edge Cases

The dataset deliberately contains situations that a naive implementation handles incorrectly. Their location is not documented: finding them is part of the analysis.

Some foreign keys are intentionally empty, so an inner join will silently drop rows:

- `QuoteLines.machineId` is empty on lines that do not refer to an installed machine
- `MaintenanceTickets.alarmId` is empty on tickets that did not originate from an alarm
- `MachineModels.primitiveDiameter` is empty where the model does not declare one

Other situations present in the data:

- a company that has users but owns no machines
- quotations that never became orders, including one approved after its validity had expired
- a quotation whose final revision was rejected
- machines whose accumulated service hours have passed a maintenance threshold defined in their manual

---

## AI Architecture

The number of agents, their responsibilities, and the way work is divided between them are **design decisions left to each team**. The dataset does not assume any particular decomposition and there is no single correct architecture. You are expected to justify the design you choose.

The grouping below is one possible starting point, not a requirement.

### Documentation retrieval

- Retrieve technical information from the machine manuals
- Provide operating, maintenance and troubleshooting instructions
- Support RAG workflows over the PDF documentation

### Telemetry and diagnostics

- Analyse machine health and detect anomalies
- Identify performance degradation
- Correlate alarms with maintenance history

### Commercial information

- Retrieve quotation and order history
- Answer questions on the commercial relationship with a customer

Other decompositions are equally valid, including a single agent with multiple tools, or a finer split with a dedicated orchestrator, planner or access-control component.

---

## QR Codes

On a real plant floor, an operator identifies the machine in front of them by scanning a QR code applied to it. How you implement this is up to you, and no QR codes are supplied with the dataset.

Our suggestion is to keep it simple: encode a **URL to your platform that points at a specific machine**, using either the `machineId` or the `serialNumber` as the identifier, for example:

```text
https://<your-platform>/machines/MCH-0004
https://<your-platform>/machines/17478
```

Scanning then opens the assistant already scoped to that machine, and the identifier is enough to reach everything else: its model, telemetry, alarms, maintenance history, and its manual in `manuals/`.

Because a QR code is just an encoding of such a URL, there is nothing to pre-generate on our side — generating them is trivial with any QR library once you have decided your URL scheme. That decision is the interesting part, so we have deliberately left it open rather than fixing it for you.

---

## Example Research Questions

The dataset can be used to answer questions such as:

- Why is machine `<serialNumber>` generating repeated alarms?
- What maintenance activities were recently performed on a given machine?
- What periodic maintenance is due for a given machine, and when?
- What does alarm `AL017_LOW_AIR_PRESSURE` mean, and what does the manual recommend?
- What was the latest quotation revision issued to a customer, and how did it change?
- When was the machine delivered and how much did it cost?
- How can I order spare parts for the machine `<serialNumber>`?
- Which safety procedures should be followed before performing maintenance on machine `<serialNumber>`?

Note: These are only examples. You are encouraged to explore the dataset and formulate your own research questions. Evaluation is an important part of the project, and your ability to define meaningful questions is part of that evaluation.

---

## Disclaimer

All data contained in this dataset is synthetic and generated exclusively for academic and research purposes. Any resemblance to real customers, industrial plants, machines, or operational data is purely coincidental.

The machine manuals in `manuals/` are the property of AROL S.p.A. and are supplied for use within this course only. Refer to the notice on page 2 of each manual.

---

## Contacts

**Politecnico di Torino**

Prof. Stefano Quer
stefano.quer@polito.it

**AROL S.p.A.**

Alessio Chessa
alessio.chessa@arol.com

Elia Ferraro
elia.ferraro@arol.com

For project-related questions, please refer to the course staff and industrial supervisors.

Questions and doubts about the dataset itself are welcome too: if a value looks wrong, a relationship is unclear, or you are unsure how something should be interpreted, get in touch rather than working around it. In this way you help us improve the dataset for everyone.
