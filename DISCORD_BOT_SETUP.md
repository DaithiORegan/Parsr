# Run the application tracker on your PC

The twice-daily scanner stays on GitHub Actions. This bot runs only while your PC, internet connection and bot window are on. It does not need paid hosting. It adds tracking buttons to existing job webhook posts in your three monitored channels.

## What it does

- Creates **jobs-applied-for** when first started, unless an existing channel ID is configured. The new channel copies permissions/category from one monitored channel.
- Replies to job posts with **Apply & record: [job title]** buttons. This is a button row, not a second copy of the job advert.
- Clicking the button records the job once per user, then privately provides **Open application website**. The channel says **Application opened — submission not verified**.
- Remembers buttons and application records across restarts in `data/discord-bot.sqlite3`.
- On startup, checks the most recent 500 messages per monitored channel and adds missing buttons. Type `!syncjobs` in a monitored channel to repeat that catch-up check.
- Only configured user IDs can record clicks. Other users are refused.

**Discord does not report clicks on ordinary embed links or link-style buttons.** Use **Apply & record** to track a job; clicking the old **Apply for this job** link or the embed title cannot be detected. A link clicked while the bot is offline cannot be reconstructed later. Buttons already posted work again after the bot reconnects.

## 1. Create a Discord application and bot

Go to https://discord.com/developers/applications and select **New Application**. Name it, for example, **Job Application Tracker**.

Open **Bot** and create/reset its token. Store that token only in your PC's `.env` file. Do not paste it into chat or commit it to GitHub.

Under the bot's privileged gateway intents, enable **Message Content Intent**. Member and presence intents are not needed.

In **OAuth2 → URL Generator**, choose the **bot** scope. Grant:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Manage Channels (only needed if the bot creates jobs-applied-for)

Use the generated invitation link to add it to your server. Administrator permission is not needed. If you create jobs-applied-for yourself, provide its channel ID and omit Manage Channels.

## 2. Copy your server, channel and user IDs

In Discord, enable **Settings → Advanced → Developer Mode**.

Right-click your server and copy its ID. Copy IDs for job-alerts, job-alerts-cork and apply-now. Right-click your own account and copy your user ID.

The bot needs permission to view/send/read history in each source channel and jobs-applied-for. In restricted channels, adjust the channel's permission overrides for the bot role.

## 3. Configure your local copy

Download the repository's ZIP from GitHub's **Code → Download ZIP**, or clone it. Extract it fully. Install Python 3.12 or newer.

Copy `.env.example` to `.env` beside `discord_bot.py`. Fill in these entries:

```dotenv
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_GUILD_ID=your_server_id
DISCORD_MONITORED_CHANNEL_IDS=general_channel_id,cork_channel_id,apply_now_channel_id
DISCORD_ALLOWED_USER_IDS=your_user_id
DISCORD_APPLIED_CHANNEL_ID=
```

Leave DISCORD_APPLIED_CHANNEL_ID blank for automatic creation, or set the existing channel's ID. Use numeric IDs without angle brackets. For this PC bot, you do not need the scanner's webhooks or Jooble key: those remain in GitHub secrets.

Never publish `.env`, `.bot-venv` or the SQLite database. They are ignored by Git.

## 4. Start it

On Windows, double-click **START_DISCORD_BOT.bat**. It creates a local environment, installs dependencies and starts the bot. Keep its window open. Ctrl+C stops it.

On macOS/Linux:

```sh
python3 -m venv .bot-venv
.bot-venv/bin/python -m pip install -r requirements-bot.txt
.bot-venv/bin/python discord_bot.py
```

When it reports **Application tracker online**, check apply-now for the tracking buttons. Click **Apply & record** on a job; verify one record appears in jobs-applied-for and that the private application-site button works. Click it again: no second record should be created.

If startup fails, check the token, numeric IDs, Message Content Intent and channel permissions. If you move the folder or reinstall, preserve `data/discord-bot.sqlite3`; deleting it removes local tracking history. Run a single bot instance per database.

## Scanner duplicate prevention

Reports, new-job alerts and manual backfills share `delivered_by_channel` in the scanner's `data/state.json`. The same job can appear once in each relevant channel, but successful deliveries are not repeated in that channel. Canonical application URLs and exact normalised employer/title/location identities are used, including duplicates within the same source.

On first upgrade, jobs in the pre-upgrade index are treated as historical to avoid replaying the existing adverts. Newly discovered jobs are still delivered. Local CSV exports remain complete; no files are attached to Discord. Existing duplicate messages are not deleted.

Report batches are checkpointed after each successful Discord response. The workflow saves partial successful history even if a later send fails, and concurrent state merges union that history. As with any external HTTP service, an accepted send whose response is lost can remain ambiguous; avoid repeatedly forcing manual retries after network timeouts.

Duplicate filtering runs on GitHub and works while your PC is off. Bot tokens and bot hosting do not need to be added to GitHub for this setup.

## Verification performed

Offline regression tests cover duplicate report suppression, partial batch success, delivery migration, application records across restarts, allowed-user checks, repeated clicks and Discord log failures. A live Discord login/channel-creation/click test requires your local bot token and IDs; it has not been performed by the assistant.
