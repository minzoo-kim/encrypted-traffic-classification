"""pcap 파일에서 통계 특징을 추출해 CSV로 저장한다.

암호화된 TLS 1.3 트래픽은 페이로드를 볼 수 없으므로, 복호화 없이 관찰 가능한
값(패킷 크기, 도착 간격, 세션 길이)만으로 특징 벡터를 만든다.

사용 예:
    # 폴더 이름이 곧 클래스인 경우
    python src/feature_extraction.py --input data/raw/dataset \\
        --labels bulk=bulk,control=control --output data/validation_data.csv

    # 사이트별 폴더를 클래스로 묶는 경우 (논문 실험에서 사용한 방식)
    python src/feature_extraction.py --input data/raw/mix \\
        --labels steamstatic.com=download,wistia.com=video,google.com=control,twitter.com=control \\
        --samples-per-folder 600 --output data/validation_data_nofilter.csv
"""

import argparse
import os
import random
import sys

import numpy as np
import pandas as pd
from scapy.error import Scapy_Exception
from scapy.layers.inet import IP
from scapy.utils import rdpcap

MIN_IP_PACKETS = 5  # 이보다 패킷이 적은 세션은 통계가 의미 없어 제외한다


def extract_features(file_path, min_file_size=0):
    """pcap 파일 하나에서 9개 통계 특징을 뽑는다.

    크기 또는 IP 패킷 수 필터에 걸리면 None을 반환한다. 파일 읽기·파싱 실패는
    호출부가 파일명과 원인을 기록할 수 있도록 그대로 전달한다.
    """
    # [노이즈 제거 1단계] 파일이 너무 작으면 읽지도 않고 패스 (속도 향상)
    if os.path.getsize(file_path) < min_file_size:
        return None

    packets = rdpcap(file_path)
    ip_packets = [pkt for pkt in packets if IP in pkt]

    # [노이즈 제거 2단계] 실제 패킷이 너무 적으면 패스
    if len(ip_packets) < MIN_IP_PACKETS:
        return None

    sizes = [pkt[IP].len for pkt in ip_packets]
    timestamps = [float(pkt.time) for pkt in ip_packets]
    deltas = np.diff(timestamps)

    return {
        "avg_pkt_size": np.mean(sizes),
        "std_pkt_size": np.std(sizes),
        "max_pkt_size": np.max(sizes),
        "min_pkt_size": np.min(sizes),
        "avg_delta_time": np.mean(deltas) if len(deltas) > 0 else 0,
        "std_delta_time": np.std(deltas) if len(deltas) > 0 else 0,
        "max_delta_time": np.max(deltas) if len(deltas) > 0 else 0,
        "duration": timestamps[-1] - timestamps[0],
        "total_packets": len(ip_packets),
    }


def parse_labels(spec):
    """'folder=class,folder=class' 형식을 dict로 변환한다."""
    mapping = {}
    for pair in spec.split(","):
        folder, _, label = pair.partition("=")
        folder = folder.strip()
        label = label.strip()
        if not folder or not label:
            raise argparse.ArgumentTypeError(f"잘못된 --labels 항목: {pair!r}")
        mapping[folder] = label
    return mapping


def build_dataset(base_path, labels, samples_per_folder, min_file_size, seed):
    rng = random.Random(seed)
    rows = []
    filtered_files = 0
    failed_files = 0
    missing_folders = 0

    for folder, label in labels.items():
        folder_path = os.path.join(base_path, folder)
        if not os.path.isdir(folder_path):
            print(f"[경고] 폴더 없음, 건너뜀: {folder_path}")
            missing_folders += 1
            continue

        files = [f for f in os.listdir(folder_path) if f.endswith(".pcap")]
        # 폴더 안 순서에 편향되지 않도록 무작위로 섞은 뒤 앞에서부터 채운다
        rng.shuffle(files)
        print(f"[{folder}] pcap {len(files)}개 중 유효 데이터 탐색 (label={label})")

        count = 0
        for file in files:
            file_path = os.path.join(folder_path, file)
            try:
                features = extract_features(file_path, min_file_size)
            except (OSError, ValueError, EOFError, Scapy_Exception) as exc:
                failed_files += 1
                print(
                    f"[오류] 특징 추출 실패: {file_path} "
                    f"({type(exc).__name__}: {exc})",
                    file=sys.stderr,
                )
                continue
            if features:
                features["class"] = label
                rows.append(features)
                count += 1
            else:
                filtered_files += 1
            if samples_per_folder and count >= samples_per_folder:
                break

        print(f"  └ {count}개 확보")

    print(
        f"[요약] 추출 {len(rows)}개 · 필터 제외 {filtered_files}개 · "
        f"파싱 실패 {failed_files}개 · 누락 폴더 {missing_folders}개"
    )
    return pd.DataFrame(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, help="클래스별 하위 폴더를 담고 있는 pcap 루트 경로")
    parser.add_argument("--labels", required=True, type=parse_labels,
                        help="'폴더명=클래스명' 쉼표 구분 목록")
    parser.add_argument("--output", default="validation_data.csv", help="저장할 CSV 경로")
    parser.add_argument("--samples-per-folder", type=int, default=0,
                        help="폴더당 최대 표본 수 (0이면 제한 없음)")
    parser.add_argument("--min-file-size", type=int, default=0,
                        help="이 크기(byte) 미만 pcap은 건너뜀")
    parser.add_argument("--seed", type=int, default=42, help="샘플링 재현용 난수 시드")
    args = parser.parse_args(argv)

    df = build_dataset(args.input, args.labels, args.samples_per_folder,
                       args.min_file_size, args.seed)

    if df.empty:
        print(
            "추출된 데이터가 없습니다. --input 경로와 --labels 폴더명을 확인하세요.",
            file=sys.stderr,
        )
        return 1

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    df.to_csv(args.output, index=False)

    print("-" * 50)
    print(f"저장 완료: {args.output} (총 {len(df)}개)")
    print(df["class"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
