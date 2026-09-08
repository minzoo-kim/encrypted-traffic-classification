"""세션 단위 분류 결과를 로그 형태로 흘려보내는 Streamlit 시연 화면.

발표용으로 만든 화면이다. 표에서 **트래픽 유형과 확신도만 모델이 낸 값**이고,
애플리케이션 이름과 IP 주소는 화면을 채우기 위해 생성한 예시값이다.
이 코드는 세션의 출처나 접속 사이트를 식별하지 않는다.

    streamlit run apps/tracker_demo.py
"""

import os
import random
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

# ─────────────────────────────────────────────────────────────────────
# 아래 두 목록은 모델 출력이 아니다. 화면을 그럴듯하게 채우기 위한 예시값이며,
# 클래스별로 "이런 앱이 이 범주에 속한다" 정도를 보여주는 용도다.
# 실제 세션이 어느 서비스로 갔는지는 이 프로젝트에서 판별하지 않는다.
# ─────────────────────────────────────────────────────────────────────
MOCK_APP_EXAMPLES = {
    "video":    ["YouTube", "Netflix", "Zoom Video"],
    "download": ["Steam Download", "APT Mirror", "S3 Transfer"],
    "control":  ["Google Search", "Twitter API", "Slack Msg", "DNS Query"],
}
CLASS_ICON = {"video": "🟣", "download": "🔵", "control": "🟢"}

st.set_page_config(page_title="O-RAN 트래픽 분류 시연", page_icon="📊", layout="wide")


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
    return model, X_test, y_test, y_pred, accuracy_score(y_test, y_pred), len(df)


st.title("📊 암호화 트래픽 유형 분류 — 발표용 시연")

st.error(
    "**이 화면에서 모델이 낸 값은 `Type`(트래픽 유형)과 `Confidence`뿐이다.** "
    "`Est. App`과 `Source IP` 열은 발표 화면을 채우려고 만든 **예시값**이며 "
    "실제 추적 결과가 아니다. 이 프로젝트는 세션의 출처나 접속 서비스를 식별하지 않는다.",
    icon="🚨",
)

result = load_and_train(DATA_PATH)
if result is None:
    st.warning(f"데이터 파일을 찾을 수 없다: `{DATA_PATH}`")
    st.stop()

model, X_test, y_test, y_pred, acc, total_rows = result

tab1, tab2 = st.tabs(["분석 리포트", "세션 로그 재생"])

with tab1:
    st.success(f"테스트셋 정확도: {acc * 100:.2f}%  |  TLS 1.3 암호화 세션 {total_rows}건 "
               f"(학습 {total_rows - len(X_test)} / 테스트 {len(X_test)}, 8:2 stratified split)")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("오차 행렬")
        fig1, ax1 = plt.subplots(figsize=(5, 4))
        sns.heatmap(confusion_matrix(y_test, y_pred), annot=True, fmt="d", cmap="Blues",
                    xticklabels=model.classes_, yticklabels=model.classes_, ax=ax1)
        ax1.set_xlabel("Predicted")
        ax1.set_ylabel("Actual")
        st.pyplot(fig1)
    with col2:
        st.subheader("결정적 특징")
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        imp = pd.Series(model.feature_importances_, index=X_test.columns).sort_values(ascending=False)
        sns.barplot(x=imp, y=imp.index, hue=imp.index, legend=False, palette="viridis", ax=ax2)
        ax2.set_xlabel("importance")
        st.pyplot(fig2)

with tab2:
    st.markdown("#### 저장된 테스트 세션을 순서대로 재생한다 (실시간 캡처 아님)")
    start_btn = st.button("▶ 재생 시작", type="primary")

    kpi_cols = st.columns(4)
    kpi1, kpi2, kpi3, kpi4 = (c.empty() for c in kpi_cols)

    st.divider()
    log_area = st.empty()

    if start_btn:
        counts = {c: 0 for c in model.classes_}
        confidences = []
        logs = []
        rng = np.random.default_rng(42)
        mock_rng = random.Random(42)
        indices = rng.choice(len(X_test), 30, replace=True)

        for i, idx in enumerate(indices):
            sample = X_test.iloc[[idx]]
            pred = model.predict(sample)[0]
            confidence = float(np.max(model.predict_proba(sample)[0]) * 100)

            counts[pred] += 1
            confidences.append(confidence)

            kpi1.metric("분석 세션", f"{i + 1}")
            kpi2.metric("control", f"{counts.get('control', 0)}")
            kpi3.metric("video / download",
                        f"{counts.get('video', 0)} / {counts.get('download', 0)}")
            kpi4.metric("평균 확신도", f"{np.mean(confidences):.1f}%")

            logs.insert(0, {
                "Time": time.strftime("%H:%M:%S"),
                "Type": f"{CLASS_ICON.get(pred, '⚪')} {pred.upper()}",
                "Confidence": f"{confidence:.1f}%",
                "Avg Size": f"{sample['avg_pkt_size'].values[0]:.0f} B",
                "Total Pkts": int(sample["total_packets"].values[0]),
                "Duration": f"{sample['duration'].values[0]:.3f} s",
                # 아래 두 열은 예시값이다 (위 경고 배너 참고)
                "Est. App (예시값)": mock_rng.choice(MOCK_APP_EXAMPLES.get(pred, ["-"])),
                "Source IP (예시값)": f"192.168.0.{mock_rng.randint(10, 250)}",
            })
            log_area.dataframe(pd.DataFrame(logs), use_container_width=True, hide_index=True)
            time.sleep(0.3)

        st.info("재생 완료. 위 표의 `Type`과 `Confidence`만 모델 출력이다.")
