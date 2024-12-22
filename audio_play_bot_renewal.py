import discord
from discord.ext import commands
import asyncio
from collections import defaultdict
from pydub import AudioSegment
from io import BytesIO
import subprocess
import re
import yt_dlp
import multiprocessing
from concurrent.futures import ProcessPoolExecutor


# 봇 기본 셋팅
bot = discord.Bot()

# yt-dlp 설정
YDL_OPTIONS = {
    'format': 'bestaudio',
    'quiet': True,
    'noplaylist': True,
}

# 목표 RMS 값
TARGET_RMS = 150

neogulman = "https://cdn.discordapp.com/attachments/469870241699069963/1259233014899277955/image.png?ex=6767c2e2&is=67667162&hm=b3d52daea4e3ed108a190d1eb83b094023d8592186d3a18cab66a0fec1cb18da&"

guild = [312795500757909506, 1242846739434569738]


class ServerInfo:
    def __init__(self):
        self.FFMPEG_OPTIONS = {
            'before_options': (
                '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
                '-fflags +nobuffer -rw_timeout 5000000'
            ),
            'options': '-vn'
        }
        self.queue = []     # [{song_play_url, volume_adjustment, song_title, requester, original_url, song_cover}]
        self.is_loop = False
        self.song_cache = None
        self.embed_id = None

    def set_bitrate(self, bitrate):
        bitrate = int(bitrate / 1000)
        self.FFMPEG_OPTIONS = {
            'before_options': (
                '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 '
                '-fflags +nobuffer -rw_timeout 5000000'
            ),
            'options': f'-vn'
        }


server_info = defaultdict(ServerInfo)


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


def youtube_download(url: str) -> tuple:
    """
    유튜브 영상에서 정보 추출

    :arg url: 유튜브 url
    :return: (곡 url, 곡 제목)
    """
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
    return info['url'], info.get('title', '제목 없음'), info.get('thumbnail', neogulman)


async def handling_embed(ctx, global_info: ServerInfo):
    """임베드 처리"""
    song_cache = global_info.song_cache
    # 재생목록이 비었을 때
    if global_info.song_cache is None:
        embed = discord.Embed(title="현재 재생중인 곡이 없습니다.", description="`/play`를 사용하여 노래를 틀어보세요!")
    # 그 외
    else:
        # 다음 곡 제목 추출
        if len(global_info.queue) == 0:
            next_title = "없음"
        else:
            next_title = global_info.queue[0]['song_title']

        # 현재 재생 곡 정보
        embed = discord.Embed(title="현재 재생중인 곡",
                              description=f"[{song_cache['song_title']}]({song_cache['original_url']})\n​")

        # 현재 재생 곡 커버 추가
        embed.set_image(url=song_cache['song_cover'])

        # 루프 일 경우 표시
        if global_info.is_loop:
            embed.add_field(name="다음 재생곡", value="현재 루프가 켜져있습니다.")
        else:
            embed.add_field(name="다음 재생곡", value=next_title)

        # 신청자 표시
        embed.set_footer(text=f"신청자 : {song_cache['requester']}")

    # 첫 임베드 생성일 경우 처리
    if global_info.embed_id is None:
        message = await ctx.send(embed=embed)
        global_info.embed_id = message.id
    else:
        message = await ctx.channel.fetch_message(global_info.embed_id)
        await message.edit(embed=embed)


