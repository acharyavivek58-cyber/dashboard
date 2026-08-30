# 🤖 Discord All-in-One Bot

A full-featured Discord bot with moderation, utility, role management, fun commands, and automatic logging.

## Features

| Category | Commands |
|----------|----------|
| **Moderation** | `ban`, `kick`, `mute`, `unmute`, `warn`, `warnings`, `purge` |
| **Utility** | `ping`, `uptime`, `userinfo`, `serverinfo`, `avatar`, `servericon`, `id` |
| **Roles** | `role`, `createrole`, `deleterole`, `roles` |
| **Fun** | `8ball`, `coinflip`, `dice`, `reverse`, `choose`, `say`, `poll` |
| **Logging** | Message delete/edit, member join/leave, voice state changes |

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your bot token from the [Discord Developer Portal](https://discord.com/developers/applications).

3. **Run the bot:**
   ```bash
   python main.py
   ```

## Required Bot Permissions

Invite your bot with these permissions:
- Administrator (simplest), or specifically:
  - Ban Members, Kick Members, Manage Messages, Manage Roles
  - Send Messages, Embed Links, Read Message History
  - Moderate Members (for timeout/mute)
  - View Audit Log

## Commands

### Moderation
- `!ban @user [reason]` — Ban a member
- `!kick @user [reason]` — Kick a member
- `!mute @user [minutes] [reason]` — Timeout a member
- `!unmute @user` — Remove timeout
- `!warn @user [reason]` — Warn a member (tracked per guild)
- `!warnings @user` — View warnings for a member
- `!purge [amount] [@user]` — Bulk delete messages

### Utility
- `!ping` — Check latency
- `!uptime` — Bot uptime
- `!userinfo [@user]` — Member info card
- `!serverinfo` — Server info card
- `!avatar [@user]` — Get user's avatar
- `!servericon` — Get server icon
- `!id [@user]` — Get user ID

### Roles
- `!role @user @role` — Add/remove a role (toggle)
- `!createrole <name> [color] [hoist]` — Create a role
- `!deleterole @role` — Delete a role
- `!roles` — List all roles

### Fun
- `!8ball <question>` — Ask the magic 8-ball
- `!coinflip` — Flip a coin
- `!dice [count] [sides]` — Roll dice
- `!reverse <text>` — Reverse text
- `!choose <option1>, <option2>, ...` — Random choice
- `!say <text>` — Bot repeats after you
- `!poll <question> [options]` — Create a reaction poll

> **Note:** All commands also work as slash commands (`/ban`, `/ping`, etc.)

## Logging

Set `LOG_CHANNEL_ID` in `.env` to enable automatic logging. If not set, the bot will auto-detect channels named `log`, `logs`, `audit-log`, `mod-log`, or `bot-logs`.

Logs include:
- Message deletions & edits (with content preview)
- Member joins & leaves (with role list)
- Voice channel activity
