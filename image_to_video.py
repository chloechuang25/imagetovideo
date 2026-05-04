import time
import argparse
import tempfile
import shutil
import os
import subprocess
from google import genai
from google.genai.types import GenerateVideosConfig, Image, VideoGenerationReferenceImage, GenerateContentConfig

def process_video_reverse_concat(main_video_path, transition_video_path, output_video_path):
    print(f"🎬 正在使用 FFmpeg 進行三段式拼接處理...")
    try:
        # 1. 產生倒播的轉場影片 (空白 -> 浮現)
        reversed_transition = "temp_reversed_trans.mp4"
        print("   -> 步驟 1: 生成倒播轉場影片...")
        subprocess.run(
            ["ffmpeg", "-y", "-i", transition_video_path, "-vf", "reverse", "-an", reversed_transition],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        # 2. 移除所有音軌以確保 concat 不會因音軌不匹配失敗
        muted_main = "temp_muted_main.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", main_video_path, "-an", "-c:v", "copy", muted_main],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        muted_trans = "temp_muted_trans.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-i", transition_video_path, "-an", "-c:v", "copy", muted_trans],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        # 3. 建立拼接清單
        list_file = "temp_concat_list.txt"
        with open(list_file, "w") as f:
            f.write(f"file '{os.path.abspath(reversed_transition)}'\n")
            f.write(f"file '{os.path.abspath(muted_main)}'\n")
            f.write(f"file '{os.path.abspath(muted_trans)}'\n")
        
        # 4. 拼接三段影片
        print("   -> 步驟 2: 拼接影片 (浮現 + 主動畫 + 拆解)...")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", output_video_path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        
        # 5. 清理暫存檔
        for f in [reversed_transition, muted_main, muted_trans, list_file]:
            if os.path.exists(f): os.remove(f)
            
        print(f"✅ 三段式特效影片製作完成！最終檔案：{output_video_path}")
        return True
    except FileNotFoundError:
        print("❌ 找不到 FFmpeg！請確保你的系統已經安裝 FFmpeg (Mac 終端機請執行 brew install ffmpeg)。")
        return False
    except subprocess.CalledProcessError:
        print(f"❌ FFmpeg 處理失敗。")
        return False
    except Exception as e:
        print(f"❌ 發生未知的錯誤：{e}")
        return False


