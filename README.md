# Telegram Community Manager

A Telegram bot for managing approved users, community invite links,
consent-based announcements, task records, and administrative reports.

## Features

- User registration and admin approval
- Admin controls for approving or banning users
- User account and credit records
- Community invite-link management
- Opt-in announcements
- Task status tracking and reports
- PostgreSQL database support
- Railway background worker deployment

## Requirements

- Python 3.11 or newer
- A Telegram bot token from BotFather
- A PostgreSQL database
- A Railway account or another compatible hosting service

## Environment Variables

Configure these in your hosting provider:

- BOT_TOKEN: Telegram bot token
- ADMIN_IDS: Comma-separated numeric Telegram user IDs
- DATABASE_URL: PostgreSQL connection URL
- APP_ENV: Set to production
- LOG_LEVEL: Usually INFO

Never commit real tokens, passwords, or database credentials to GitHub.

## Local Setup

Install the dependencies:

    pip install -r requirements.txt

Set the required environment variables, initialize the database,
and start the bot:

    python bot.py

## Railway Deployment

1. Push the project to GitHub.
2. Create a Railway project from the repository.
3. Add a PostgreSQL database.
4. Configure the required environment variables.
5. Deploy the worker and review the deployment logs.

## Safety

Use the bot for authorized community management and messages to users
who have opted in. Do not use it to scrape members or automate
unsolicited bulk invitations.
