import time
import argparse
import os
from google import genai
from google.genai.types import GenerateVideosConfig, Image, GenerateContentConfig

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../storybook/assets"))

def generate_character_loop(image_path, prompt, output_filename=None, api_key=None, enhance=True, assets_dir=None):
    # 決定輸出資料夾，預設為 storybook/assets/
    out_dir = assets_dir if assets_dir else ASSETS_DIR
    os.makedirs(out_dir, exist_ok=True)
    filename = output_filename if output_filename else "page1_action.mp4"
    output_path = os.path.join(out_dir, filename)
    print(f"📂 輸出資料夾：{out_dir}")

    print("初始化 Google GenAI 客戶端...")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    print(f"讀取圖片: {image_path}...")
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    input_frame = Image(
        image_bytes=image_bytes,
        mime_type="image/jpeg" if image_path.lower().endswith(("jpg", "jpeg")) else "image/png"
    )

    if enhance:
        print("正在呼叫 Gemini 模型優化主角動畫提示詞...")
        system_instruction = (
            "You are an expert prompt engineer for AI video models like Veo. "
            "The user will provide an idea for a CHARACTER animation video that involves a REFERENCE IMAGE. "
            "Your top priority is to expand the user's idea into a detailed, cinematic video prompt in English.\n"
            "CRITICAL: You MUST explicitly instruct that the video must end exactly as it started, returning the character to its original static pose (looping back to the original state).\n\n"
            "CRITICAL FIDELITY RULES:\n"
            "1. The reference image must be reproduced with 100% strict visual fidelity.\n"
            "2. Do NOT reinterpret, stylize, or alter the reference image in any way.\n"
            "3. Explicitly state in the prompt: 'Maintain absolute pixel-perfect fidelity to the reference image.'\n"
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
            print(f"✨ 優化後的提示詞: {prompt_main}")
        except Exception as e:
            print(f"提示詞優化失敗，將使用原始提示詞。錯誤: {e}")
            prompt_main = prompt
    else:
        prompt_main = prompt

    print("啟動主角循環影片生成任務 (首尾幀相同)...")
    operation = client.models.generate_videos(
        model="veo-3.1-fast-generate-preview",
        prompt=prompt_main,
        image=input_frame,
        config=GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=4, # 可視需求調整
            resolution="720p",
            last_frame=input_frame # 強制最後一幀等於第一幀
        )
    )

    print("等待影片生成完成...")
    while not operation.done:
        time.sleep(15)
        print("生成中...")
        operation = client.operations.get(operation)

    if operation.response and operation.response.generated_videos:
        video = operation.response.generated_videos[0]
        if video.video.video_bytes:
            with open(output_path, "wb") as f:
                f.write(video.video.video_bytes) 
        elif video.video.uri:
            print("正在下載影片...")
            video_bytes = client.files.download(file=video.video.uri)
            with open(output_path, "wb") as f:
                f.write(video_bytes)
        print(f"✅ 主角互動影片儲存成功：{output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成首尾相同的主角互動影片 (Action)")
    parser.add_argument("--image", required=True, help="輸入的圖片路徑")
    parser.add_argument("--prompt", required=True, help="主角動畫提示詞")
    parser.add_argument("--output", default="page1_action.mp4", help="輸出的檔名 (預設: page1_action.mp4)")
    parser.add_argument("--api_key", default=None, help="API Key (選填)")
    parser.add_argument("--no-enhance", dest="enhance", action="store_false", help="關閉 Gemini 自動優化提示詞 (預設為開啟)")
    parser.set_defaults(enhance=True)
    parser.add_argument("--assets_dir", default=None, help=f"輸出資料夾 (預設: {ASSETS_DIR})")
    args = parser.parse_args()
    generate_character_loop(args.image, args.prompt, args.output, args.api_key, args.enhance, args.assets_dir)
