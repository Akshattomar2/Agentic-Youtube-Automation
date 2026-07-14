import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

import os
import json
import ast
import logging
import asyncio
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from crewai import Agent, Task, Crew, Process
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeVideoClip
import edge_tts

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

os.environ["OPENAI_API_BASE"] = "https://api.groq.com/openai/v1"
os.environ["OPENAI_MODEL_NAME"] = "llama-3.3-70b-versatile"
os.environ["OPENAI_API_KEY"] = "your_api_key"

SPICE_DATASET = {
    "saffron": {
        "angle": "The dark economics, extreme manual labor, and historical thefts of the spice.",
        "banned_words": ["mysterious", "exotic bazaars", "worth its weight in gold", "coveted"]
    },
    "black_pepper": {
        "angle": "How black pepper launched the Age of Discovery, funded European empires, and was used as rent currency.",
        "banned_words": ["common condiment", "table shaker", "ordinary spice", "black gold"]
    },
    "vanilla": {
        "angle": "The genius botanical heist where a 12-year-old enslaved boy named Edmond Albius discovered hand-pollination.",
        "banned_words": ["plain vanilla", "sweet flavor", "popular ice cream", "baking ingredient"]
    },
    "nutmeg": {
        "angle": "The bloody Dutch war over the Banda Islands, leading to the exchange of Manhattan for a nutmeg island.",
        "banned_words": ["holiday baking", "warm spice", "fall flavors", "eggnog"]
    }
}

def create_subtitle_clip(text, duration, start_time, video_size=(1080, 1920), font_size=55):
    try:
        img = Image.new("RGBA", video_size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
            
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (video_size[0] - text_width) // 2
        y = int(video_size[1] * 0.75) 
        
        draw.text((x, y), text, font=font, fill=(255, 255, 0, 255), stroke_width=5, stroke_fill=(0, 0, 0, 255))
        return ImageClip(np.array(img)).set_start(start_time).set_duration(duration).set_pos(('center', 'top'))
    except Exception as e:
        logger.error(f"Failed to render subtitle clip: {e}")
        raise

async def generate_voiceover(text, output_audio_path):
    try:
        communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
        await communicate.save(output_audio_path)
    except Exception as e:
        logger.error(f"TTS Engine Failure: {e}")
        raise

def download_image(prompt, output_image_path, width=1080, height=1920):
    try:
        encoded_prompt = requests.utils.quote(prompt)
        url = f"https://image.pollinations.ai/p/{encoded_prompt}?width={width}&height={height}&seed=42"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(output_image_path, 'wb') as f:
                f.write(response.content)
        else:
            raise requests.exceptions.HTTPError(f"Status code: {response.status_code}")
    except Exception as e:
        logger.error(f"Image Download Exception for prompt '{prompt[:30]}...': {e}")
        raise

def upload_to_youtube(video_path, thumbnail_path, title, description):
    try:
        logger.info("🔐 Accessing Google YouTube Data API v3 Matrix...")
        SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        
        if not os.path.exists('client_secrets.json'):
            raise FileNotFoundError("Missing critical 'client_secrets.json' credentials in root.")
            
        flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
        credentials = flow.run_local_server(port=0, authorization_prompt_message="")
        youtube = build('youtube', 'v3', credentials=credentials)
        
        logger.info(f"📤 Uploading video binary payload: {video_path}")
        body = {
            'snippet': {
                'title': title[:100],  
                'description': description,
                'tags': ['shorts', 'history', 'spices', 'automation'],
                'categoryId': '22'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }
        
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype='video/mp4')
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        response = request.execute()
        video_id = response['id']
        logger.info(f"✅ Core Video uploaded successfully! ID: {video_id}")
        
        logger.info("🖼️ Injecting high-CTR Cover Art Frame...")
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
        ).execute()
        logger.info("🎉 Complete Content Stack deployed live onto channel!")
        
    except Exception as e:
        logger.error(f"YouTube Pipeline Interrupted: {e}")
        print(f"\n💡 [FALLBACK] Video saved locally as '{video_path}'. Manual upload required.")

