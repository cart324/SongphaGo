from pydub import AudioSegment
from pydub.silence import split_on_silence

AudioSegment.converter = r'C:\Users\user\AppData\Local\ffmpegio\ffmpeg-downloader\ffmpeg\bin\ffmpeg.exe'

# 오디오 파일을 불러오는 함수 정의
def match_target_amplitude(aChunk, target_dBFS):
    # 주어진 오디오 청크를 목표 dBFS에 맞게 정규화
    change_in_dBFS = target_dBFS - aChunk.dBFS
    return aChunk.apply_gain(change_in_dBFS)


user_id = input("처리할 유저의 ID를 입럭하세요.")
# 오디오 파일 불러오기
song = AudioSegment.from_wav(f"recordings/{user_id}.wav")

# 공백이 2초 이상인 부분을 기준으로 오디오를 나누기
chunks = split_on_silence(
    song,
    min_silence_len=2000,  # 공백이 최소 2초 이상이어야 함
    silence_thresh=-16  # -16 dBFS보다 조용한 부분을 공백으로 간주
)

# 각 청크 처리
for i, chunk in enumerate(chunks):
    # 0.5초 길이의 공백 청크 생성
    silence_chunk = AudioSegment.silent(duration=500)

    # 전체 청크의 시작과 끝에 공백 청크 추가
    audio_chunk = silence_chunk + chunk + silence_chunk

    # 전체 청크 정규화
    normalized_chunk = match_target_amplitude(audio_chunk, -20.0)

    # 새 비트레이트로 오디오 청크 내보내기
    print(f"Exporting chunk{i}.mp3")
    normalized_chunk.export(
        f"./output/{user_id}chunk{i}.mp3",
        bitrate="192k",
        format="mp3"
    )
