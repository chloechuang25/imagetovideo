import time
import argparse
import os
import subprocess
from google import genai
from google.genai.types import GenerateVideosConfig, Image

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../storybook/assets"))

def generate_transition(image_path, output_prefix, api_key=None, assets_dir=None):
    # 決定輸出資料夾，預設為 storybook/assets/
    out_dir = assets_dir if assets_dir else ASSETS_DIR
    os.makedirs(out_dir, exist_ok=True)
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

    # 步驟 1：呼叫 Gemini Vision 分析圖片，產生針對此圖的客製化 Veo Prompt
    print("🔍 正在呼叫 Gemini Vision 分析圖片內容，產生客製化轉場 Prompt...")
    from google.genai.types import Part, GenerateContentConfig
    import base64

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    mime = "image/jpeg" if image_path.lower().endswith(("jpg", "jpeg")) else "image/png"

    vision_system_prompt = (
        "You are an expert AI video prompt engineer specializing in Veo, Google's video generation model.\n"
        "Your task: analyze the provided image and write a highly specific, detailed Veo video prompt "
        "for a scrapbook-style disassembly animation.\n\n"

        "WHAT TO INCLUDE in your prompt:\n"
        "1. ART STYLE: Describe the illustration style of the image (e.g. hand-drawn, watercolor, crayon, digital painting)\n"
        "2. START FRAME: State that the video begins with the image as a static start frame\n"
        "3. ELEMENT IDENTIFICATION: Name every major visual element specifically — describe each character's appearance "
        "(clothing color, expression, pose), each object, and the background in detail\n"
        "4. CUTOUT TRANSFORMATION: Describe how elements are instantly cut out with jagged white paper edges, "
        "becoming scrapbook-style stickers\n"
        "5. MOTION: Describe how each specific element moves — drift apart, rotate slowly, peel away in fragments, "
        "scatter toward the edges. Include a slow camera zoom out.\n"
        "6. TEXTURE PRESERVATION: State that the original art style textures must be maintained throughout\n"
        "7. END STATE: The video must conclude with all elements flown off-screen, leaving a 100% solid white canvas\n\n"

        "EXAMPLE OUTPUT (for a different image — use this as a style reference only):\n"
        "\"The video begins with the hand-drawn colored pencil illustration as the static start frame. "
        "Suddenly, the main elements—the crying boy in the blue sweater, the vibrant rainbow spiral portal, "
        "the large crowned cockroach, and the smaller insects—are instantly cut out with jagged white paper edges, "
        "transforming into scrapbook-style stickers. These paper elements begin to drift apart and rotate slowly "
        "as if caught in a gentle breeze. The grey scribbled background peels away in fragments, revealing a bright "
        "white space behind it. The camera slowly zooms out as all the cutout characters and the portal scatter toward "
        "the edges of the frame and disappear. The motion is smooth and whimsical, maintaining the original crayon and "
        "pencil textures. The video concludes with all elements having flown off-screen, leaving a clean, 100% solid white canvas.\"\n\n"

        "Now write the same style of prompt for the provided image. "
        "Output ONLY the final Veo prompt. No explanations, no preamble, no bullet points."
    )

    try:
        vision_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                Part.from_bytes(data=image_bytes, mime_type=mime),
                "Analyze this image and write the scrapbook disassembly animation prompt."
            ],
            config=GenerateContentConfig(
                system_instruction=vision_system_prompt,
                temperature=0.7
            )
        )
        prompt_transition = vision_response.text.strip()
        print(f"✨ Gemini Vision 產生的客製化 Prompt:\n{prompt_transition}\n")
    except Exception as e:
        print(f"⚠️ Gemini Vision 呼叫失敗，使用備用 Prompt。錯誤：{e}")
        prompt_transition = (
            "A handcrafted scrapbook disassembly animation. "
            "Each element gently wobbles, curls at its edges, and drifts softly off screen. "
            "The final frame is a completely blank white canvas with nothing on it."
        )

    # 步驟 2：將客製化 Prompt 送給 Veo 生成影片

    operation = client.models.generate_videos(
        model="veo-3.1-fast-generate-preview",
        prompt=prompt_transition,
        image=input_frame,
        config=GenerateVideosConfig(
            aspect_ratio="16:9",
            duration_seconds=4,
            resolution="720p"
        )
    )

    print("等待影片生成完成 (通常需要 2~5 分鐘，請耐心等候)...")
    elapsed = 0
    while not operation.done:
        time.sleep(15)
        elapsed += 15
        print(f"生成中... (已等待 {elapsed} 秒)")
        operation = client.operations.get(operation)

    if operation.response and operation.response.generated_videos:
        video = operation.response.generated_videos[0]
        disassemble_path = os.path.join(out_dir, f"{output_prefix}_disassemble.mp4")
        
        if video.video.video_bytes:
            with open(disassemble_path, "wb") as f:
                f.write(video.video.video_bytes) 
        elif video.video.uri:
            print("正在下載影片...")
            video_bytes = client.files.download(file=video.video.uri)
            with open(disassemble_path, "wb") as f:
                f.write(video_bytes)
                
        print(f"✅ 成功儲存拆解影片：{disassemble_path}")
        
        assemble_path = os.path.join(out_dir, f"{output_prefix}_assemble.mp4")
        print(f"正在使用 FFmpeg 倒轉產生：{assemble_path}...")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", disassemble_path, "-vf", "reverse", "-an", assemble_path],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            print(f"✅ 成功生成組合影片：{assemble_path}")
        except Exception as e:
            print(f"❌ FFmpeg 倒轉失敗: {e}")
    else:
        print("\n❌ 影片生成失敗！API 回應中沒有影片資料。")
        print(f"   Operation done: {operation.done}")
        print(f"   Operation response: {operation.response}")
        print(f"   Operation error: {getattr(operation, 'error', 'N/A')}")
        print("\n💡 建議：Prompt 可能觸發了內容安全過濾器，已自動使用更溫和的 Prompt，請重新執行一次試試看。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成轉場影片(拆解與組合)")
    parser.add_argument("--image", required=True, help="輸入的圖片路徑")
    parser.add_argument("--prefix", default="page1", help="輸出的檔名前綴 (預設: page1)")
    parser.add_argument("--api_key", default=None, help="Google AI Studio API Key (選填)")
    parser.add_argument("--assets_dir", default=None, help=f"輸出資料夾 (預設: {ASSETS_DIR})")
    args = parser.parse_args()
    generate_transition(args.image, args.prefix, args.api_key, args.assets_dir)
