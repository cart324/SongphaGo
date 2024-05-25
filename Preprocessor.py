from pydub import AudioSegment
from pydub.silence import split_on_silence
import os

AudioSegment.converter = r'C:\Users\desktop\Desktop\SongphaGo-main\ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe'


# 오디오 파일을 불러오는 함수 정의
def match_target_amplitude(aChunk, target_dBFS):
    # 주어진 오디오 청크를 목표 dBFS에 맞게 정규화
    change_in_dBFS = target_dBFS - aChunk.dBFS
    return aChunk.apply_gain(change_in_dBFS)


for (path, dirs, files) in os.walk("./recordings"):
    all_count = len(files)
    current_count = 1
    for file in files:
        file_name = file[:-4]
        # 오디오 파일 불러오기
        song = AudioSegment.from_wav(f"recordings/{file_name}.wav")
        print(f"processing {file_name}.wav [{current_count}/{all_count}]")

        # 공백이 2초 이상인 부분을 기준으로 오디오를 나누기
        chunks = split_on_silence(
            song,
            min_silence_len=2000,  # 공백이 최소 2초 이상이어야 함
            silence_thresh=-50  # -50 dBFS보다 조용한 부분을 공백으로 간주
        )

        # 각 청크 처리
        all_chunk = len(chunks)
        current_chunk = 1
        for i, chunk in enumerate(chunks):
            # 0.5초 길이의 공백 청크 생성
            silence_chunk = AudioSegment.silent(duration=500)

            # 전체 청크의 시작과 끝에 공백 청크 추가
            audio_chunk = silence_chunk + chunk + silence_chunk

            # 전체 청크 정규화
            normalized_chunk = match_target_amplitude(audio_chunk, -20.0)

            # 새 비트레이트로 오디오 청크 내보내기
            name = file_name[:-16]
            os.makedir(name, exist_ok=True)  # 유저별 폴더 생성
            print(f"Exporting {file_name}chunk{i}.mp3 [{current_chunk}/{all_chunk}]")
            normalized_chunk.export(
                f"./output/{name}/{file_name}chunk{i}.mp3",
                bitrate="192k",
                format="mp3"
            )

        # os.remove(f"recordings/{file_name}.wav")
