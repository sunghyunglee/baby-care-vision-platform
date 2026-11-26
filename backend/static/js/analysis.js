const ANALYSES_API_URL = "/api/v1/analyses/";

const RESULT_DISPLAY = {
  SAFE: { text: "위험 미감지", color: "green" },
  DANGER: { text: "위험 감지", color: "red" },
};

class AnalysisApiClient {
  async requestAnalysis(videoFile) {
    const formData = new FormData();
    formData.append("video", videoFile);

    // Content-Type은 적지 않는다: 브라우저가 multipart 경계(boundary)를 붙여 직접 채운다
    const response = await fetch(ANALYSES_API_URL, {
      method: "POST",
      headers: { "X-CSRFToken": this.getCsrfToken() },
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    return data.result;
  }

  getCsrfToken() {
    // index.html의 {% csrf_token %}이 만든 숨은 입력칸에서 읽는다 (쿠키 설정과 무관하게 동작)
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
  }
}

class ResultView {
  constructor(resultElement) {
    this.resultElement = resultElement;
  }

  showResult(result) {
    // 계약에 없는 값은 '위험 미감지'처럼 보이면 안 되므로 따로 표시한다
    const display = RESULT_DISPLAY[result] ?? { text: "알 수 없는 결과", color: "gray" };
    this.showMessage(display.text, display.color);
  }

  showMessage(text, color) {
    this.resultElement.textContent = text;
    this.resultElement.style.color = color;
  }
}

class AnalysisPage {
  constructor() {
    this.videoInput = document.getElementById("video-input");
    this.analyzeButton = document.getElementById("analyze-button");
    this.resultView = new ResultView(document.getElementById("result"));
    this.apiClient = new AnalysisApiClient();
  }

  start() {
    this.analyzeButton.addEventListener("click", (event) => this.handleAnalyzeClick(event));
  }

  async handleAnalyzeClick(event) {
    // 버튼이 form 안에 있어도 페이지가 새로고침되지 않게 막는다
    event.preventDefault();

    const videoFile = this.videoInput.files[0];
    if (!videoFile) {
      this.resultView.showMessage("영상을 먼저 선택하세요", "gray");
      return;
    }

    try {
      const result = await this.apiClient.requestAnalysis(videoFile);
      this.resultView.showResult(result);
    } catch (error) {
      this.resultView.showMessage(`분석 실패 (${error.message})`, "gray");
    }
  }
}

document.addEventListener("DOMContentLoaded", () => new AnalysisPage().start());
