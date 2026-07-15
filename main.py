mport PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

import os
import sys
import json
import random
import logging
import asyncio
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field
from typing import List

import edge_tts
from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_KEY:
    log.critical("GROQ_API_KEY missing from your local .env file! Please add it there.")
    sys.exit(1)

os.environ["OPENAI_API_BASE"]   = "https://api.groq.com/openai/v1"
os.environ["OPENAI_MODEL_NAME"] = "llama-3.3-70b-versatile"
os.environ["OPENAI_API_KEY"]    = GROQ_KEY

VIDEO_W        = 1080
VIDEO_H        = 1920
VIDEO_FPS      = 24
OUTPUT_VIDEO   = "final_shorts_video.mp4"
OUTPUT_THUMB   = "thumbnail.jpg"
FONT_SIZE      = 65             
CAPTION_Y_FRAC = 0.55          
YT_SCOPES      = ["https://www.googleapis.com/auth/youtube.upload"]

TOPICS = [
    "turmeric", "saffron", "black_pepper", "vanilla", 
    "cinnamon", "nutmeg", "cardamom", "cloves", "long_pepper", "paprika"
]

class Scene(BaseModel):
    narration: str = Field(description="Fast-paced, highly dramatic 8 to 10-second narration text.")
    image_prompt: str = Field(description="Cinematic detailed description for Pollinations AI to draw.")

class VideoStory(BaseModel):
    angle_title: str = Field(description="Viral title based on the researched angle.")
    scenes: List[Scene] = Field(description="Strict list of exactly 4 sequential scenes.", min_length=4, max_length=4)

def clear_old_cache():
    """Ensures absolutely zero leaking of old clips from previous pipeline iterations."""
    log.info("Cleaning up historical cache workspace...")
    files_to_remove = [OUTPUT_VIDEO, OUTPUT_THUMB]
    for i in range(10):
        files_to_remove.extend([f"scene_{i}_voice.mp3", f"scene_{i}_ai.jpg"])
    
    for file in files_to_remove:
        if os.path.exists(file):
            try:
                os.remove(file)
            except Exception:
                pass

def generate_autonomous_story(topic: str) -> VideoStory:
    researcher = Agent(
        role="Senior Historical Detective",
        goal="Brainstorm a shocking, bizarre, or lesser-known dark historical incident about the requested topic.",
        backstory="Master of hidden histories. You dig up forgotten wars, ancient medicinal thefts, or secrets.",
        verbose=False,
    )

    script_writer = Agent(
        role="Viral Shorts Producer",
        goal="Format the historical incident into a high-retention 40-second script split across 4 scenes with image prompts.",
        backstory="YouTube Shorts editing wizard. You structure narration into 4 punchy segments with perfect descriptive prompts.",
        verbose=False,
    )

    task_research = Task(
        description=f"Find a unique, dramatic, or scandalous historical fact about '{topic}'. Focus on high-drama true stories.",
        expected_output="A summarized historical angle or story selected.",
        agent=researcher,
    )

    task_write_script = Task(
        description=(
            "Using the researched angle, generate a 4-scene blueprint mapping out narration and image prompts. "
            "You MUST output raw JSON text only matching this exact structure: \n"
            "{\n"
            '  "angle_title": "Viral Hook Title Here",\n'
            '  "scenes": [\n'
            '    {"narration": "8-10 second fast narration text", "image_prompt": "Cinematic visual description for AI graphics generation"},\n'
            '    {"narration": "...", "image_prompt": "..."},\n'
            '    {"narration": "...", "image_prompt": "..."},\n'
            '    {"narration": "...", "image_prompt": "..."}\n'
            "  ]\n"
            "}\n"
            "Do not output markdown blocks like ```json, just output clean raw text starting with '{' and ending with '}'."
        ),
        expected_output="A raw JSON string containing angle_title and exactly 4 scenes.",
        agent=script_writer,
        dependencies=[task_research]
    )

    crew = Crew(agents=[researcher, script_writer], tasks=[task_research, task_write_script], process=Process.sequential)
    result = crew.kickoff()
    
    raw_output = str(result.raw).strip()
    
    if "```json" in raw_output:
        raw_output = raw_output.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_output:
        raw_output = raw_output.split("```")[1].split("```")[0].strip()
        
    try:
        data = json.loads(raw_output)
        return VideoStory(**data)
    except Exception as e:
        log.error(f"JSON Parsing failed. Falling back to structured backup template. Error: {e}")
        return VideoStory(
            angle_title=f"The Forbidden Mystery of {topic.title()}",
            scenes=[
                Scene(narration=f"History hides dark secrets about {topic}. Secrets kept under lock and key.", image_prompt=f"Cinematic historic dark mystery visual of {topic}, cinematic lighting"),
                Scene(narration="Powerful empires fought silent bloody wars over this resource.", image_prompt=f"Ancient royal storehouses filled with {topic}, guards watching, dramatic atmosphere"),
                Scene(narration="A strange ancient law made possession punishable by death.", image_prompt="Dark medieval courtroom, judge pointing finger angrily, historical accuracy"),
                Scene(narration="And today, you still use it completely unaware of its bloody past.", image_prompt=f"Modern cinematic kitchen close up showing {topic} spilling on counter, high detail 8k")
            ]
        )

def download_pollinations_image(prompt: str, out_path: str) -> str:
    log.info(f"🎨 Rendering fresh Pollinations Image for prompt: '{prompt[:40]}...'")
    
    clean_prompt = prompt.strip()
    encoded_prompt = requests.utils.quote(clean_prompt)
    
    base_parts = ["https://", "image.pollinations.ai", "/p/"]
    base_url = "".join(base_parts)
    
    url = f"{base_url}{encoded_prompt}?width={VIDEO_W}&height={VIDEO_H}&seed={random.randint(1, 99999)}"
    
    try:
        r = requests.get(url, timeout=45)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)
        return out_path
    except Exception as e:
        log.error(f"❌ Image engine failure: {e}")
        raise

