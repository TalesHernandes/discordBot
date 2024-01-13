import asyncio
import discord
from discord.ext import commands
import yt_dlp
import os
import re

intents = discord.Intents.default()
intents.message_content = True

# Crie uma instância do bot
bot = commands.Bot(command_prefix='!', intents=intents)
global music_playing
voice_channel = None
music_queue = []
ydl_opts_flat = {
    'extract_flat': True,
}


@bot.event
async def on_ready():
    print('Bot está pronto para ser utilizado!')


@bot.command(name='playYT')
async def play(ctx, *, query):
    global voice_channel
    global music_queue

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
                music_queue.append(entry['id'])
    else:
        # Se não for uma playlist, adicione a música à fila
        if voice_channel is not None and voice_channel.is_playing():
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                info = ydl.extract_info(url, download=False)
                song_title = info.get('title', None)
                song_duration = info.get('duration', None)

            await ctx.send(f'Música adicionada: `{song_title}`\nDuração: `{song_duration}` segundos')

        music_queue.append(url)

    # Se uma música já estiver tocando, não faça mais nada
    if voice_channel is not None and voice_channel.is_playing():
        return

    # Conecte-se ao canal de voz do usuário
    channel = ctx.message.author.voice.channel
    if voice_channel is None or not voice_channel.is_connected():
        voice_channel = await channel.connect()

    # Comece a tocar as músicas na fila
    await play_music(ctx)


async def play_music(ctx):
    global voice_channel
    global music_queue

    while len(music_queue) > 0:
        url = music_queue.pop(0)

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
        voice_channel.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=f'downloads/{song_title}.mp3'))

        # Enviar uma mensagem com o nome da música
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            song_title = info_dict.get('title', None)
        if len(music_queue) > 0:
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                next_info_dict = ydl.extract_info(music_queue[0], download=False)
                next_title = next_info_dict.get('title', None)
            await ctx.send(f'Tocando: `{song_title}`\nDuração: `{song_duration}` segundos\nPróxima música: '
                           f'`{next_title}`')
        else:
            await ctx.send(f'Tocando: `{song_title}`\nDuração: `{song_duration}` segundos.')

        # Aguarde até que o áudio termine de tocar, depois desconecte
        while voice_channel.is_playing():
            await asyncio.sleep(1)

        # Remova o arquivo de áudio
        if os.path.exists(f'downloads/{song_title}.mp3'):
            os.remove(f'downloads/{song_title}.mp3')

    if len(music_queue) == 0:
        await asyncio.sleep(120)
        await voice_channel.disconnect()


@bot.command(name='stopYT')
async def stop(ctx):
    global voice_channel
    global music_queue

    if os.path.exists(f'downloads/{music_playing}.mp3'):
        os.remove(f'downloads/{music_playing}.mp3')

    if voice_channel is not None:
        voice_channel.stop()
        await voice_channel.disconnect()
        voice_channel = None
        music_queue.clear()


@bot.command(name='skipYT')
async def skip(ctx):
    global voice_channel
    global music_queue

    if voice_channel is not None:
        # Pare a música atual
        voice_channel.stop()

        # Se não houver mais músicas na fila, pare a reprodução
        if len(music_queue) == 0:
            await stop(ctx)


# Inicie o bot
bot.run('MTE5NTIwMzI2NTQ1Mzg5MTYyNQ.GhXhLD.v7aqRhijHlQwj7-txefWvuTCM3yWfY8OBIRfAQ')
