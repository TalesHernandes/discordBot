import asyncio
import discord
from discord.ext import commands
import yt_dlp
import os
import re
import time

intents = discord.Intents.default()
intents.message_content = True

# Crie uma instância do bot
bot = commands.Bot(command_prefix='!!', intents=intents)
voice_channels = {}
music_queues = {}
ydl_opts_flat = {
    'extract_flat': True,
}
global music_playing
global loop_status


@bot.event
async def on_ready():
    print('Bot está pronto para ser utilizado!')
    await bot.loop.create_task(cleanup_downloads())


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
        print(f"Não é uma URL, inciando busca da query {query} no YouTube para pegar o primeiro vídeo")
        # Se não for uma URL, pesquise no YouTube
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            print("Busca iniciada")
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            url = info['entries'][0]['id']
            print("Busca realizada, vídeo encontrado: " + info['entries'][0]['title'])
    else:
        url = query

    # Verifique se a URL é uma playlist do YouTube
    if 'list=' in url and 'v=' not in url:
        print("URL é uma playlist")
        # Se for uma playlist, baixe todas as músicas da playlist
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            print("Download das URLs dos vídeos iniciada")
            info = ydl.extract_info(url, download=False)
            for entry in info['entries']:
                music_queues[guild_id].append(entry['id'])
            print("Download das URLs dos vídeos das playlists finalizada")
    else:
        # Se não for uma playlist, adicione a música à fila
        print("Query é uma URL de vídeo, iniciando busca")
        if guild_id in voice_channels and voice_channels[guild_id].is_playing():
            print(f"Já há uma música tocando para o servidor {guild_id}, música {music_playing}")
            with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
                print("Extraindo informações da música para enviar mensagem ao discord")
                info = ydl.extract_info(url, download=False)
                song_title = info.get('title', None)
                song_duration = info.get('duration', None)
                print("Extração finalizada")

            await ctx.send(f'Música adicionada: `{song_title}`\nDuração: `{song_duration}` segundos')
            print("Mensagem enviada no discord")

        if guild_id not in music_queues:
            music_queues[guild_id] = []
        music_queues[guild_id].append(url)
        print(f"Música adicionada à fila do servidor {guild_id}")

    # Se uma música já estiver tocando, não faça mais nada
    if guild_id in voice_channels and voice_channels[guild_id].is_playing():
        print("Música já esta tocando, não fazer nada")
        return

    # Conecte-se ao canal de voz do usuário
    print("Pegando canal de voz do usuário")
    if ctx.message.author.voice is None:
        await ctx.send("Você precisa estar em um canal de voz para usar este comando.")
        return
    else:
        channel = ctx.message.author.voice.channel
    if guild_id not in voice_channels or (guild_id in voice_channels and not voice_channels[guild_id].is_connected()):
        print("Conectando ao canal de voz do usuario...")
        voice_channels[guild_id] = await channel.connect()
        print(f"Conectado ao canal de voz {channel} no server {guild_id}")

    # Comece a tocar as músicas na fila
    print("Iniciando fila de músicas")
    await play_music(ctx)


async def play_music(ctx):
    inicio = time.time()
    global voice_channels
    global music_queues
    global music_playing
    music_playing = {}
    global loop_status

    guild_id = ctx.guild.id

    while len(music_queues[guild_id]) > 0:
        # Alterar valor da url para da primeira música e a removendo da lista
        url = music_queues[guild_id].pop(0)

        print("Iniciando busca de dados da música...")
        with yt_dlp.YoutubeDL(ydl_opts_flat) as ydl:
            print("Busca iniciada")
            info_dict = ydl.extract_info(url, download=False)
            song_title = info_dict.get('title', None)
            song_name_discord_msg = song_title
            try:
                song_title = re.sub('[^A-Za-z0-9 ]+', '', song_title)
                song_title = song_title.replace(' ', '_')
            except TypeError as e:
                print(e)
            music_playing = song_title
            song_duration = info_dict.get('duration', None)
            print("Busca finalizada")

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
        print("Iniciando download da música...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print("Download iniciado")
            ydl.extract_info(url, download=True)
            print("Download finalizado")

        # Reproduza o áudio baixado
        print("Iniciando toque da música...")
        voice_channels[guild_id].play(discord.FFmpegPCMAudio(executable="ffmpeg", source=f'downloads/{song_title}.mp3'))
        fim = time.time()
        tempo_total = fim - inicio

        print(f"Tempo de execução: {tempo_total} segundos")
        print("Tocando a música")

        # Enviar uma mensagem com o nome da música
        await ctx.send(f'Tocando: `{song_name_discord_msg}`\nDuração: `{song_duration}` segundos.')

        # Aguarde até que o áudio termine de tocar, depois desconecte
        while voice_channels[guild_id].is_playing():
            await asyncio.sleep(1)

        # Checagem de loop
        try:
            while guild_id in loop_status and loop_status[guild_id]:
                print(f"Loop ativo para o servidor {guild_id}")
                print("Retocando música")
                voice_channels[guild_id].play(
                    discord.FFmpegPCMAudio(executable="ffmpeg", source=f'downloads/{music_playing}.mp3'))
                while voice_channels[guild_id].is_playing():
                    await asyncio.sleep(1)
        except NameError as e:
            # Não sei resolver isso sem colocar 'loop_status = {}' no começo do código
            print(e)
        finally:
            loop_status = {guild_id: False}

        # Remova o arquivo de áudio
        if os.path.exists(f'downloads/{song_title}.mp3'):
            os.remove(f'downloads/{song_title}.mp3')

    if len(music_queues[guild_id]) == 0:
        print("Sem músicas na fila, aguardando 120s para desconectar")
        await asyncio.sleep(120)
        if guild_id in voice_channels and voice_channels[guild_id].is_playing():
            print("Música tocando, retornando")
            return
        else:
            await voice_channels[guild_id].disconnect()
            print("Desconectado com sucesso")


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


@bot.command(name='loop')
async def loop(ctx):
    global loop_status
    loop_status = {}

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


async def cleanup_downloads():
    while True:
        # Aguarde 5 minutos
        await asyncio.sleep(300)

        # Obtenha uma lista de todas as músicas atualmente tocando
        try:
            currently_playing = f'downloads/{music_playing}.mp3'
        except NameError as e:
            currently_playing = None
            print(e)

        # Obtenha uma lista de todos os arquivos na pasta de downloads
        downloads = os.listdir('downloads')

        if currently_playing is not None:
            for file in downloads:
                # Se o arquivo não estiver sendo reproduzido atualmente, exclua-o
                if file not in currently_playing:
                    os.remove(f'downloads/{file}')

# Inicie o bot
bot.run('TOKEN')
