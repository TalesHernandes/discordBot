import asyncio
import discord
from discord.ext import commands
import yt_dlp
import concurrent.futures

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!!', intents=intents)
voice_clients = {}
music_queues = {}
loop_status = {}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'outtmpl': '',
}


executor = concurrent.futures.ThreadPoolExecutor()


@bot.event
async def on_ready():
    print('Bot está pronto para ser utilizado!')


@bot.command(name='play')
async def play(ctx, *, query):
    voice_client = await connect_to_voice(ctx)
    guild_id = ctx.guild.id

    if guild_id not in music_queues:
        music_queues[guild_id] = []

    info_dict = await fetch_youtube_info(query, ctx)
    music_queues[guild_id].append(info_dict)
    await ctx.send(f'Musica adicionada na fila: `{info_dict["title"]} \n Duração: {info_dict["duration"]}`')

    if not voice_client.is_playing():
        await play_music(ctx, voice_client)


async def fetch_youtube_info(query, ctx):
    loop_ = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if query.startswith('http'):
            return await loop_.run_in_executor(executor, ydl.extract_info, query, False)
        else:
            await ctx.send(f'Procurando `{query}`')
            result = await loop_.run_in_executor(executor, ydl.extract_info, f"ytsearch:{query}")
            return result['entries'][0]


async def connect_to_voice(ctx):
    guild_id = ctx.guild.id
    if guild_id not in voice_clients or not voice_clients[guild_id].is_connected():
        channel = ctx.author.voice.channel
        voice_clients[guild_id] = await channel.connect()
    return voice_clients[guild_id]


async def play_music(ctx, voice_client):
    guild_id = ctx.guild.id

    while music_queues[guild_id]:
        info_dict = music_queues[guild_id].pop(0)
        voice_client.play(discord.FFmpegPCMAudio(info_dict['url'], **ffmpeg_options))
        await ctx.send(f'Tocando: `{info_dict["title"]} \n Duração: {info_dict["duration"]}`')

        while voice_client.is_playing():
            await asyncio.sleep(1)

        if loop_status.get(guild_id, False):
            music_queues[guild_id].append(info_dict)

    await asyncio.sleep(120)
    if not voice_client.is_playing():
        await voice_client.disconnect()


@bot.command(name='stop')
async def stop(ctx):
    guild_id = ctx.guild.id
    if guild_id in voice_clients:
        await voice_clients[guild_id].disconnect()
        voice_clients.pop(guild_id, None)
        music_queues.pop(guild_id, None)


@bot.command(name='skip')
async def skip(ctx):
    guild_id = ctx.guild.id
    if guild_id in voice_clients:
        voice_clients[guild_id].stop()


@bot.command(name='loop')
async def loop(ctx):
    guild_id = ctx.guild.id
    loop_status[guild_id] = not loop_status.get(guild_id, False)
    await ctx.send(f'Modo de loop {"ativado" if loop_status[guild_id] else "desativado"}.')

bot.run('TOKEN')
