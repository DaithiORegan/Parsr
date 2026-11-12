import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
import discord_bot
from job_monitor.bot_store import jobs_from_embeds

async def no_history(**kwargs):
    if False:yield None

class Clicks(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_click_only_logs_once_and_provides_real_application_url(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(discord_bot,'BASE',Path(tmp)),patch.dict(discord_bot.os.environ,{'DISCORD_GUILD_ID':'1','DISCORD_MONITORED_CHANNEL_IDS':'2','DISCORD_ALLOWED_USER_IDS':'9'}):
            bot=discord_bot.Tracker();bot._connection.user=SimpleNamespace(id=99)
            bot.applied=SimpleNamespace(mention='#jobs-applied-for',history=no_history,send=AsyncMock(return_value=SimpleNamespace(id=101)))
            job=jobs_from_embeds([{'title':'Support','url':'https://example.com/job/1','description':'Employer · Cork'}])[0]
            bot.store.save_jobs([job],'https://discord.com/channels/1/2/3')
            interaction=SimpleNamespace(guild_id=1,channel_id=2,user=SimpleNamespace(id=9),response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
            await bot.record_application(interaction,job['key'])
            await bot.record_application(interaction,job['key'])
            self.assertEqual(bot.applied.send.await_count,1)
            self.assertEqual(bot.store.application(9,job['key']),'101')
            view=interaction.followup.send.call_args.kwargs['view']
            self.assertEqual(view.children[0].url,'https://example.com/job/1')
            interaction.user=SimpleNamespace(id=10)
            await bot.record_application(interaction,job['key'])
            interaction.response.send_message.assert_awaited_once()
            self.assertEqual(bot.applied.send.await_count,1)
            bot.store.db.close();await bot.close()
    async def test_discord_failure_does_not_claim_logged(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(discord_bot,'BASE',Path(tmp)),patch.dict(discord_bot.os.environ,{'DISCORD_GUILD_ID':'1','DISCORD_MONITORED_CHANNEL_IDS':'2','DISCORD_ALLOWED_USER_IDS':'9'}):
            bot=discord_bot.Tracker();bot._connection.user=SimpleNamespace(id=99)
            bot.applied=SimpleNamespace(mention='#jobs-applied-for',history=no_history,send=AsyncMock(side_effect=RuntimeError('offline')))
            job=jobs_from_embeds([{'title':'Support','url':'https://example.com/job/1','description':'Employer · Cork'}])[0]
            bot.store.save_jobs([job],'https://discord.com/channels/1/2/3')
            interaction=SimpleNamespace(guild_id=1,channel_id=2,user=SimpleNamespace(id=9),response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
            await bot.record_application(interaction,job['key'])
            self.assertIsNone(bot.store.application(9,job['key']))
            self.assertIn('Could not confirm',interaction.followup.send.call_args.args[0])
            bot.store.db.close();await bot.close()