@bot.command(guild_ids=guild)
async def play(ctx, url):
    """음악을 재생목록에 추가"""
    global_info = server_info[ctx.guild.id]

    # 명령어 실행 대기 상태 표시
    await ctx.defer(ephemeral=True)

    # URL인지 확인
    url_pattern = re.compile(r'^(http|https)://')
    is_url = url_pattern.match(url)

    # 온라인 파일일 경우
    if is_url:
        # URL 정보를 멀티프세싱으로 가져오기
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor() as executor:
            song_url, title, image = await loop.run_in_executor(executor, youtube_download, url)

        # 고정 볼륨
        volume_adjustment = 0.2

        await ctx.respond(f"재생목록에 추가되었습니다: {title}\n(URL: {url})", ephemeral=True)

    # 로컬 파일일 경우
    else:
        # 파일 정보 추출
        song_url, title, image = url, "로컬 파일", neogulman

        # 동적 볼륨 계산
        loop = asyncio.get_event_loop()
        with ProcessPoolExecutor() as executor:
            volume_adjustment = await loop.run_in_executor(executor, normalize_volume, url)

        await ctx.respond(f"로컬파일이 재생목록에 추가되었습니다: {title}", ephemeral=True)

    # 재생목록 등록
    song_dict = {
        'song_play_url': song_url,
        'volume_adjustment': volume_adjustment,
        'song_title': title,
        'requester': ctx.author.name,
        'original_url': url,
        'song_cover': image
    }
    global_info.queue.append(song_dict)

    # 보이스 채널 입장
    if ctx.voice_client is None:
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            await channel.connect()
            # 채널별 비트레이트 설정
            global_info.set_bitrate(ctx.author.voice.channel.bitrate)
        else:
            await ctx.respond("먼저 음성 채널에 접속해주세요.", ephemeral=True)
            return

    # 현재 재생 중이 아니면 다음 곡 재생
    if not ctx.voice_client.is_playing():
        await play_queue(ctx)
    # 재생 중 다음 곡이 생겼을 때 임배드 수정
    else:
        if len(global_info.queue) == 1:
            await handling_embed(ctx, global_info)


async def play_queue(ctx):
    """재생목록에서 다음 음악 재생"""
    global_info = server_info[ctx.guild.id]

    # leave를 사용했을 때 간섭 방지용
    if ctx.voice_client is None:
        return
    # 재생목록이 비었을 때
    elif len(global_info.queue) == 0 and not global_info.is_loop:
        global_info.song_cache = None
        await handling_embed(ctx, global_info)

    else:
        # 루프 중일 때는 캐쉬 갱신 안함
        if global_info.is_loop and (global_info.song_cache is not None):
            pass

        else:
            global_info.song_cache = global_info.queue.pop(0)

        # ffmpeg로 스트림 재생
        source = discord.FFmpegPCMAudio(global_info.song_cache['song_play_url'], **global_info.FFMPEG_OPTIONS)
        audio_with_volume = discord.PCMVolumeTransformer(source, volume=global_info.song_cache['volume_adjustment'])
        ctx.voice_client.play(audio_with_volume, after=lambda e: bot.loop.create_task(play_queue(ctx)))

        await handling_embed(ctx, global_info)


@bot.command(guild_ids=guild)
async def set_volume(ctx, volume_percent: discord.Option(int)):
    """현재 재생 중인 곡의 볼륨을 조정합니다. (%단위로 입력하세요.)"""
    global_info = server_info[ctx.guild.id]

    if ctx.voice_client and ctx.voice_client.source:
        current_volume = global_info.song_cache['volume_adjustment']
        new_volume = current_volume * volume_percent / 100
        ctx.voice_client.source.volume = max(0.0, min(new_volume, 1.0))  # 볼륨 범위 제한
        await ctx.send(f"현재 곡의 볼륨을 {volume_percent}%로 설정했습니다.")
    else:
        await ctx.send("재생 중인 오디오가 없습니다.", ephemeral=True)


@bot.command(guild_ids=guild)
async def auto_volume(ctx):
    """현재 재생 중인 곡의 볼륨을 자동으로 적절하게 조절합니다."""
    global_info = server_info[ctx.guild.id]

    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as executor:
        current_volume = global_info.song_cache['volume_adjustment']
        new_volume = await loop.run_in_executor(executor, normalize_volume, global_info.song_cache['song_play_url'])
        volume_percent = int(new_volume / current_volume)
        ctx.voice_client.source.volume = max(0.0, min(new_volume, 1.0))  # 볼륨 범위 제한
        await ctx.respond(f"현재 곡의 볼륨을 {volume_percent}%로 설정했습니다.")