def run_spice_pipeline(spice_name):
    spice_info = SPICE_DATASET.get(spice_name.lower())
    if not spice_info:
        logger.error(f"Spice '{spice_name}' not configured in matrix dataset.")
        return

    logger.info(f"🚀 Launching Pipeline Engine for Topic: {spice_name.upper()}")
    
    script_writer = Agent(
        role='Expert YouTube Growth Manager',
        goal='Create high-retention 60-second shorts narration scripts.',
        backstory='You write aggressive, fast-paced historical hooks that retain users on mobile loops.',
        verbose=False
    )

    video_planner = Agent(
        role='Visual Director',
        goal='Structure narration arrays and high-CTR thumbnail prompts into clean structural properties.',
        backstory='You translate audio narratives into stunning visual compositions.',
        verbose=False
    )

    task_write_script = Task(
        description=f"Write a 40-second fast narration script about {spice_name}. Angle: {spice_info['angle']}. DO NOT use these words: {spice_info['banned_words']}.",
        expected_output="Pure speech narration text blocks without annotations.",
        agent=script_writer
    )

    task_plan_scenes = Task(
        description="Map script into exactly 4 sequential segments. Generate fields: 'scenes' (array containing 'image_prompt' and 'narration_text'), 'thumbnail_prompt', 'youtube_title', and 'youtube_description'. Return absolute raw JSON string payload only.",
        expected_output="JSON data matching the defined fields schema.",
        agent=video_planner,
        dependencies=[task_write_script]
    )

    crew = Crew(agents=[script_writer, video_planner], tasks=[task_write_script], process=Process.sequential)
    result = crew.kickoff()

    raw_output = str(result)
    if "```json" in raw_output:
        raw_output = raw_output.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_output:
        raw_output = raw_output.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(raw_output)
        except Exception:
            logger.warning("Unstructured raw text parsing triggered standard failover dictionary.")
            data = {
                'scenes': [{'image_prompt': f'Cinematic shot of historic {spice_name}', 'narration_text': raw_output[:150]}],
                'thumbnail_prompt': f'Epic studio shot of raw {spice_name}',
                'youtube_title': f"The Mindblowing Truth About {spice_name.capitalize()}!",
                'youtube_description': f"Uncovering the crazy hidden history of {spice_name}. #shorts"
            }

    scenes_list = data.get('scenes', data) if isinstance(data, dict) else data
    if not isinstance(scenes_list, list):
        scenes_list = [{'image_prompt': f'Cinematic asset for {spice_name}', 'narration_text': str(scenes_list)}]

    video_clips = []
    subtitle_clips = []
    current_time_marker = 0.0

    for index, scene in enumerate(scenes_list):
        logger.info(f"Processing Clip Sequence {index + 1}/{len(scenes_list)}...")
        img_path = f"scene_{index}.jpg"
        audio_path = f"scene_{index}.mp3"
        
        try:
            download_image(scene.get('image_prompt', spice_name), img_path)
            asyncio.run(generate_voiceover(scene.get('narration_text', ''), audio_path))
            
            audio_clip = AudioFileClip(audio_path)
            img_clip = ImageClip(img_path).set_duration(audio_clip.duration)
            
            animated_clip = img_clip.resize(lambda t: 1.0 + 0.15 * (t / audio_clip.duration))
            animated_clip = animated_clip.set_position(('center', 'center')).set_audio(audio_clip)
            video_clips.append(animated_clip)
            
            sub_clip = create_subtitle_clip(scene.get('narration_text', ''), audio_clip.duration, current_time_marker)
            subtitle_clips.append(sub_clip)
            current_time_marker += audio_clip.duration
        except Exception as step_error:
            logger.error(f"Skipping corrupt frame matrix index {index}: {step_error}")
            continue

    if not video_clips:
        logger.fatal("No active visual streams available to process.")
        return

    logger.info("🎞️ Stitching media compositions...")
    base_video = concatenate_videoclips(video_clips, method="compose")
    output_filename = f"final_{spice_name}_short.mp4"
    CompositeVideoClip([base_video] + subtitle_clips).write_videofile(output_filename, fps=24, codec="libx264", audio_codec="aac")
    
    thumb_filename = f"thumb_{spice_name}.jpg"
    download_image(data.get('thumbnail_prompt', spice_name), thumb_filename, width=1280, height=720)
    
    upload_to_youtube(
        video_path=output_filename,
        thumbnail_path=thumb_filename,
        title=data.get('youtube_title', f"Secrets of {spice_name.capitalize()}"),
        description=data.get('youtube_description', '#shorts')
    )

if __name__ == "__main__":
    target_topic = "black_pepper" 
    run_spice_pipeline(target_topic)