def generate_video(image_path, prompt, output_path=None, api_key=None, enhance=False):
    # 如果沒有指定輸出檔名，自動用當下時間產生一個不會重複的檔名
    if not output_path:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output_video_{timestamp}.mp4"

    # 初始化客戶端 (可以透過 API Key 或是設定好 GOOGLE_APPLICATION_CREDENTIALS)
    print("初始化 Google GenAI 客戶端...")
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        client = genai.Client()

    # 1. 讀取圖片檔案內容
    print(f"讀取圖片: {image_path}...")
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 預設的轉場解構提示詞 (Scrapbook style)
    default_transition_prompt = (
        "A cinematic scrapbook style animation. The subject is cut out into small paper pieces that "
        "fly outwards in all directions rapidly, leaving a completely blank white screen. "
        "Maintain absolute pixel-perfect fidelity to the reference image."
    )

    # 2. 處理提示詞 (自動優化或使用預設)
    if enhance:
        print("正在呼叫 Gemini 模型優化主動畫提示詞...")
        system_instruction = (
            "You are an expert prompt engineer for AI video models like Veo. "
            "The user will provide an idea for a video that involves a REFERENCE IMAGE. "
            "Your top priority is to expand the user's idea into a detailed, cinematic video prompt in English.\n"
            "CRITICAL: You MUST explicitly instruct that the video must end exactly as it started, returning the subject to its original static pose (looping back to the original state).\n\n"
            "CRITICAL FIDELITY RULES:\n"
            "1. The reference image subject must be reproduced with 100% strict visual fidelity: exact same colors, shapes, composition, textures, and details.\n"
            "2. Do NOT reinterpret, stylize, or alter the reference image in any way.\n"
            "3. Explicitly state in the prompt: 'Maintain absolute pixel-perfect fidelity to the reference image. Reproduce all visual elements, colors, and details exactly as shown.'\n"
            "\nOutput ONLY the final optimized prompt, no explanations."
        )
        try:
            llm_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7
                )
            )
            prompt_main = llm_response.text.strip()
            print(f"✨ 優化後的主提示詞: {prompt_main}")
        except Exception as e:
            print(f"提示詞優化失敗，將使用原始提示詞。錯誤訊息: {e}")
            prompt_main = prompt
    else:
        prompt_main = prompt
        
    prompt_transition = default_transition_prompt

    # 3. 設定生成請求參數
    model_name = "veo-3.1-fast-generate-preview" # 由於是使用 AI Studio API Key，需要使用 preview 版本模型
    
    print(f"開始同時生成兩支影片 (模型: {model_name})...")
    
    # 建立輸入圖片的 Image 物件 (將作為頭尾幀)
    input_frame = Image(
        image_bytes=image_bytes,
        mime_type="image/jpeg" if image_path.lower().endswith(("jpg", "jpeg")) else "image/png"
    )

    # 3-1. 呼叫主影片生成 (第一幀和最後一幀都是輸入圖片)
    print(" -> 啟動 主影片(Main) 生成任務...")
    operation_main = client.models.generate_videos(
        model=model_name,
        prompt=prompt_main,
        image=input_frame, # 控制第一幀
        config=GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=8,
            resolution="720p",
            last_frame=input_frame # 控制最後一幀
        )
    )

    # 3-2. 呼叫轉場影片生成 (第一幀是輸入圖片，化為空白所以沒有最後一幀)
    print(" -> 啟動 轉場影片(Transition) 生成任務...")
    operation_transition = client.models.generate_videos(
        model=model_name,
        prompt=prompt_transition,
        image=input_frame, # 控制第一幀
        config=GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=8,
            resolution="720p"
        )
    )

    # 4. 輪詢直到兩者皆完成
    print("等待兩支影片生成完成（這可能需要幾分鐘的時間）...")
    while not (operation_main.done and operation_transition.done):
        time.sleep(15) # 每 15 秒檢查一次狀態
        status_main = "完成" if operation_main.done else "生成中..."
        status_trans = "完成" if operation_transition.done else "生成中..."
        print(f"檢查狀態中... 主影片: [{status_main}] | 轉場影片: [{status_trans}]")
        
        if not operation_main.done:
            operation_main = client.operations.get(operation_main)
        if not operation_transition.done:
            operation_transition = client.operations.get(operation_transition)

    # 5. 處理結果並下載
    print("生成任務結束，準備下載影片...")
    
    def download_video(operation, prefix):
        if operation.response and operation.response.generated_videos:
            video = operation.response.generated_videos[0]
            temp_path = f"temp_{prefix}_{os.path.basename(output_path)}"
            if video.video.video_bytes:
                with open(temp_path, "wb") as f:
                    f.write(video.video.video_bytes) 
                return temp_path
            elif video.video.uri:
                print(f"正在從 {video.video.uri} 下載 {prefix} 影片...")
                video_bytes = client.files.download(file=video.video.uri)
                with open(temp_path, "wb") as f:
                    f.write(video_bytes)
                return temp_path
        return None

    temp_main_path = download_video(operation_main, "main")
    temp_trans_path = download_video(operation_transition, "trans")

    if temp_main_path and temp_trans_path:
        print("下載完成！準備進行三段式後製拼接...")
        success = process_video_reverse_concat(temp_main_path, temp_trans_path, output_path)
        if success:
            if os.path.exists(temp_main_path): os.remove(temp_main_path)
            if os.path.exists(temp_trans_path): os.remove(temp_trans_path)
        else:
            print("⚠️ 拼接失敗，為您保留原始的影片檔案供檢查。")
    else:
        print("❌ 部分影片生成或下載失敗，無法進行拼接。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用 Google Veo (Vertex AI) 將圖片轉為影片")
    parser.add_argument("--image", required=True, help="輸入的圖片路徑 (例如: input.jpg)")
    parser.add_argument("--prompt", required=True, help="影片生成的提示詞 (例如: 'A cinematic animation of the subject moving')")
    parser.add_argument("--output", default=None, help="輸出的影片路徑 (預設會自動產生加上時間戳記的檔名，如 output_video_20260503_205800.mp4)")
    parser.add_argument("--api_key", default=None, help="你的 Google AI Studio API Key (選填)")
    parser.add_argument("--enhance", action="store_true", help="是否要先使用 Gemini 自動優化你的提示詞 (選填)")
    
    args = parser.parse_args()
    
    generate_video(args.image, args.prompt, args.output, args.api_key, args.enhance)
