import os
import time
import psutil
from pydub import AudioSegment
from pydub.silence import split_on_silence
from concurrent.futures import ProcessPoolExecutor, as_completed

# 정확한 FFmpeg 경로 설정
ffmpeg_path = 'bin/ffmpeg.exe'

# FFmpeg 경로를 환경 변수로 추가
os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

# FFmpeg 경로를 Pydub에 설정
AudioSegment.converter = ffmpeg_path


# 오디오 파일을 불러오는 함수 정의
def match_target_amplitude(aChunk, target_dBFS):
    # 주어진 오디오 청크를 목표 dBFS에 맞게 정규화
    change_in_dBFS = target_dBFS - aChunk.dBFS
    return aChunk.apply_gain(change_in_dBFS)


def process_file(index, total, file_path):
    file_name = os.path.basename(file_path)[:-4]
    # 오디오 파일 불러오기
    song = AudioSegment.from_wav(file_path)
    print(f"Processing {file_name}.wav [{index + 1}/{total}]")

    # 공백이 2초 이상인 부분을 기준으로 오디오를 나누기
    chunks = split_on_silence(
        song,
        min_silence_len=2000,  # 공백이 최소 2초 이상이어야 함
        silence_thresh=-50  # -50 dBFS보다 조용한 부분을 공백으로 간주
    )

    # 길이가 1초 이하인 청크는 제외
    chunks = [chunk for chunk in chunks if len(chunk) > 1000]

    # 각 청크 처리
    total_chunk = len(chunks)
    current_chunk = 1
    for i, chunk in enumerate(chunks):
        # 0.5초 길이의 공백 청크 생성
        silence_chunk = AudioSegment.silent(duration=500)

        # 전체 청크의 시작과 끝에 공백 청크 추가
        audio_chunk = silence_chunk + chunk + silence_chunk

        # 전체 청크 정규화
        normalized_chunk = match_target_amplitude(audio_chunk, -20.0)

        # 새 비트레이트로 오디오 청크 내보내기
        name = file_name[:-12]
        os.makedirs(f"./output/{name}", exist_ok=True)  # 유저별 폴더 생성
        print(f"Exporting {file_name}chunk{i}.mp3 [{current_chunk}/{total_chunk}]")
        normalized_chunk.export(
            f"./output/{name}/{file_name}chunk{i}.mp3",
            bitrate="192k",
            format="mp3"
        )
        current_chunk += 1

    os.remove(f"recordings/{file_name}.wav")


def main():
    # recordings 디렉토리에서 모든 wav 파일 경로 수집
    file_paths = []
    for (path, dirs, files) in os.walk("./recordings"):
        for file in files:
            if file.endswith(".wav"):
                file_paths.append(os.path.join(path, file))

    total_files = len(file_paths)
    cpu_usage_limit = 60  # CPU 사용률을 최대 60%로 제한
    check_interval = 1  # CPU 사용률을 확인하는 주기 (초)

    def should_add_more_workers(current_workers):
        current_cpu_usage = psutil.cpu_percent(interval=check_interval)
        return current_cpu_usage < cpu_usage_limit and current_workers < total_files

    remain_file_list = list(range(1, total_files + 1))  # 전체 리스트 생성
    with ProcessPoolExecutor(max_workers=total_files) as executor:
        futures = {}
        for i, file_path in enumerate(file_paths):
            while not should_add_more_workers(len(futures)):
                time.sleep(check_interval)
            futures[executor.submit(process_file, i, total_files, file_path)] = i
            print(f"Started processing {i + 1}/{total_files}")

        for future in as_completed(futures):  # 남은 파일 출력
            file_number = futures[future] + 1
            remain_file_list.pop(file_number - 1)
            print(f"Completed file No.{file_number}.")
            print(f"{len(remain_file_list)} files remain : {remain_file_list}")


if __name__ == "__main__":
    main()
