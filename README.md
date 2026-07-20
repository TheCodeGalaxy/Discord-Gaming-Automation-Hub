<div align="center">

# 🎮 Discord Gaming Automation Hub

### Self-hosted gaming automation for Discord

Free games • Crazy discounts • Major releases • Google Calendar • Automation

<p>
  <a href="https://github.com/TheCodeGalaxy/Discord-Gaming-Automation-Hub">
    <img src="https://img.shields.io/badge/GitHub-Repository-black?style=for-the-badge&logo=github">
  </a>
</p>

<p>
<img src="https://img.shields.io/badge/Status-Beta-yellow?style=flat-square">
<img src="https://img.shields.io/badge/License-MIT-green?style=flat-square">
<img src="https://img.shields.io/badge/Python-3.12+-blue?style=flat-square&logo=python">
<img src="https://img.shields.io/badge/discord.py-Latest-5865F2?style=flat-square&logo=discord">
<img src="https://img.shields.io/badge/FastAPI-Async-009688?style=flat-square&logo=fastapi">
<img src="https://img.shields.io/badge/SQLite-Built--in-blue?style=flat-square">
<img src="https://img.shields.io/badge/Google%20Calendar-Supported-success?style=flat-square">
<img src="https://img.shields.io/badge/tests-536%20passing-brightgreen?style=flat-square">
<img src="https://img.shields.io/badge/mypy-strict-success?style=flat-square">
<img src="https://img.shields.io/badge/Coverage-%3E80%25-yellow?style=flat-square">
</p>

</div>

---

# ✨ Overview

Discord Gaming Automation Hub is a fully self-hosted Discord bot that continuously monitors the gaming ecosystem and automatically delivers:

- 🆓 Free games
- 💸 Historical-low discounts
- 🎮 Major game releases
- 📰 Important game updates
- 📈 Trending games
- 📅 Seasonal gaming events
- 🔎 Instant slash-command search
- 🎲 Personalized game suggestions

Everything runs on your own machine without relying on paid services or cloud hosting.

No Steam Web API key.
No monthly subscription.
No SaaS.

Just clone, configure `.env`, and run.

---

# ❤️ Why this project?

Unlike most Discord gaming bots, this project is designed to be:

- ✅ Completely self-hosted
- ✅ Open source (MIT)
- ✅ Easy to configure
- ✅ Powered only by free APIs
- ✅ Highly customizable
- ✅ Google Calendar integrated
- ✅ Scheduler driven
- ✅ Production-ready architecture

---

# ✨ Features

| Feature | Description |
|---------|-------------|
| 💸 Crazy Discounts | Automatically finds historical-low and high-percentage discounts across multiple stores |
| 🆓 Free Games | Weekly Epic Games free titles with upcoming giveaways |
| 📅 Gaming Calendar | Syncs releases, seasonal sales and major gaming events into Google Calendar |
| 🎮 Major Releases | Daily upcoming AAA & Indie releases |
| 📰 Major Updates | DLCs, patches, expansions and seasonal content |
| 📈 Trending Games | Weekly trending games collected from multiple providers |
| 🔎 `/search` | Search prices, stores and game information instantly |
| 🎲 `/surprise` | Random hidden gems and highly-rated recommendations |
| ⚙️ Environment Driven | Almost everything configurable from `.env` |
| 🌍 Open Source | MIT licensed |

---

# 📸 Screenshots

> Screenshots will be added soon.

```text
/search Hades

🎮 Hades
⭐ 93 Metacritic

💰 $24.99 → $12.49 (-50%)

🏪 Steam
🏪 Epic
🏪 GOG

📊 Historical Low:
$9.99

──────────────────────

View Deal
View Steam
```

---

# 📋 Requirements

- Python **3.12+**
- Linux / Windows / macOS
- Discord Bot Token
- (Optional) Google Calendar Service Account

Game information comes from free providers:

- Steam
- Epic Games
- CheapShark
- RAWG
- IsThereAnyDeal (optional)

---

# 🚀 Installation

## Linux

```bash
git clone https://github.com/TheCodeGalaxy/Discord-Gaming-Automation-Hub.git

cd Discord-Gaming-Automation-Hub

python3 -m venv .venv

source .venv/bin/activate

pip install -e ".[dev]"

cp .env.example .env

nano .env

python -m gaming_hub
```

---

## Windows PowerShell

```powershell
git clone https://github.com/TheCodeGalaxy/Discord-Gaming-Automation-Hub.git

cd Discord-Gaming-Automation-Hub

python -m venv .venv

.\.venv\Scripts\Activate.ps1

pip install -e ".[dev]"

Copy-Item .env.example .env

notepad .env

python -m gaming_hub
```

> **Tip**
>
> During the very first startup Discord may take several minutes (or up to one hour for global commands) before slash commands become visible.
> For development, configure `DISCORD_GUILD_ID` to enable instant command registration.

---

# ⚙️ Configuration

The bot is completely configured through the `.env` file.

