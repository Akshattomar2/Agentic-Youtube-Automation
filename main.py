# ============================================================
#  YouTube Shorts Automation — CrewAI + Groq + Pollinations
# ============================================================
#  Setup:
#    pip install crewai moviepy edge-tts requests pillow numpy
#                google-api-python-client google-auth-oauthlib
#
#  Set environment variables before running:
#    export GROQ_API_KEY="your_groq_key_here"
#
#  Place client_secrets.json (Google OAuth) in the same folder.
# ============================================================

# --- Monkey patch (must be before moviepy import) -----------
import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

import ast
import asyncio
import json
import os
import sys

import edge_tts
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

from crewai import Agent, Crew, Process, Task
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

# ── Environment ──────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
if not groq_key:
    sys.exit("❌  GROQ_API_KEY environment variable not set.")

os.environ["OPENAI_API_BASE"]   = "https://api.groq.com/openai/v1"
os.environ["OPENAI_MODEL_NAME"] = "llama-3.3-70b-versatile"
os.environ["OPENAI_API_KEY"]    = groq_key

# ── Config ───────────────────────────────────────────────────
VIDEO_TOPIC    = "The bizarre history of the world's most expensive spice, Saffron"
VIDEO_SIZE     = (1080, 1920)   # portrait / Shorts
THUMBNAIL_SIZE = (1280, 720)    # landscape / YouTube thumbnail
FONT_SIZE      = 55
OUTPUT_VIDEO   = "final_shorts_video.mp4"
OUTPUT_THUMB   = "custom_thumbnail.jpg"
YT_SCOPES      = ["https://www.googleapis.com/auth/youtube.upload"]

# ── CrewAI Agents ────────────────────────────────────────────
script_writer = Agent(
    role="Expert YouTube Growth Manager",
    goal="Create engaging scripts and optimise YouTube SEO metadata (title, tags, description).",
    backstory="You know exactly how to hook viewers and optimise algorithms to push vertical shorts viral.",
    verbose=True,
)

video_planner = Agent(
    role="Visual Director",
    goal="Break down a script into visual scenes, create image prompts, and design a high-CTR thumbnail concept.",
    backstory="You translate concepts into striking imagery for video segments and high-clickability banners.",
    verbose=True,
)

# ── Tasks ────────────────────────────────────────────────────
task_write_script = Task(
    description=f"Write a fast-paced 60-second narration script about: {VIDEO_TOPIC}.",
    expected_output="Compelling paragraphs-only narration text — no brackets, no stage directions.",
    agent=script_writer,
)

task_plan_scenes = Task(
    description=(
        "Break down the narration into exactly 4 sequential scenes. "
        "For each scene provide an 'image_prompt' and the matching 'narration_text'. "
        "Also output a single 'thumbnail_prompt' for a high-CTR concept, "
        "a catchy 'youtube_title', and a 'youtube_description' packed with hashtags. "
        "Output ONLY valid raw JSON — no markdown, no extra text — matching: "
        '{"scenes":[{"image_prompt":"...","narration_text":"..."},...], '
        '"thumbnail_prompt":"...","youtube_title":"...","youtube_description":"..."}'
    ),
    expected_output='Raw JSON with keys: "scenes", "thumbnail_prompt", "youtube_title", "youtube_description".',
    agent=video_planner,
    dependencies=[task_write_script],
)

# ── Helpers ──────────────────────────────────────────────────
def parse_agent_output(raw: str) -> dict:
    """Robustly parse JSON from the agent's output string."""
    # Strip markdown code fences if present
    for fence in ("```json", "```"):
        if fence in raw:
            raw = raw.split(fence)[1].split("```")[0].strip()
            break

    for parser in (json.loads, ast.literal_eval):
        try:
            result = parser(raw)
            if isinstance(result, dict):
                return result
        except Exception:
            continue

    # Last resort: swap single quotes → double quotes
    try:
        return json.loads(raw.replace("'", '"'))
    except Exception as err:
        print("FATAL: Could not parse agent output:\n", raw)
        raise err


