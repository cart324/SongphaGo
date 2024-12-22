import discord
from discord.ext import commands
import asyncio
import yt_dlp
from pydub import AudioSegment
from io import BytesIO
import subprocess
import re
import traceback
import time

bot = discord.Bot()

# yt-dlp 설정
YDL_OPTIONS = {
    'format': 'bestaudio',
    'quiet': True,
    'noplaylist': True,
}

FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
        '-fflags +nobuffer -rw_timeout 5000000'
    ),
    'options': '-vn -b:a 128k'
}

neogulman = "https://cdn.discordapp.com/attachments/469870241699069963/1259233014899277955/image.png?ex=6767c2e2&is=67667162&hm=b3d52daea4e3ed108a190d1eb83b094023d8592186d3a18cab66a0fec1cb18da&"

# 목표 RMS 값
TARGET_RMS = 150

queue = []
embed_id = None
is_loop = False
song_cache = None

guild = [312795500757909506, 1242846739434569738]


# 볼륨 정규화 함수
def normalize_volume(audio_url: str) -> float:
    """볼륨 정규화를 위한 RMS 분석 및 조정 배율 계산"""
    try:
        # ffmpeg로 오디오 데이터를 추출하여 pydub로 로드
        process = subprocess.Popen(
            ['ffmpeg', '-i', audio_url, '-f', 'mp3', '-'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        audio_data = BytesIO(process.stdout.read())
        audio = AudioSegment.from_file(audio_data, format="mp3")
        rms = audio.rms
        adjustment_factor = TARGET_RMS / max(rms, 1)
        print(adjustment_factor)
        return min(max(adjustment_factor, 0.1), 0.5)  # 0.1배 ~ 0.5배로 제한
    except Exception as e:
        print(f"볼륨 정규화 오류: {e}")
        return 0.15  # 오류 시 기본 배율


async def handling_embed(ctx, current_song_data, queue_list):
    global embed_id

    if current_song_data is None:
        embed = discord.Embed(title="현재 재생중인 곡이 없습니다.", description="`/play`를 사용하여 노래를 틀어보세요!")
    else:
        next_song, is_url, requester, title, image, url = current_song_data

        if len(queue_list) == 0:
            next_title = "없음"
        else:
            next_title = queue_list[0][3]

        embed = discord.Embed(title="현재 재생중인 곡", description=f"[{title}]({url})\n​")
        embed.set_image(url=image)
        if is_loop:
            embed.add_field(name="다음 재생곡", value="현재 루프가 켜져있습니다.")
        else:
            embed.add_field(name="다음 재생곡", value=next_title)
        embed.set_footer(text=f"요청자 : {requester}")

    if embed_id is None:
        message = await ctx.send(embed=embed)
        embed_id = message.id
    else:
        message = await ctx.channel.fetch_message(embed_id)
        await message.edit(embed=embed)


@bot.command(guild_ids=guild)
async def join(ctx):
    """음성 채널에 입장합니다."""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.respond(f"{channel.name}에 입장했습니다!")
    else:
        await ctx.respond("먼저 음성 채널에 접속해주세요.")


@bot.command(guild_ids=guild)
async def leave(ctx):
    """음성 채널에서 퇴장합니다."""
    global embed_id

    if ctx.voice_client:
        embed = discord.Embed(title="플레이어가 종료되었습니다.")
        message = await ctx.channel.fetch_message(embed_id)
        await message.edit(embed=embed)
        embed_id = None
        await ctx.voice_client.disconnect()
        await ctx.respond("봇이 음성 채널에서 퇴장하였습니다.", ephemeral=True)
    else:
        await ctx.respond("봇이 음성 채널에 있지 않습니다.")


async def fetch_info(url):
    """YouTube URL 정보 로드"""
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
        return info['url'], info.get('title', '제목 없음'), info.get('thumbnail', neogulman)


@bot.command(guild_ids=guild)
async def play(ctx, url):
    """음악 재생: URL을 병렬로 로딩 후 재생목록에 추가"""
    # 명령어 실행 대기 상태 표시
    await ctx.defer(ephemeral=True)

    # URL인지 확인
    url_pattern = re.compile(r'^(http|https)://')
    is_url = url_pattern.match(url)

    try:
        if is_url:
            # URL 정보를 병렬로 가져오기
            loop = asyncio.get_event_loop()
            audio_info = await loop.run_in_executor(None, lambda: asyncio.run(fetch_info(url)))
            audio_url, title, thumbnail = audio_info
            queue.append((audio_url, True, ctx.author.name, title, thumbnail, url))
            await ctx.respond(f"재생목록에 추가되었습니다: {title} (URL: {url})", ephemeral=True)
        else:
            queue.append((url, False, ctx.author.name, "로컬 파일"))
            await ctx.respond(f"재생목록에 추가되었습니다: {url}", ephemeral=True)

        if ctx.voice_client is None:
            if ctx.author.voice:
                channel = ctx.author.voice.channel
                await channel.connect()
            else:
                await ctx.respond("먼저 음성 채널에 접속해주세요.", ephemeral=True)
                return

        # 현재 재생 중이 아니면 다음 곡 재생
        if not ctx.voice_client.is_playing():
            await play_next(ctx)

        # 다음 재생 곡이 생기면 임베드 수정
        if len(queue) == 1:
            await handling_embed(ctx, song_cache, queue)

    except Exception:
        error_log = traceback.format_exc(limit=None, chain=True)
        cart = bot.get_user(344384179552780289)
        await ctx.send("에러가 발생하였습니다.")
        await cart.send("```" + str(error_log) + "```")


async def play_next(ctx):
    """재생목록에서 다음 음악 재생"""
    global song_cache

    if not queue and not is_loop:
        await handling_embed(ctx, None, None)
        return

    if is_loop and song_cache:
        next_song, is_url, requester, title, thumbnail, url = song_cache
    else:
        song_cache = next_song, is_url, requester, title, thumbnail, url = queue.pop(0)

    try:
        # URL 또는 로컬 파일 처리
        if is_url:
            audio_url = next_song
            volume_adjustment = 0.2
        else:
            audio_url = next_song
            volume_adjustment = normalize_volume(audio_url)

        # ffmpeg로 스트림 재생
        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
        audio_with_volume = discord.PCMVolumeTransformer(source, volume=volume_adjustment)
        ctx.voice_client.play(audio_with_volume, after=lambda e: bot.loop.create_task(play_next(ctx)))

        await handling_embed(ctx, song_cache, queue)

    except Exception:
        error_log = traceback.format_exc(limit=None, chain=True)
        cart = bot.get_user(344384179552780289)
        await ctx.send("에러가 발생하였습니다.")
        await cart.send("```" + str(error_log) + "```")


@bot.command(guild_ids=guild)
async def skip(ctx):
    """현재 곡을 건너뜁니다."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.respond("현재 곡을 건너뜁니다.")
    else:
        await ctx.respond("재생 중인 곡이 없습니다.")


@bot.command(guild_ids=guild)
async def stop(ctx):
    """재생을 중지하고 재생목록 초기화"""
    global queue
    if ctx.voice_client:
        ctx.voice_client.stop()
        queue = []
        await ctx.respond("재생을 중지하고 재생목록을 초기화했습니다.")
    else:
        await ctx.respond("재생 중이 아닙니다.")


@bot.command(guild_ids=guild)
async def start_loop(ctx):
    """현재 곡을 무한 반복"""
    global is_loop
    if ctx.voice_client and (song_cache is not None) and ctx.voice_client.is_playing():
        is_loop = True
        await ctx.respond("루프가 켜졌습니다.")
    else:
        await ctx.respond("재생 중이 아닙니다.", ephemeral=True)


@bot.command(guild_ids=guild)
async def stop_loop(ctx):
    """무한 반복 중단"""
    global is_loop
    if is_loop:
        is_loop = False
        await ctx.respond("루프가 꺼졌습니다.")
    else:
        await ctx.respond("루프 중이 아닙니다.", ephemeral=True)


with open('token.txt', 'r') as f:
    token = f.read()

bot.run(token)