async def _tts(text: str, path: str) -> None:
    await edge_tts.Communicate(text, "en-US-ChristopherNeural").save(path)

def generate_voiceover(text: str, path: str) -> None:
    try:
        asyncio.run(_tts(text, path))
    except Exception as e:
        log.error("TTS failed: %s", e)
        raise

def make_ken_burns_clip(image_path: str, duration: float) -> ImageClip:
    """Applies continuous zoom styling on pure image files."""
    try:
        clip = ImageClip(image_path).set_duration(duration)
        animated_clip = clip.resize(lambda t: 1.0 + 0.18 * (t / duration))
        return animated_clip.set_position(('center', 'center'))
    except Exception as e:
        log.error(f"Ken Burns rendering failure: {e}")
        raise

def generate_captions_for_scene(text: str, total_duration: float, start_timeline: float) -> List[ImageClip]:
    words = text.split()
    chunks = []
    chunk_size = 3  
    
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i + chunk_size]))
    
    num_chunks = len(chunks)
    if num_chunks == 0:
        return []
        
    chunk_duration = total_duration / num_chunks
    caption_clips = []

    for idx, chunk_text in enumerate(chunks):
        chunk_start = start_timeline + (idx * chunk_duration)
        img = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", FONT_SIZE)
        except IOError:
            font = ImageFont.load_default()

        lines = []
        words_in_chunk = chunk_text.split()
        if len(words_in_chunk) > 2:
            lines.append(" ".join(words_in_chunk[:2]))
            lines.append(" ".join(words_in_chunk[2:]))
        else:
            lines.append(chunk_text)

        line_h = FONT_SIZE + 10
        total_h = line_h * len(lines)
        y_start = int(VIDEO_H * CAPTION_Y_FRAC) - total_h // 2

        for line_idx, ln in enumerate(lines):
            ln = ln.upper()
            bbox = draw.textbbox((0, 0), ln, font=font)
            x = (VIDEO_W - (bbox[2] - bbox[0])) // 2
            y = y_start + line_idx * line_h
            
            draw.text((x, y), ln, font=font, fill=(255, 255, 0, 255),
                      stroke_width=6, stroke_fill=(0, 0, 0, 255))

        cap_clip = (
            ImageClip(np.array(img))
            .set_start(chunk_start)
            .set_duration(chunk_duration)
            .set_pos(("center", "top"))
        )
        caption_clips.append(cap_clip)

    return caption_clips

def upload_to_youtube(video_path: str, thumb_path: str, title: str, description: str) -> None:
    if not os.path.exists("client_secrets.json"):
        log.warning("⚠️ Manual upload required — client_secrets configuration file not found.")
        return

    try:
        flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", YT_SCOPES)
        creds = flow.run_local_server(port=0, authorization_prompt_message="")
        youtube = build("youtube", "v3", credentials=creds)
        
        body = {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": ["shorts", "history", "facts", "ai", "automation"],
                "categoryId": "22",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        response = youtube.videos().insert(part="snippet,status", body=body, media_body=media).execute()
        video_id = response["id"]
        log.info(f"✅ Upload Complete! ID: {video_id}")
        
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg"),
        ).execute()
        
    except Exception as e:
        log.error(f"YouTube Upload Failed: {e}")

def run_pipeline(topic_key: str) -> None:
    clear_old_cache()
    
    story_data = generate_autonomous_story(topic_key)
    log.info(f"🧠 AI Blueprint Ready: '{story_data.angle_title}'")

    scene_clips = []
    caption_clips = []
    timeline = 0.0

    for i, scene in enumerate(story_data.scenes):
        audio_path = f"scene_{i}_voice.mp3"
        image_path = f"scene_{i}_ai.jpg"

        generate_voiceover(scene.narration, audio_path)
        download_pollinations_image(scene.image_prompt, image_path)

        try:
            audio = AudioFileClip(audio_path)
            bg_clip = make_ken_burns_clip(image_path, audio.duration).set_audio(audio)
            scene_clips.append(bg_clip)

            scene_captions = generate_captions_for_scene(scene.narration, audio.duration, timeline)
            caption_clips.extend(scene_captions)
            
            timeline += audio.duration
        except Exception as e:
            log.critical(f"Compilation crashed at scene generation block: {e}"); sys.exit(1)

    log.info("Rendering final composite layers...")
    try:
        base_video = concatenate_videoclips(scene_clips, method="compose")
        final_video = CompositeVideoClip([base_video] + caption_clips)
        final_video.write_videofile(
            OUTPUT_VIDEO, 
            fps=VIDEO_FPS, 
            codec="libx264", 
            audio_codec="aac"
        )
    except Exception as e:
        log.critical(f"Render setup failed: {e}"); sys.exit(1)

    thumbnail_prompt = f"Highly dramatic, cinematic close-up relating to {story_data.angle_title}, studio lighting, highly detailed 8k"
    download_pollinations_image(thumbnail_prompt, OUTPUT_THUMB)

    upload_to_youtube(
        video_path=OUTPUT_VIDEO,
        thumb_path=OUTPUT_THUMB,
        title=f"{story_data.angle_title[:80]}! 😱 #shorts",
        description=f"An incredible true history story about {topic_key}.\n\n#shorts #history #facts",
    )

if __name__ == "__main__":
    selected_topic = random.choice(TOPICS)
    run_pipeline(selected_topic)
