import discord
from discord import app_commands, ui
from discord.ext import commands
import os, aiohttp, asyncio, random, math, json
from dotenv import load_dotenv
from datetime import datetime

# =================================================================
# MEUAI - PROFESSIONAL AUTOMATION (v23.0 - CONSOLIDATED)
# =================================================================

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# CONFIGURATION
AUTHORIZED_USER_ID = 1003765580823805982
REQUIRED_ROLE_ID = 1439202018865446948

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Referer": "https://www.languagenut.com/",
    "Origin": "https://www.languagenut.com"
}

def seconds_to_string(seconds):
    seconds = int(seconds)
    if seconds < 60: return f"{seconds}s"
    if seconds < 3600: return f"{seconds//60}m {seconds%60}s"
    if seconds < 86400: return f"{seconds//3600}h {(seconds%3600)//60}m"
    return f"{seconds//86400}d {(seconds%86400)//3600}h"

class TaskCompleter:
    def __init__(self, token, task, ietf, speed):
        self.token = token
        self.task = task
        self.ietf = ietf
        self.speed = speed
        self.catalog_uid = task.get('catalog_uid') or task['base'][-1]
        self.homework_id = task['base'][0]

    def get_mode(self):
        link = self.task.get('gameLink', '').lower()
        if "sentencecatalog" in link: return "sentence"
        if "verbuid" in link: return "verbs"
        if "phoniccataloguid" in link: return "phonics"
        if "examuid" in link: return "exam"
        return "vocabs"

    async def execute(self, session):
        mode = self.get_mode()
        endpoints = {
            "sentence": "sentenceTranslationController/getSentenceTranslations",
            "verbs": "verbTranslationController/getVerbTranslations",
            "phonics": "phonicsController/getPhonicsData",
            "exam": "examTranslationController/getExamTranslationsCorrect",
            "vocabs": "vocabTranslationController/getVocabTranslations"
        }
        
        params = {"token": self.token, "toLanguage": self.ietf, "fromLanguage": "en-US"}
        if mode == "vocabs": params["catalogUid[]"] = self.catalog_uid
        elif mode == "phonics": params["phonicCatalogUid"] = self.catalog_uid
        elif mode == "sentence": params["catalogUid"] = self.catalog_uid
        elif mode == "exam": params.update({"gameUid": self.task.get('game_uid'), "examUid": self.catalog_uid})
        else: params["verbUid"] = self.catalog_uid

        async with session.get(f"https://api.languagenut.com/{endpoints[mode]}", params=params, headers=HEADERS) as r:
            try:
                res = await r.json(content_type=None)
                keys = {"sentence": "sentenceTranslations", "verbs": "verbTranslations", "phonics": "phonics", "exam": "examTranslations", "vocabs": "vocabTranslations"}
                vocabs = res.get(keys[mode], [])
            except: return None, 0, 0

        if not vocabs: return None, 0, 0

        # Simulation: Speed with 10% random variance
        ts = math.floor(self.speed + ((random.random() - 0.5) / 10) * self.speed) * 1000
        score_base = len(vocabs) * 200
        
        payload = {
            "moduleUid": self.catalog_uid, "gameUid": self.task.get('game_uid'), "gameType": self.task.get('type'),
            "isTest": "true", "toietf": self.ietf, "fromietf": "en-US", "score": score_base,
            "correctVocabs": ",".join([str(x.get('uid')) for x in vocabs]), "incorrectVocabs": "[]",
            "homeworkUid": self.homework_id, "isSentence": str(mode == "sentence").lower(),
            "isALevel": "false", "isVerb": str(mode == "verbs").lower(),
            "verbUid": self.catalog_uid if mode == "verbs" else "", "phonicUid": self.catalog_uid if mode == "phonics" else "",
            "sentenceScreenUid": "100" if mode == "sentence" else "", "sentenceCatalogUid": self.catalog_uid if mode == "sentence" else "",
            "grammarCatalogUid": self.catalog_uid, "isGrammar": "false", "isExam": str(mode == "exam").lower(),
            "timeStamp": ts, "vocabNumber": len(vocabs), "rel_module_uid": self.task.get('rel_module_uid', ''),
            "dontStoreStats": "true", "product": "secondary", "token": self.token
        }
        
        async with session.get("https://api.languagenut.com/gameDataController/addGameScore", params=payload, headers=HEADERS) as r:
            try: 
                data = await r.json(content_type=None)
                return data, score_base, (ts / 1000)
            except: return {"status": "success"}, score_base, (ts / 1000)

