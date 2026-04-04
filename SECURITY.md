# Security Policy

## What this repo is

This repository contains a FaB game engine **and prompt files** — markdown documents that get read by AI coding agents as instructions. When you run `claude` in this directory, the agent reads these files and acts on them, including creating files, modifying code, and running commands.

**This is a supply chain risk.** A compromised prompt file can instruct an AI agent to exfiltrate data, install backdoors, or modify your code in harmful ways — all while appearing to do legitimate work.

## What these files are allowed to do

The role files (`agents/*.md`) and protocol files in this repo should **only**:

- Read files within this project directory
- Create/modify agent system files (CLAUDE.md, AGENTS.md, role files, memory files, protocol files)
- Run `git` commands scoped to this repo
- Run `pytest` and other dev tooling defined in `pyproject.toml`
- Produce reports within the project directory

They should **never**:

- Read `.env`, credentials, SSH keys, API keys, or any secrets
- Make unsolicited network requests — agents may fetch URLs when the user explicitly asks, but should not make network calls on their own initiative
- Access system paths outside this project directory (`/etc/`, `/home/`, `~/.ssh/`, etc.)
- Push to remotes, deploy, or execute deployment scripts without user confirmation
- Encode, obfuscate, or eval anything
- Suppress user review or bypass confirmation prompts
- Reference environment variables
- Include executable files or non-markdown content in `agents/`

## Before you use this

1. **Read every file in `agents/`** before running the agents. These are the instructions your AI agent will follow.
2. **Verify the source.** Clone from the official repo. Check the commit history.
3. **Review changes to agent files.** When agent files are modified, read the diff before accepting.

## Reporting vulnerabilities

If you find a security issue in this repo — including prompt injection, data exfiltration instructions, or scope violations — please report it privately:

- Open a [GitHub Security Advisory](https://github.com/CollCrom/tcg-htc/security/advisories/new) on this repo
- Or email the maintainer directly (see GitHub profile)

Do not open a public issue for security vulnerabilities.
