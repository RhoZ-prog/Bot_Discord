import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse, urllib.request, re

def run_bot():
    TOKEN = os.getenv('DISCORD_TOKEN')
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix=".", intents=intents)

    queues = {}
    voice_clients = {}
    youtube_base_url = 'https://www.youtube.com/'
    youtube_results_url = youtube_base_url + 'results?'
    youtube_watch_url = youtube_base_url + 'watch?v='
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    @client.event
    async def on_ready():
        print(f'{client.user} esta conectada')

    async def play_next(ctx):
        if ctx.guild.id in queues and queues[ctx.guild.id]: 
            # Obtiene la siguiente cancion de la cola y la reproduce
            next_song = queues[ctx.guild.id].pop(0)
            voice_client = voice_clients[ctx.guild.id]
            player = discord.FFmpegOpusAudio(next_song['url'], **ffmpeg_options)
            voice_client.play(player, after=lambda e: play_next(ctx))
            asyncio.run_coroutine_threadsafe(ctx.send(f"Reproduciendo ahora: **{next_song['title']}**"), client.loop)

    
    @client.command(name="play")
    async def play(ctx, *, link):
        try:
            # Conectar a un canal de voz si no está conectado
            if ctx.guild.id not in voice_clients or not voice_clients[ctx.guild.id].is_connected():
                voice_client = await ctx.author.voice.channel.connect()
                voice_clients[ctx.guild.id] = voice_client
                if not voice_client or not voice_client.is_connected():
                # Reconecta si el cliente de voz se ha desconectado
                    voice_client = await ctx.author.voice.channel.connect()
                    voice_clients[ctx.guild.id] = voice_client
            else:
                voice_client = voice_clients[ctx.guild.id]

            # Si 'link' no es una URL de Youtube, Hace la busqueda
            if youtube_base_url not in link:
                query_string = urllib.parse.urlencode({
                    'search_query': link
                })

                content = urllib.request.urlopen(
                    youtube_results_url + query_string
                )

                search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())

                link = youtube_watch_url + search_results[0]

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))

            song = {
                "title" : data.get('title', 'Unknown Title'),
                "url": data['url']
            }

            # Si ya hay una cancion reproduciendose, agrega a la cola
            if voice_client.is_playing():
                if ctx.guild.id not in queues:
                    queues[ctx.guild.id] = []
                queues[ctx.guild.id].append(song)
                await ctx.send(f"Agregada a la cola: **{song['title']}**")
            else:
                # Si no hay ninguna cancion reproduciendose, reproduce la cancion inmediatamente
                player = discord.FFmpegOpusAudio(song['url'], **ffmpeg_options)
                voice_clients[ctx.guild.id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
                await ctx.send(f"Reproduciendo ahora: **{song['title']}**")
        
        except Exception as e:
            print(f"Error en el play: {e}")

    @client.command(name="clear_queue")
    async def clear_queue(ctx):
        if ctx.guild.id in queues:
            queues[ctx.guild.id].clear()
            await ctx.send("Cola de reproduccion limpiada!")
        else:
            await ctx.send("No hay nada que limpiar")

    @client.command(name="pause")
    async def pause(ctx):
        try:
            voice_clients[ctx.guild.id].pause()
        except Exception as e:
            print(e)

    @client.command(name="resume")
    async def resume(ctx):
        try:
            voice_clients[ctx.guild.id].resume()
        except Exception as e:
            print(e)

    @client.command(name="stop")
    async def stop(ctx):
        try:
            voice_clients[ctx.guild.id].stop()
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
        except Exception as e:
            print(e)

    @client.command(name="skip")
    async def skip(ctx):
        try:
            voice_clients[ctx.guild.id].stop()  # Detiene la canción actual
            await ctx.send("Saltando la canción actual!")
            await play_next(ctx)  # Llama a play_next para reproducir la siguiente canción en la cola
        except Exception as e:
            print(f"Error en skip: {e}")

    @client.command(name="list")
    async def list_queue(ctx):
        if ctx.guild.id in queues and queues[ctx.guild.id]:
            queue_list = queues[ctx.guild.id]
            queue_message = "Canciones en la cola:\n"
            for index, song in enumerate(queue_list, start=1):
                queue_message += f"{index}. {song['title']}\n"
            
            await ctx.send(queue_message)
        else:
            await ctx.send("La cola está vacía.")

    client.run(TOKEN)