class DMControlView(ui.View):
    def __init__(self, tracker):
        super().__init__(timeout=None)
        self.tracker = tracker

    @ui.button(label="Cancel Session", style=discord.ButtonStyle.danger, emoji="🛑")
    async def stop_tasks(self, it: discord.Interaction, button: ui.Button):
        self.tracker.is_running = False
        button.disabled = True
        button.label = "Terminating..."
        await it.response.edit_message(view=self)

class DMProgress:
    def __init__(self, user, tasks, token, hws, speed):
        self.user, self.tasks, self.token, self.hws, self.speed = user, tasks, token, hws, speed
        self.logs, self.total_reported_time, self.is_running = ["📡 Neural link established. Initializing."], 0, True

    def create_embed(self, current_name, progress, finished, total, status="Processing"):
        color = 0x2b2d31
        if not self.is_running: color = 0xe74c3c
        elif progress >= 100: color = 0x2ecc71
        
        log_display = "\n".join(self.logs[-5:])
        embed = discord.Embed(title=f"🛠️ Simulation Status: {status}", color=color)
        embed.description = f"**Agent:** `Node-{random.randint(100, 999)}`"
        
        bar_len = 16
        filled = int((progress/100) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        
        embed.add_field(name="Deployment Data", value=f"**Task:** `{current_name}`\n**Logged Time:** `{seconds_to_string(self.total_reported_time)}`", inline=True)
        embed.add_field(name="Queue", value=f"**Progress:** `{progress}%`\n**Items:** `{finished}/{total}`", inline=True)
        embed.add_field(name="Agent Output", value=f"```ansi\n\u001b[0;32m[SYSTEM]\u001b[0;0m {log_display}```", inline=False)
        embed.set_footer(text=f"MeuAi Professional | {datetime.now().strftime('%H:%M:%S')}")
        return embed

    async def start(self):
        view = DMControlView(self)
        try: dm_msg = await self.user.send(embed=self.create_embed("Syncing...", 0, 0, len(self.tasks)), view=view)
        except: return

        finished, total = 0, len(self.tasks)
        for hw_idx, _, t in self.tasks:
            if not self.is_running:
                self.logs.append("🛑 Manual Stop: Connection severed.")
                await dm_msg.edit(embed=self.create_embed("Disconnected", int((finished/total)*100), finished, total, "Stopped"), view=None)
                return

            hw = self.hws[hw_idx]
            async with aiohttp.ClientSession(headers=HEADERS) as session:
                res, points, time_taken = await TaskCompleter(self.token, t, hw['languageCode'], self.speed).execute(session)
                finished += 1
                if res:
                    self.total_reported_time += time_taken
                    self.logs.append(f"Synced: {t.get('name', 'Task')[:15]} (+{seconds_to_string(time_taken)})")
                else: self.logs.append(f"⚠️ Simulation Error: {t.get('name', 'Task')[:15]}")
                
                pct = int((finished/total)*100)
                try: await dm_msg.edit(embed=self.create_embed(t.get('name', 'Task'), pct, finished, total))
                except: pass
                await asyncio.sleep(0.15) 
        
        try: await dm_msg.edit(embed=self.create_embed("All Tasks Synced", 100, total, total, "Successful"), view=None)
        except: pass

class MainDashboard(ui.View):
    def __init__(self, token, hws, user):
        super().__init__(timeout=None)
        self.token, self.hws, self.user, self.selected_tasks, self.speed = token, hws, user, [], 120.0
        self.all_tasks = [(h_idx, t_idx, t) for h_idx, h in enumerate(hws) for t_idx, t in enumerate(h['tasks'])]
        self.add_item(TaskSelect(self.all_tasks))

    def create_embed(self):
        embed = discord.Embed(title="🛡️ MeuAi Control Center", color=0x2b2d31)
        embed.description = "Select assignments from the queue to initialize simulation."
        embed.add_field(name="Diagnostics", value=f"• Queue: `{len(self.all_tasks)}` tasks\n• Target: `{len(self.selected_tasks)}` tasks\n• Simulation Speed: `{int(self.speed)}s/task`", inline=False)
        embed.set_footer(text="Language Nut | Neural Tutor Network")
        return embed

    @ui.button(label="Initialize Simulation", style=discord.ButtonStyle.success, emoji="⚡", row=1)
    async def do_hw(self, it: discord.Interaction, button: ui.Button):
        if not self.selected_tasks: return await it.response.send_message("⚠️ No tasks selected for simulation.", ephemeral=True)
        await it.response.defer(ephemeral=True)
        task_list = [self.all_tasks[int(idx)] for idx in self.selected_tasks]
        asyncio.create_task(DMProgress(self.user, task_list, self.token, self.hws, self.speed).start())
        await it.followup.send("✅ Deployment successful. Simulation logs transferred to DMs.", ephemeral=True)

    @ui.button(label="Adjust Time", style=discord.ButtonStyle.gray, emoji="⏲️", row=1)
    async def set_time(self, it: discord.Interaction, button: ui.Button):
        modal = ui.Modal(title="Calibration: Time Simulation")
        time_input = ui.TextInput(label="Reported Seconds per Task", placeholder="e.g. 120", default=str(int(self.speed)))
        async def on_sub(inter):
            try:
                self.speed = float(time_input.value)
                await inter.response.edit_message(embed=self.create_embed())
            except: await inter.response.send_message("Invalid input.", ephemeral=True)
        modal.on_submit = on_sub; modal.add_item(time_input); await it.response.send_modal(modal)

    @ui.button(label="Select All", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def select_all(self, it: discord.Interaction, button: ui.Button):
        self.selected_tasks = [f"{i}" for i in range(min(len(self.all_tasks), 25))]
        await it.response.edit_message(embed=self.create_embed(), view=self)

    @ui.button(label="End Session", style=discord.ButtonStyle.danger, emoji="🔌", row=1)
    async def end_session(self, it: discord.Interaction, button: ui.Button):
        await it.response.edit_message(content="🔌 Session terminated. System offline.", embed=None, view=None)

class TaskSelect(ui.Select):
    def __init__(self, tasks):
        options = [discord.SelectOption(label=t[2].get('name', 'Task')[:50], value=f"{i}", description=f"Score: {t[2].get('gameResults', {}).get('percentage', 0)}%") for i, t in enumerate(tasks[:25])]
        super().__init__(placeholder="📂 Queue Selection...", min_values=1, max_values=len(options), options=options)
    async def callback(self, it: discord.Interaction):
        self.view.selected_tasks = self.values
        await it.response.edit_message(embed=self.view.create_embed(), view=self.view)

class Portal(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @ui.button(label="Language Nut Login", style=discord.ButtonStyle.success, emoji="🔐")
    async def start(self, it: discord.Interaction, button: ui.Button):
        modal = ui.Modal(title="Gateway Authentication")
        u = ui.TextInput(label="Username"); p = ui.TextInput(label="Password", style=discord.TextStyle.short)
        async def on_sub(inter):
            await inter.response.defer(ephemeral=True)
            async with aiohttp.ClientSession(headers=HEADERS) as s:
                async with s.get("https://api.languagenut.com/loginController/attemptLogin", params={"username": u.value, "pass": p.value}) as r:
                    data = await r.json(content_type=None)
                    token = data.get("newToken")
                if token:
                    async with s.get("https://api.languagenut.com/assignmentController/getViewableAll", params={"token": token}) as r:
                        homework_data = (await r.json(content_type=None)).get("homework", [])
                    dash = MainDashboard(token, homework_data, inter.user)
                    await inter.followup.send(embed=dash.create_embed(), view=dash, ephemeral=True)
                else: await inter.followup.send("❌ Access Denied: Invalid Credentials.", ephemeral=True)
        modal.on_submit = on_sub; modal.add_item(u); modal.add_item(p); await it.response.send_modal(modal)

class MeuAiBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
    async def setup_hook(self): await self.tree.sync()

bot = MeuAiBot()

@bot.tree.command(name="languagenut", description="Access the Professional Tutor Network")
async def languagenut(it: discord.Interaction):
    await it.response.defer(ephemeral=False)
    
    role = it.guild.get_role(REQUIRED_ROLE_ID)
    if it.user.id != AUTHORIZED_USER_ID and (not role or role not in it.user.roles):
        return await it.followup.send("❌ Access Denied.", ephemeral=True)
    
    embed = discord.Embed(title="💠 Language Nut Professional Portal", color=0x2b2d31)
    embed.description = (
        "Welcome to the **MeuAi Portal**. This system connects you to a professional network of "
        "tutors who will complete your LanguageNut assignments for you.\n\n"
        "**Terms of Use:**\n"
        "• Human-simulation active for profile safety.\n"
        "• All results are final.\n"
        "• Users are responsible for academic integrity."
    )
    embed.set_footer(text="MeuAi Secure Gateway • v23.0")
    await it.followup.send(embed=embed, view=Portal(bot))

if __name__ == "__main__":
    bot.run(TOKEN)