def _ensure_scene_defaults(data: dict) -> dict:
    """Fill in fallback values if the agent omitted optional keys."""
    if isinstance(data, list):
        data = {"scenes": data}

    data.setdefault(
        "thumbnail_prompt",
        "Cinematic close-up of vivid Saffron threads on a gold scale, hyper-detailed, 8k",
    )
    data.setdefault("youtube_title", "The Bizarre History of the World's Most Expensive Spice!")
    data.setdefault(
        "youtube_description",
        "Discover the crazy history of Saffron! #shorts #history #saffron",
    )
    return data


def download_image(prompt: str, path: str, width: int, height: int) -> None:
    encoded = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/p/{encoded}?width={width}&height={height}&seed=42"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with open(path, "wb") as f:
        f.write(r.content)


async def generate_voiceover(text: str, path: str) -> None:
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(path)


def create_subtitle_clip(text: str, duration: float, start: float):
    img = Image.new("RGBA", VIDEO_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    x = (VIDEO_SIZE[0] - (bbox[2] - bbox[0])) // 2
    y = int(VIDEO_SIZE[1] * 0.75)
    draw.text((x, y), text, font=font, fill=(255, 255, 0, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))

    return (
        ImageClip(np.array(img))
        .set_start(start)
        .set_duration(duration)
        .set_pos(("center", "top"))
    )


def upload_to_youtube(video_path: str, thumbnail_path: str, title: str, description: str) -> None:
    print("\n🔐 Authenticating with YouTube...")
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", YT_SCOPES)
    credentials = flow.run_local_server(port=0)
    youtube = build("youtube", "v3", credentials=credentials)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["shorts", "history", "spices", "ai"],
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    print("📤 Uploading video...")
    response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
    video_id = response["id"]
    print(f"✅ Uploaded! Video ID: {video_id}")

    print("🖼️  Attaching thumbnail...")
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
    ).execute()
    print("🎉 Done! Check your YouTube channel.")


# ── Main Pipeline ────────────────────────────────────────────
def main():
    # Step 1 — Run CrewAI
    crew = Crew(
        agents=[script_writer, video_planner],
        tasks=[task_write_script, task_plan_scenes],
        process=Process.sequential,
    )
    print("🚀 Starting CrewAI workflow...")
    result = crew.kickoff()

    # Step 2 — Parse output
    data = _ensure_scene_defaults(parse_agent_output(str(result)))
    print("✅ Agent output parsed successfully.")

    # Step 3 — Build video scenes
    video_clips, subtitle_clips, current_time = [], [], 0.0

    for i, scene in enumerate(data["scenes"]):
        print(f"\n🎬 Processing scene {i + 1} / {len(data['scenes'])}...")
        img_path   = f"scene_{i}.jpg"
        audio_path = f"scene_{i}.mp3"

        download_image(scene["image_prompt"], img_path, *VIDEO_SIZE)
        asyncio.run(generate_voiceover(scene["narration_text"], audio_path))

        audio = AudioFileClip(audio_path)
        clip  = (
            ImageClip(img_path)
            .set_duration(audio.duration)
            .resize(lambda t, d=audio.duration: 1.0 + 0.15 * (t / d))
            .set_position(("center", "center"))
            .set_audio(audio)
        )
        video_clips.append(clip)
        subtitle_clips.append(create_subtitle_clip(scene["narration_text"], audio.duration, current_time))
        current_time += audio.duration

    # Step 4 — Render final video
    print("\n🎞️  Rendering final video...")
    base = concatenate_videoclips(video_clips, method="compose")
    CompositeVideoClip([base] + subtitle_clips).write_videofile(
        OUTPUT_VIDEO, fps=24, codec="libx264", audio_codec="aac"
    )

    # Step 5 — Download thumbnail
    print("\n🖼️  Downloading thumbnail...")
    download_image(data["thumbnail_prompt"], OUTPUT_THUMB, *THUMBNAIL_SIZE)

    # Step 6 — Upload to YouTube
    upload_to_youtube(OUTPUT_VIDEO, OUTPUT_THUMB, data["youtube_title"], data["youtube_description"])


if __name__ == "__main__":
    main()