Simply copy:

```bash
cp .env.example .env
```

Then edit only the values you need.

---

## Discord

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Discord bot token |
| `DISCORD_GUILD_ID` | Development guild (instant slash command sync) |
| `DISCORD_COMMAND_SYNC` | Synchronize application commands on startup |

---

## Channels

Configure where automated posts will be sent.

| Variable | Description |
|----------|-------------|
| `CHANNEL_FREE_GAMES` | Weekly free games |
| `CHANNEL_DISCOUNTS` | Crazy discounts |
| `CHANNEL_TOP_GAMES` | Trending games |
| `CHANNEL_MAJOR_UPDATES` | Major updates |
| `CHANNEL_COMING_SOON` | Upcoming releases |

---

## Google Calendar

Google Calendar integration is completely optional.

| Variable | Description |
|----------|-------------|
| `ENABLE_GOOGLE_CALENDAR` | Enable calendar synchronization |
| `GOOGLE_CALENDAR_ID` | Calendar ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account credentials |
| `GOOGLE_SYNC_YEARS_AHEAD` | Years to synchronize ahead |
| `GOOGLE_SYNC_ON_STARTUP` | Sync automatically when the bot starts |

---

## Scheduler

Every automatic task has its own cron expression.

Examples include:

- Hourly discounts
- Weekly free games
- Daily releases
- Daily major updates
- Weekly trending games
- Daily calendar synchronization

See `.env.example` for the complete list of available options.

---

# 📅 Google Calendar Integration

The bot can automatically synchronize important gaming events into Google Calendar, including:

- 🎮 Major game releases
- 💸 Steam seasonal sales
- 🎉 Gaming festivals
- 🕹️ Industry showcases
- 📅 Other seasonal gaming events

## Setup

### 1. Create a Service Account

Create a Google Cloud project and generate a Service Account.

### 2. Download the JSON credentials

Save the credentials securely.

### 3. Share your Calendar

Share your Google Calendar with the Service Account email and grant **Make changes to events**.

### 4. Copy the Calendar ID

Open:

**Google Calendar → Settings → Integrate Calendar**

Copy the Calendar ID.

### 5. Configure `.env`

```ini
ENABLE_GOOGLE_CALENDAR=true

GOOGLE_CALENDAR_ID=xxxxxxxxxxxxxxxx@group.calendar.google.com

GOOGLE_SERVICE_ACCOUNT_JSON=google-calendar.json
```

### 6. Synchronize

```bash
python -m gaming_hub calendar sync
```

Or simply enable

```ini
GOOGLE_SYNC_ON_STARTUP=true
```

and synchronization will happen automatically.

---

# ▶ Running

Start the complete application

```bash
python -m gaming_hub
```

Run only the API

```bash
python -m gaming_hub api
```

Synchronize Google Calendar

```bash
python -m gaming_hub calendar sync
```

Run tests

```bash
pytest
```

---

## Startup Sequence

When the application starts it automatically:

1. Connects to Discord
2. Registers Slash Commands
3. Initializes the Scheduler
4. Creates the local SQLite database (if needed)
5. Starts the FastAPI backend
6. Synchronizes Google Calendar (optional)

No manual intervention is required.

---

# 📂 Project Structure

```
src/
 ├── api/
 ├── automation/
 ├── calendar/
 ├── config/
 ├── core/
 ├── data/
 ├── discord_bot/
 ├── models/
 ├── services/
 └── utils/

tests/
docs/
scripts/
n8n/
```

The project follows a modular architecture where each package has a single responsibility.

---

# 🛠 Tech Stack

| Category | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Discord | discord.py |
| API | FastAPI |
| Database | SQLite + SQLAlchemy |
| Configuration | pydantic-settings |
| HTTP | httpx |
| Scheduler | APScheduler |
| Calendar | Google Calendar API |
| Testing | pytest |
| Type Checking | mypy |
| Linting | Ruff |
| Containers | Docker & Docker Compose |

---

# 🌐 Data Sources

This project intentionally relies on **free public APIs** whenever possible.

Current providers include:

- Steam Store
- Steam Community
- CheapShark
- Epic Games Store
- RAWG
- IsThereAnyDeal *(optional)*
- Google Calendar API

No paid APIs are required.

---

# 🤝 Contributing

Contributions are welcome.

If you'd like to improve the project:

1. Fork the repository.
2. Create a feature branch.
3. Implement your changes.
4. Run the test suite.
5. Submit a Pull Request.

Please keep code style consistent with Ruff and mypy strict mode.

---

# 🗺 Roadmap

Future improvements may include:

- Steam Wishlist synchronization
- Multiple Discord server profiles
- Localization support
- More gaming providers
- Better analytics
- Dashboard UI

---

# 📄 License

Distributed under the MIT License.

See the `LICENSE` file for details.

---

<div align="center">

### ⭐ If this project helped you, consider giving it a star!

Made with ❤️ for the Discord self-hosting and gaming communities.

</div>