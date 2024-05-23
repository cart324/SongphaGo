import discord

bot = discord.Bot()
connections = {}


@bot.command()
async def record(ctx):
    # Check if the author is in a voice channel
    voice = ctx.author.voice
    if not voice:
        await ctx.respond("You aren't in a voice channel!")
        return

    # Connect to the voice channel the author is in
    vc = await voice.channel.connect()
    connections.update({ctx.guild.id: vc})  # Update the cache with the guild and channel
    vc.start_recording(
        discord.sinks.WaveSink(),  # The sink type to use (you can choose other formats too)
        once_done,  # What to do once recording is done
        ctx.channel  # The channel to disconnect from
    )
    await ctx.respond("Started recording!")


async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):
    # Get the recorded users
    recorded_users = [f"<@{user_id}>" for user_id, audio in sink.audio_data.items()]
    await sink.vc.disconnect()  # Disconnect from the voice channel
    files = [discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in sink.audio_data.items()]
    await channel.send(f"Finished recording audio for: {', '.join(recorded_users)}.", files=files)


@bot.command()
async def stop_recording(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()  # Stop recording and call the callback (once_done)
        del connections[ctx.guild.id]  # Remove the guild from the cache
        await ctx.delete()  # Delete the command message
    else:
        await ctx.respond("I am currently not recording here.")

with open('token.txt', 'r') as f:
    token = f.read()

bot.run(token)