@bot.command(guild_ids=guild)
async def skip(ctx):
    """현재 곡을 건너뜁니다."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.respond("현재 곡을 건너뜁니다.")
    else:
        await ctx.respond("재생 중인 곡이 없습니다.", ephemeral=True)


@bot.command(guild_ids=guild)
async def stop(ctx):
    """재생을 중지하고 재생목록 초기화"""
    global_info = server_info[ctx.guild.id]

    if ctx.voice_client:
        global_info.queue = []
        ctx.voice_client.stop()
        await ctx.respond("재생을 중지하고 재생목록을 초기화했습니다.")
    else:
        await ctx.respond("재생 중이 아닙니다.", ephemeral=True)


@bot.command(guild_ids=guild)
async def loop(ctx):
    """현재 곡의 루프를 켜고 끕니다."""
    global_info = server_info[ctx.guild.id]

    if global_info.is_loop:
        global_info.is_loop = False
        await handling_embed(ctx, global_info)
        await ctx.respond("루프가 꺼졌습니다.", ephemeral=True)

    else:
        if ctx.voice_client and (global_info.song_cache is not None) and ctx.voice_client.is_playing():
            global_info.is_loop = True
            await handling_embed(ctx, global_info)
            await ctx.respond("루프가 켜졌습니다.", ephemeral=True)
        else:
            await ctx.respond("재생 중이 아닙니다.", ephemeral=True)


@bot.command(guild_ids=guild)
async def re_embed(ctx):
    """플레이어 UI를 지웠다 다시 보내어 채팅의 아래에 위치시킵니다."""
    global_info = server_info[ctx.guild.id]

    if global_info.embed_id is None:
        await ctx.respond("현재 활성화된 플레이어가 없습니다.", ephemeral=True)
    else:
        message = await ctx.channel.fetch_message(global_info.embed_id)
        await message.delete()
        global_info.embed_id = None
        await handling_embed(ctx, global_info)
        await ctx.respond("플레이어를 갱신하였습니다.", ephemeral=True)


@bot.command(guild_ids=guild)
async def leave(ctx):
    """노래 재생을 중단하고 음성 채널에서 퇴장합니다."""
    global_info = server_info[ctx.guild.id]

    if ctx.voice_client:
        embed = discord.Embed(title="플레이어가 종료되었습니다.")
        message = await ctx.channel.fetch_message(global_info.embed_id)
        await message.edit(embed=embed)
        global_info.embed_id = None
        await ctx.voice_client.disconnect()
        await ctx.respond("봇이 음성 채널에서 퇴장하였습니다.", ephemeral=True)
    else:
        await ctx.respond("봇이 음성 채널에 있지 않습니다.", ephemeral=True)


# @bot.command(guild_ids=guild)
# async def view_current_bitrate(ctx):
#     """현재 노래를 재생중인 채널의 비트레이트를 출력합니다."""
#     global_info = server_info[ctx.guild.id]
#
#     if ctx.voice_client:
#         current_bitrate = global_info.FFMPEG_OPTIONS['options'].split()[-1]
#         await ctx.respond(f"현재 채널의 비트레이트는 {current_bitrate}bps 입니다.", ephemeral=True)
#     else:
#         await ctx.respond("봇이 음성 채널에 있지 않습니다.", ephemeral=True)
#
#
# @bot.command(guild_ids=guild)
# async def set_bitrate(ctx, bitrate: discord.Option(int)):
#     """다음 노래부터 비트레이트를 변경합니다. (kbps 단위로 입력하세요.)"""
#     global_info = server_info[ctx.guild.id]
#     global_info.set_bitrate(int(bitrate * 1000))
#     await ctx.respond(f"비트레이트를 {bitrate}kbps로 설정하였습니다.")


# 멀티프로세스 실행시 봇 접속 방지
if __name__ == '__main__':

    multiprocessing.set_start_method('spawn', force=True)

    # 봇 토큰 설정
    with open('token.txt', 'r') as f:
        token = f.read()

    bot.run(token)
