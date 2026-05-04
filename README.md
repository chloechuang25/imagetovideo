# Google Veo (Vertex AI / Gemini API) 圖片轉影片工具

這是一個使用 Google 最新 `veo-3.1-fast-generate-preview` 模型將靜態圖片轉換為動態影片的 Python 腳本工具。

腳本中實作了透過提示詞 (Prompt) 搭配主體參考圖片 (Asset Reference) 來生成特殊轉場效果（例如從白紙開始，剪貼簿拼湊，最後拆解回白紙）。

---

## 🛠️ 環境建置 (使用虛擬環境)

強烈建議使用 Python 的虛擬環境來執行此腳本，以避免破壞 macOS 系統預設的 Python 環境套件（即解決 `externally-managed-environment` 錯誤）。

### 1. 建立虛擬環境
打開終端機 (Terminal) 並進入此專案的資料夾，輸入以下指令建立一個名為 `venv` 的虛擬環境：
```bash
python3 -m venv venv
```

### 2. 啟動虛擬環境
每次要執行腳本之前，都需要先啟動虛擬環境：
```bash
source venv/bin/activate
```
*(啟動成功後，終端機的提示字元前方會多出一個 `(venv)` 的標示。)*

### 3. 安裝必要套件
在啟動虛擬環境的狀態下，安裝 Google 官方的 GenAI SDK：
```bash
pip install google-genai
```

*(如果你想離開虛擬環境，只需輸入 `deactivate` 即可)*

---

## 🚀 如何執行腳本

此腳本透過 [Google AI Studio](https://aistudio.google.com/) 取得的 API Key 來進行認證。

### 基本指令格式
確保你已經準備好一張圖片（例如 `中01.jpeg`），並且取得了一組 API Key。

```bash
python image_to_video.py --image "你的圖片檔名.jpg" --api_key "你的_API_KEY" --prompt "你的英文提示詞"
```

### 剪貼簿特效 (Scrapbook Effect) 完整執行範例
你可以直接複製以下指令（請記得把 API Key 換成你自己的），這個 Prompt 會讓畫面從一張白紙開始，像剪貼簿一樣把你的圖片拼湊出來，動起來後，再自動拆解變回白紙。

```bash
python image_to_video.py \
  --image "中01.jpeg" \
  --api_key "YOUR_GOOGLE_API_KEY" \
  --prompt "Start with a solid white, empty screen. Pieces of a scrapbook magically fly in and assemble to form a scene featuring the subject in the reference image. Once fully assembled, the scene briefly comes to life and the subject moves. Finally, the scrapbook pieces peel away and disassemble, leaving a solid white screen again."
```

### 參數說明
* `--image`: (必填) 你要參考的圖片路徑（支援中文檔名）。
* `--prompt`: (必填) 決定影片演出內容的提示詞，建議使用英文以獲得最佳效果。
* `--api_key`: (選填) Google AI Studio 申請的 API Key。如果不想每次都輸入，也可以設定為環境變數 `export GOOGLE_API_KEY="你的_API_KEY"`。
* `--output`: (選填) 生成影片的存檔名稱，預設為 `output_video.mp4`。

---

## 📝 關於 API 的限制說明
目前透過 Gemini Developer API (API Key) 呼叫 Veo 預覽版模型 (`veo-3.1-fast-generate-preview`) 有以下已知限制：
1. **不支援配樂生成 (`generate_audio`)**：若要生成音效需使用 Google Cloud 企業版 (Vertex AI)。
2. **不支援負面提示詞 (`negative_prompt`)**。
3. **不支援提示詞擴寫 (`enhance_prompt`)**。
4. **回傳格式**：需確保 SDK 版本為最新，並使用 `client.files.download` 解析回傳的二進位影片內容 (`bytes`)。

本專案的 `image_to_video.py` 已經將上述限制與錯誤排除，並實作了最穩定的生成流程。
