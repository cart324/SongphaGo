import discord
from Restore_header import recover_wav_header
import os
import time

bot = discord.Bot()
connections = {}


@bot.command(guild_ids=[312795500757909506, 1242846739434569738])
async def record(ctx):
    # Check if the author is in a voice channel
    voice = ctx.author.voice
    if not voice:
        await ctx.respond("You aren't in a voice channel!", ephemeral=True)
        return

    # Connect to the voice channel the author is in
    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})  # Update the cache with the guild and channel
    vc.start_recording(
        discord.sinks.WaveSink(),  # The sink type to use (you can choose other formats too)
        once_done,  # What to do once recording is done
        ctx.channel  # The channel to disconnect from
    )
    await ctx.respond("Started recording!", ephemeral=True)


async def once_done(sink, user, *ags):
    await sink.vc.disconnect()  # Disconnect from the voice channel
    cart = await bot.fetch_user(344384179552780289)
    now = str(time.strftime('_%m_%d_%H_%M'))  # 현재 시간 추출
    # 녹음된 오디오 데이터를 파일로 저장
    for user_id, audio in sink.audio_data.items():
        id_name = await bot.fetch_user(user_id)  # ID에서 닉네임 추출
        id_name = str(id_name.name) + now
        filename = f"recordings/{user_id}.wav"
        filename2 = f"recordings/{id_name}.wav"
        with open(filename, 'wb') as file:
            file.write(audio.file.getvalue())
        recover_wav_header(filename, filename2)  # 헤더 복구
        os.remove(filename)  # 원본 파일 제거
        await cart.send(f"녹음된 오디오 파일을 저장했습니다: {filename2}")


@bot.command(guild_ids=[312795500757909506, 1242846739434569738])
async def stop_recording(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()  # Stop recording and call the callback (once_done)
        del connections[ctx.guild.id]  # Remove the guild from the cache
        await ctx.delete()  # Delete the command message
    else:
        await ctx.respond("I am currently not recording here.", ephemeral=True)

with open('token.txt', 'r') as f:
    token = f.read()

bot.run(token)
