"""트래픽 분류 결과와 슬라이스 정책 매핑을 보여주는 Streamlit 대시보드.

데이터 경로는 환경변수 ORAN_DATA로 바꿀 수 있다.
    streamlit run apps/dashboard.py
"""

import os
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA = os.path.join(REPO_ROOT, "data", "validation_data.csv")
DATA_PATH = os.environ.get("ORAN_DATA", DEFAULT_DATA)

# 분류 결과를 어느 슬라이스로 보낼지 정한 규칙표.
# 학습된 것이 아니라 사람이 정한 정책이며, 이 데모의 전부다.
SLICE_POLICY = {
    "control":  ("Control",  "URLLC",           "1 (Highest)", "즉시 할당 (Priority)"),
    "video":    ("Video",    "eMBB (Video)",    "2 (High)",    "대역폭 보장 (Guaranteed)"),
    "download": ("Download", "eMBB (Download)", "3 (Low)",     "최선형 처리 (Best Effort)"),
}

st.set_page_config(page_title="O-RAN 트래픽 분류 대시보드", page_icon="📡", layout="wide")


@st.cache_data
def load_and_train(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)

    X = df.drop("class", axis=1)
    y = df["class"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    return model, X_test, y_test, y_pred, accuracy_score(y_test, y_pred)


st.title("📡 O-RAN 트래픽 분류 대시보드")
st.markdown(
    "TLS 1.3로 암호화된 세션을 **복호화 없이** 패킷 크기·도착 간격 통계만으로 분류하고, "
    "분류 결과를 슬라이스 정책에 매핑한다."
)

st.warning(
    "**범위 명시** — 상용 O-RAN / E2 인터페이스 구현이 아니다. "
    "CipherSpectrum 공개 데이터에서 추출한 특징 CSV를 분류하는 모델과, 그 결과를 슬라이스에 대응시킨 "
    "규칙표(`SLICE_POLICY`)로 이루어진 데모다. 슬라이스 할당은 학습된 판단이 아니라 "
    "고정된 매핑이다.",
    icon="⚠️",
)

result = load_and_train(DATA_PATH)
if result is None:
    st.error(f"데이터 파일을 찾을 수 없다: `{DATA_PATH}`\n\n"
             "환경변수 `ORAN_DATA`로 경로를 지정할 수 있다.")
    st.stop()

model, X_test, y_test, y_pred, acc = result

tab1, tab2 = st.tabs(["모델 성능", "슬라이스 매핑 데모"])

with tab1:
    col1, col2, col3 = st.columns(3)
    col1.metric("테스트셋 정확도", f"{acc * 100:.2f}%")
    col2.metric("테스트 표본", f"{len(X_test)}개")
    col3.metric("클래스 수", f"{len(model.classes_)}개 ({', '.join(model.classes_)})")

    st.caption(f"데이터: `{os.path.relpath(DATA_PATH, REPO_ROOT)}` · 8:2 stratified split · RandomForest(n=100, seed=42)")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("오차 행렬")
        fig1, ax1 = plt.subplots(figsize=(5, 4))
        sns.heatmap(confusion_matrix(y_test, y_pred), annot=True, fmt="d", cmap="Blues",
                    xticklabels=model.classes_, yticklabels=model.classes_, ax=ax1)
        ax1.set_xlabel("Predicted")
        ax1.set_ylabel("Actual")
        st.pyplot(fig1)
    with c2:
        st.subheader("특징 중요도")
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        imp = pd.Series(model.feature_importances_, index=X_test.columns).sort_values(ascending=False)
        sns.barplot(x=imp, y=imp.index, hue=imp.index, legend=False, palette="viridis", ax=ax2)
        ax2.set_xlabel("importance")
        st.pyplot(fig2)

with tab2:
    st.info("테스트셋에서 30개를 무작위로 뽑아 순서대로 흘려보내며, 분류 결과에 따라 "
            "슬라이스를 배정하는 과정을 보여준다. 실시간 캡처가 아니라 저장된 테스트 데이터 재생이다.")

    start_btn = st.button("▶ 재생 시작", type="primary")

    kpi_cols = st.columns(4)
    kpi_total, kpi_urllc, kpi_video, kpi_down = (c.empty() for c in kpi_cols)
    kpi_total.metric("처리 세션", "0 건")
    kpi_urllc.metric("URLLC (control)", "0 건")
    kpi_video.metric("eMBB (video)", "0 건")
    kpi_down.metric("eMBB (download)", "0 건")

    st.divider()
    st.markdown("### 세션별 분류 로그")
    log_table = st.empty()

    if start_btn:
        stats = {"control": 0, "video": 0, "download": 0}
        logs = []
        rng = np.random.default_rng(42)
        indices = rng.choice(len(X_test), 30, replace=True)

        for i, idx in enumerate(indices):
            sample = X_test.iloc[[idx]]
            pred = model.predict(sample)[0]
            confidence = float(np.max(model.predict_proba(sample)[0]) * 100)

            traffic_type, assigned_slice, priority, action = SLICE_POLICY[pred]
            stats[pred] += 1

            kpi_total.metric("처리 세션", f"{i + 1} 건")
            kpi_urllc.metric("URLLC (control)", f"{stats['control']} 건")
            kpi_video.metric("eMBB (video)", f"{stats['video']} 건")
            kpi_down.metric("eMBB (download)", f"{stats['download']} 건")

            logs.insert(0, {
                "Time": time.strftime("%H:%M:%S"),
                "Traffic Type": traffic_type,
                "Assigned Slice": assigned_slice,
                "Priority": priority,
                "Network Action": action,
                "Avg Pkt Size": int(sample["avg_pkt_size"].values[0]),
                "Std Pkt Size": float(sample["std_pkt_size"].values[0]),
                "Total Packets": int(sample["total_packets"].values[0]),
                "Confidence": confidence,
            })

            log_table.dataframe(
                pd.DataFrame(logs), use_container_width=True, height=400, hide_index=True,
                column_config={
                    "Avg Pkt Size": st.column_config.NumberColumn(format="%d B"),
                    "Std Pkt Size": st.column_config.NumberColumn(format="%.1f"),
                    "Total Packets": st.column_config.ProgressColumn(min_value=0, max_value=5000, format="%d"),
                    "Confidence": st.column_config.NumberColumn(format="%.1f %%"),
                },
            )
            time.sleep(0.3)

        st.success("재생 완료.")
