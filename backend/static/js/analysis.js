const ANALYSES_API_URL = "/api/v1/analyses/";

const RESULT_DISPLAY = {
  SAFE: { state: "safe", label: "위험 미감지" },
  DANGER: { state: "danger", label: "위험 감지" },
};

function getCsrfToken() {
  // index.html의 {% csrf_token %}이 만든 숨은 입력칸에서 읽는다 (쿠키 설정과 무관하게 동작)
  return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

async function requestAnalysis(videoFile) {
  const formData = new FormData();
  formData.append("video", videoFile);

  // Content-Type은 적지 않는다: 브라우저가 multipart 경계(boundary)를 붙여 직접 채운다
  const response = await fetch(ANALYSES_API_URL, {
    method: "POST",
    headers: { "X-CSRFToken": getCsrfToken() },
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
  return data.result;
}

function showState(state, label, message) {
  // 색·모양은 index.html의 data-state 스타일이 맡으므로 상태와 글자만 바꾼다
  const resultElement = document.getElementById("result");
  resultElement.dataset.state = state;
  resultElement.querySelector("[data-result-label]").textContent = label;
  resultElement.querySelector("[data-result-message]").textContent = message;
}

function showResult(result) {
  // 계약에 없는 값은 '위험 미감지'처럼 보이면 안 되므로 오류로 표시한다
  const display = RESULT_DISPLAY[result] ?? { state: "error", label: "알 수 없는 결과" };
  showState(display.state, display.label, "");
}

async function handleAnalyzeClick(event) {
  // 버튼이 form 안에 있어도 페이지가 새로고침되지 않게 막는다
  event.preventDefault();

  const videoFile = document.getElementById("video-input").files[0];
  if (!videoFile) {
    showState("error", "영상을 먼저 선택하세요", "");
    return;
  }

  // 응답을 기다리는 동안 다시 눌러 같은 영상이 두 번 올라가지 않게 잠근다
  const analyzeButton = document.getElementById("analyze-button");
  analyzeButton.disabled = true;
  showState("loading", "분석 중", "");
  try {
    showResult(await requestAnalysis(videoFile));
  } catch (error) {
    showState("error", "분석 실패", error.message);
  } finally {
    analyzeButton.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("analyze-button").addEventListener("click", handleAnalyzeClick);
});
