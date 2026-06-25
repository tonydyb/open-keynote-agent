# Spec: Project Positioning

## Capability

The project documentation shall position the product as `Open Keynote Agent`, a focused macOS agent for creating and editing Apple Keynote presentations through natural language.

## Requirements

### REQ-001: Project name and purpose

The documentation shall use `Open Keynote Agent` as the product name and `open-keynote-agent` as the project slug.

#### Scenario: Reader opens project documentation

Given a reader opens the README or OpenSpec project overview  
Then they shall understand that the project focuses on Keynote presentation automation  
And not on general-purpose macOS automation.

### REQ-002: Existing file organizer context

The documentation shall preserve the existing CLI file organizer as a completed learning milestone.

#### Scenario: Reader sees file organizer commands

Given the README still includes `oma organize` and `oma ask` examples  
Then it shall explain that these commands demonstrate the first-stage agent foundation  
And future work is Keynote-focused.

### REQ-003: No mechanical rename in this change

This change shall not require renaming the Python package, CLI command, or repository directory.

#### Scenario: Developer runs existing commands

Given the developer has the current package installed  
When they run existing CLI commands  
Then the commands shall continue to work without a package rename.

### REQ-004: Future roadmap

The documentation shall identify the next direction as an interactive Keynote agent.

#### Scenario: Developer chooses next implementation work

Given the developer reads the project overview  
Then they shall see that future changes should focus on interactive sessions, Keynote tools, observations, and export verification.
