# 데이터 출처와 이용 조건

이 폴더의 두 CSV는 원본 PCAP 파일을 포함하지 않습니다. 각 행은 암호화된 세션에서
페이로드를 복호화하지 않고 계산한 통계 특징 9개와 실험용 클래스 라벨로 구성됩니다.

## 파일

| 파일 | 행 수 | 클래스 | 변환 |
|---|---:|---|---|
| `validation_data_nofilter.csv` | 2,400 | control / video / download | 사이트별 최대 600개 세션에서 통계 특징 추출 |
| `validation_data.csv` | 992 | control / video / download | 통계 특징 추출 전에 파일 크기 필터 적용. 당시 임계값은 기록되지 않음 |

두 파일에는 IP 주소, 호스트명, 원본 파일명, 패킷 페이로드가 들어 있지 않습니다.

## 원 데이터

- 이름: CipherSpectrum: TLS 1.3 Encrypted Network Traffic Dataset
- 공식 사이트: https://cgi.cse.unsw.edu.au/~cspectrum/
- 논문: *SoK: Decoding the Enigma of Encrypted Network Traffic Classifiers*
- 저자: Nimesha Wickramasinghe, Arash Shaghaghi, Gene Tsudik, Sanjay Jha
- DOI: https://doi.org/10.1109/SP61157.2025.00165
- 원 데이터 라이선스: [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)

## 이 저장소에서 적용한 변경

1. 사이트별 PCAP 세션에서 패킷 크기·도착 간격·세션 길이 통계 9개를 추출했습니다.
2. 사이트를 `control`, `video`, `download` 실험 클래스에 매핑했습니다.
3. `validation_data_nofilter.csv`는 사이트별 최대 600개를 샘플링했습니다.
4. `validation_data.csv`는 추가 파일 크기 필터를 적용했습니다.

이 CSV는 CipherSpectrum에서 파생되었으므로 데이터 부분에는 CC BY-NC 4.0의
저작자 표시와 비상업 조건이 적용됩니다. 이 고지는 저장소의 Python 코드에 적용할
코드 라이선스를 별도로 부여하는 것이 아닙니다.

원본 PCAP을 사용하려면 공식 사이트에서 직접 받아 해당 조건을 확인하세요.
