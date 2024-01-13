import asyncio
import discord
from discord.ext import commands
import yt_dlp
import os
import re

intents = discord.Intents.default()
intents.message_content = True

# Crie uma instância do bot
bot = commands.Bot(command_prefix='!!', intents=intents)
global music_playing
voice_channels = {}
music_queues = {}
ydl_opts_flat = {
    'extract_flat': True,
}
global music_playing
music_playing = {}
global loop_status
loop_status = {}


@bot.event
async def on_ready():
    await bot.loop.create_task(cleanup_downloads())
    print('Bot está pronto para ser utilizado!')


@bot.command(name='loop')
async def loop(ctx):
    global loop_status

    guild_id = ctx.guild.id

    # Verifique se o modo de loop já está ativado para este servidor
    if guild_id in loop_status and loop_status[guild_id]:
        # Se o modo de loop estiver ativado, desative-o
        loop_status[guild_id] = False
        await ctx.send('Modo de loop desativado.')
    else:
        # Se o modo de loop estiver desativado, ative-o
        loop_status[guild_id] = True
        await ctx.send('Modo de loop ativado.')


@bot.command(name='play')
async def play(ctx, *, query):
    global voice_channels
    global music_queues

    guild_id = ctx.guild.id

    # Verifique se a fila de música para o servidor atual existe, se não, crie uma
    if guild_id not in music_queues:
        music_queues[guild_id] = []

    # Verifique se a consulta é uma URL
    if not query.startswith('http'):
        # Se não for uma URL, pesquise no YouTube
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            url = info['entries'][0]['id']
    else:
        url = query

    # Verifique se a URL é uma playlist do YouTube
    if 'list=' in url and 'v=' not in url:
        # Se for uma playlist, baixe todas as músicas da playlist
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info = ydl.extract_info(url, download=False)
            for entry in info['entries']:
                music_queues[guild_id].append(entry['id'])
    else:
        # Se não for uma playlist, adicione a música à fila
        if guild_id in voice_channels and voice_channels[guild_id].is_playing():
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                info = ydl.extract_info(url, download=False)
                song_title = info.get('title', None)
                song_duration = info.get('duration', None)

            await ctx.send(f'Música adicionada: `{song_title}`\nDuração: `{song_duration}` segundos')

        if guild_id not in music_queues:
            music_queues[guild_id] = []
        music_queues[guild_id].append(url)

    # Se uma música já estiver tocando, não faça mais nada
    if guild_id in voice_channels and voice_channels[guild_id].is_playing():
        return

    # Conecte-se ao canal de voz do usuário
    channel = ctx.message.author.voice.channel
    if guild_id not in voice_channels or (guild_id in voice_channels and not voice_channels[guild_id].is_connected()):
        voice_channels[guild_id] = await channel.connect()

    # Comece a tocar as músicas na fila
    await play_music(ctx)


async def play_music(ctx):
    global voice_channels
    global music_queues
    global music_playing
    global loop_status

    guild_id = ctx.guild.id

    while len(music_queues[guild_id]) > 0:
        url = music_queues[guild_id].pop(0)

        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            song_title = info_dict.get('title', None)
            song_title = re.sub('[^A-Za-z0-9 ]+', '', song_title)
            song_title = song_title.replace(' ', '_')
            music_playing = song_title
            song_duration = info_dict.get('duration', None)
            print("ESSA MERDA PASSA AQUI 2?")

        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'downloads/{song_title}',
        }

        # Baixe o áudio do vídeo do YouTube
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            print("ESSA MERDA PASSA AQUI 3?")

        # Reproduza o áudio baixado
        voice_channels[guild_id].play(discord.FFmpegPCMAudio(executable="ffmpeg", source=f'downloads/{song_title}.mp3'))

        # Enviar uma mensagem com o nome da música
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            song_title = info_dict.get('title', None)
        if len(music_queues[guild_id]) > 0:
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                next_info_dict = ydl.extract_info(music_queues[guild_id][0], download=False)
                next_title = next_info_dict.get('title', None)
            await ctx.send(f'Tocando: `{song_title}`\nDuração: `{song_duration}` segundos\nPróxima música: '
                           f'`{next_title}`')
        else:
            await ctx.send(f'Tocando: `{song_title}`\nDuração: `{song_duration}` segundos.')

        # Aguarde até que o áudio termine de tocar, depois desconecte
        while voice_channels[guild_id].is_playing():
            await asyncio.sleep(1)

        while guild_id in loop_status and loop_status[guild_id]:
            voice_channels[guild_id].play(
                discord.FFmpegPCMAudio(executable="ffmpeg", source=f'downloads/{music_playing}.mp3'))
            while voice_channels[guild_id].is_playing():
                await asyncio.sleep(1)

        # Remova o arquivo de áudio
        if os.path.exists(f'downloads/{song_title}.mp3'):
            os.remove(f'downloads/{song_title}.mp3')

    if len(music_queues[guild_id]) == 0:
        await asyncio.sleep(120)
        await voice_channels[guild_id].disconnect()


@bot.command(name='stop')
async def stop(ctx):
    global voice_channels
    global music_queues

    guild_id = ctx.guild.id

    if guild_id in voice_channels:
        voice_channels[guild_id].stop()
        await voice_channels[guild_id].disconnect()
        del voice_channels[guild_id]
        music_queues[guild_id].clear()

    if os.path.exists(f'downloads/{music_playing}.mp3'):
        os.remove(f'downloads/{music_playing}.mp3')


@bot.command(name='skip')
async def skip(ctx):
    global voice_channels
    global music_queues

    guild_id = ctx.guild.id

    if guild_id in voice_channels:
        # Pare a música atual
        voice_channels[guild_id].stop()

        # Se não houver mais músicas na fila, pare a reprodução
        if len(music_queues[guild_id]) == 0:
            await stop(ctx)


async def cleanup_downloads():
    while True:
        # Aguarde 5 minutos
        await asyncio.sleep(300)

        # Obtenha uma lista de todas as músicas atualmente tocando
        currently_playing = [f'downloads/{song}.mp3' for song in music_playing.values()]

        # Obtenha uma lista de todos os arquivos na pasta de downloads
        downloads = os.listdir('downloads')

        for file in downloads:
            # Se o arquivo não estiver sendo reproduzido atualmente, exclua-o
            if file not in currently_playing:
                os.remove(f'downloads/{file}')

# Inicie o bot
bot.run('MTE5NTIwMzI2NTQ1Mzg5MTYyNQ.GhXhLD.v7aqRhijHlQwj7-txefWvuTCM3yWfY8OBIRfAQ')
