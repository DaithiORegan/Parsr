"""Run on your PC: attach tracking buttons to job webhooks and record clicks."""
import asyncio
import json
import os
from pathlib import Path
import discord
from dotenv import load_dotenv
from job_monitor.bot_store import Store, jobs_from_embeds

BASE=Path(__file__).resolve().parent
load_dotenv(BASE/'.env')

def required(name):
    value=os.getenv(name,'').strip()
    if not value:raise ValueError('Set '+name+' in your local .env file')
    return value

def ids(name):
    result={int(x.strip()) for x in required(name).split(',') if x.strip()}
    if not result:raise ValueError('Set '+name)
    return result

class ApplyButton(discord.ui.Button):
    def __init__(self,job,index):
        super().__init__(label=('Apply & record: '+job['title'])[:80],style=discord.ButtonStyle.primary,
                         custom_id='jobapply:'+job['key'],row=index//5)
        self.job_key=job['key']
    async def callback(self,interaction):
        await interaction.client.record_application(interaction,self.job_key)

class ApplyView(discord.ui.View):
    def __init__(self,jobs):
        super().__init__(timeout=None)
        for i,job in enumerate(jobs[:10]):self.add_item(ApplyButton(job,i))

class Tracker(discord.Client):
    def __init__(self):
        intents=discord.Intents.default()
        intents.message_content=True
        super().__init__(intents=intents,allowed_mentions=discord.AllowedMentions.none())
        self.guild_id=int(required('DISCORD_GUILD_ID'))
        self.monitored_channels=ids('DISCORD_MONITORED_CHANNEL_IDS')
        self.allowed_users=ids('DISCORD_ALLOWED_USER_IDS')
        (BASE/'data').mkdir(exist_ok=True)
        self.store=Store(BASE/'data/discord-bot.sqlite3')
        self.message_lock=asyncio.Lock()
        self.apply_lock=asyncio.Lock()
        self.started=False
    async def on_ready(self):
        if self.started:return
        self.started=True
        try:
            guild=self.get_guild(self.guild_id)
            if not guild:raise ValueError('Bot must be invited to DISCORD_GUILD_ID')
            log_id=os.getenv('DISCORD_APPLIED_CHANNEL_ID','').strip()
            self.applied=guild.get_channel(int(log_id)) if log_id else discord.utils.get(guild.text_channels,name='jobs-applied-for')
            if not self.applied:
                source=guild.get_channel(next(iter(self.monitored_channels)))
                if not source:raise ValueError('Monitored channel not accessible')
                self.applied=await guild.create_text_channel('jobs-applied-for',category=source.category,
                    overwrites=source.overwrites,reason='User-requested application tracking')
            if not isinstance(self.applied,discord.TextChannel) or self.applied.id in self.monitored_channels:
                raise ValueError('jobs-applied-for must be a separate text channel')
            for message_id,job_keys in self.store.companions():
                jobs=[self.store.job(k) for k in json.loads(job_keys)]
                self.add_view(ApplyView([j for j in jobs if j]),message_id=int(message_id))
            await self.sync_history()
            print('Application tracker online. Use the Apply & record buttons; ordinary links cannot be tracked.')
        except Exception as exc:
            print('Startup failed:',type(exc).__name__,'— check channel permissions and .env IDs.')
            await self.close()
    async def sync_history(self):
        for channel_id in self.monitored_channels:
            channel=self.get_channel(channel_id)
            if not isinstance(channel,discord.TextChannel) or channel.guild.id!=self.guild_id:
                raise ValueError('Invalid monitored channel')
            messages=[m async for m in channel.history(limit=500)]
            recovered={m.reference.message_id:m for m in messages if m.author.id==self.user.id and m.reference}
            for message in reversed(messages):
                await self.track_message(message,recovered.get(message.id))
    async def track_message(self,message,recovered=None):
        if not message.guild or message.guild.id!=self.guild_id or message.channel.id not in self.monitored_channels:return
        if not message.webhook_id:return
        async with self.message_lock:
            if self.store.companion(message.id):return
            known=self.store.tracked_jobs(message.channel.id)
            jobs=[j for j in jobs_from_embeds([e.to_dict() for e in message.embeds]) if j['key'] not in known]
            if not jobs:return
            self.store.save_jobs(jobs,message.jump_url)
            companion=recovered or await message.reply('Use these buttons to record an application-link click. Submission is not verified.',
                  view=ApplyView(jobs),mention_author=False)
            self.store.save_companion(message.id,companion.id,jobs,message.channel.id)
    async def on_message(self,message):
        if not self.started or not hasattr(self,'applied'):return
        try:
            if message.author.id in self.allowed_users and message.channel.id in self.monitored_channels and message.content.strip()=='!syncjobs':
                await self.sync_history()
                await message.reply('Recent job posts checked.',mention_author=False)
            else:await self.track_message(message)
        except Exception as exc:
            print('Tracking failed:',type(exc).__name__,'— reconnect or use !syncjobs to retry.')
    async def record_application(self,interaction,key):
        if interaction.guild_id!=self.guild_id or interaction.channel_id not in self.monitored_channels or interaction.user.id not in self.allowed_users:
            await interaction.response.send_message('This tracker is not configured for your account or channel.',ephemeral=True)
            return
        job=self.store.job(key)
        if not job:
            await interaction.response.send_message('Job data is missing. Ask the bot owner to sync recent posts.',ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True,thinking=True)
        recorded=False
        try:
            async with self.apply_lock:
                existing=self.store.application(interaction.user.id,key)
                if existing:
                    recorded=True
                else:
                    marker='Opened:'+str(interaction.user.id)+':'+key
                    recovered=None
                    # Recover an accepted send if its response/DB checkpoint was lost.
                    async for previous in self.applied.history(limit=500):
                        if previous.author.id==self.user.id and any(e.footer.text==marker for e in previous.embeds):
                            recovered=previous;break
                    if not recovered:
                        embed=discord.Embed.from_dict(job['embed'])
                        embed.set_footer(text=marker)
                        recovered=await self.applied.send(
                            content=f'**Application opened — submission not verified**\nUser: {interaction.user}\nOriginal post: {job["source_url"]}',
                            embed=embed)
                    self.store.mark_application(interaction.user.id,key,recovered.id)
                    recorded=True
        except Exception as exc:
            print('Application log failed:',type(exc).__name__)
        view=discord.ui.View()
        view.add_item(discord.ui.Button(label='Open application website',url=job['url']))
        text=('Recorded in '+self.applied.mention+'. Opening a link does not confirm submission.' if recorded else
              'Could not confirm the channel record. Click Apply & record again to retry. You can still open the job below.')
        await interaction.followup.send(text,view=view,ephemeral=True)

if __name__=='__main__':
    try:
        token=required('DISCORD_BOT_TOKEN')
        bot=Tracker()
        bot.run(token,log_handler=None)
    except Exception as exc:
        print('Bot stopped:',type(exc).__name__,'— check .env, token, internet access and Discord intents.')
        raise SystemExit(1)
