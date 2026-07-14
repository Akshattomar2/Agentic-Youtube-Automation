<div align="center">

# 🎬 YouTube Shorts Automation
### AI-Powered Multi-Agent Pipeline · CrewAI + Groq + Pollinations · 100% Free Stack

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-FF6B6B?style=for-the-badge)](https://crewai.com)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

*Fully automated pipeline that writes, visualises, voices, assembles, and uploads a YouTube Short — zero manual effort.*

</div>

---

## ✨ What This Does

Give it a topic. Walk away. Come back to a published YouTube Short.

| Stage | What Happens |
|---|---|
| 📝 Script | LLM agent writes a punchy 60-sec narration |
| 🎨 Scenes | Visual agent splits script into 4 scenes + image prompts |
| 🖼️ Visuals | Pollinations.ai generates scene images (free, no key) |
| 🔊 Voice | Edge-TTS converts narration to natural-sounding audio |
| 🎞️ Assembly | MoviePy stitches images + audio + animated subtitles |
| 📤 Upload | YouTube Data API publishes the Short with thumbnail + SEO |

---

## 🤖 Agent Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CrewAI Sequential Crew                   │
│                                                             │
│  ┌──────────────────────────┐                              │
│  │   🧠 Script Writer Agent  │  Role: YouTube Growth Manager│
│  │                          │  LLM:  Groq LLaMA 3.3 70B   │
│  │  INPUT:  Video topic     │                              │
│  │  OUTPUT: 60-sec script   │                              │
│  └────────────┬─────────────┘                              │
│               │  passes script                              │
│               ▼                                             │
│  ┌──────────────────────────┐                              │
│  │   🎨 Video Planner Agent  │  Role: Visual Director       │
│  │                          │  LLM:  Groq LLaMA 3.3 70B   │
│  │  INPUT:  Script text     │                              │
│  │  OUTPUT: JSON →          │                              │
│  │   • 4 scenes             │                              │
│  │   • image_prompt each    │                              │
│  │   • narration_text each  │                              │
│  │   • thumbnail_prompt     │                              │
│  │   • youtube_title        │                              │
│  │   • youtube_description  │                              │
│  └────────────┬─────────────┘                              │
└───────────────┼─────────────────────────────────────────────┘
                │  structured JSON output
                ▼
┌──────────────────────────────────────────────────────────────┐
│                    Production Pipeline                        │
│                                                              │
│  For each scene:                                             │
│  ┌─────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │ Pollinations│   │   Edge-TTS   │   │     MoviePy      │  │
│  │  image gen  │ + │  voiceover   │ → │  Ken Burns clip  │  │
│  └─────────────┘   └──────────────┘   └────────┬────────┘  │
│                                                  │           │
│  ┌───────────────────────────────────────────────▼────────┐ │
│  │         concatenate_videoclips + subtitle overlay       │ │
│  │                  → final_shorts_video.mp4               │ │
│  └───────────────────────────────────────────────┬────────┘ │
│                                                   │          │
│  ┌────────────────────────────────────────────────▼────────┐ │
│  │              YouTube Data API v3 Upload                  │ │
│  │         video + thumbnail + title + description          │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

**🧠 Script Writer Agent**
- Role: `Expert YouTube Growth Manager`
- Writes hook-driven, fast-paced 60-second narration scripts
- Optimises for viewer retention and algorithm visibility
- Output: clean paragraph narration (no brackets or stage directions)

**🎨 Video Planner Agent**
- Role: `Visual Director`
- Receives the script and splits it into exactly 4 timed scenes
- Generates a cinematic image prompt per scene
- Outputs full YouTube SEO metadata (title, description, tags)
- Designs a high-CTR thumbnail concept prompt
- Output: strict raw JSON (no markdown fencing)

---

## 🛠️ Tech Stack

| Tool | Purpose | Cost |
|---|---|---|
| [CrewAI](https://crewai.com) | Multi-agent orchestration | Free |
| [Groq](https://groq.com) | LLaMA 3.3 70B inference | Free tier |
| [Pollinations.ai](https://pollinations.ai) | AI image generation | Free, no key |
| [Edge-TTS](https://github.com/rany2/edge-tts) | Neural voice synthesis | Free |
| [MoviePy](https://zulko.github.io/moviepy/) | Video assembly & effects | Free |
| [YouTube Data API v3](https://developers.google.com/youtube/v3) | Video upload & thumbnail | Free (quota-based) |
| [GitHub Actions](https://github.com/features/actions) | Scheduled automation | Free (public repos) |

**Total running cost: $0**

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/yt-automation.git
cd yt-automation
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API keys

Copy the example env file:
```bash
cp .env.example .env
```

Fill in `.env`:
```
GROQ_API_KEY=your_groq_key_here
```

Get your Groq key free at → https://console.groq.com

### 4. Set up YouTube OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project → Enable **YouTube Data API v3**
3. Create **OAuth 2.0 credentials** (Desktop app type)
4. Download as `client_secrets.json` → place in project root
5. First run will open a browser for one-time login

> ⚠️ `client_secrets.json` is in `.gitignore` — it will never be pushed to GitHub.

### 5. Change the topic and run
```python
# In main.py, line ~45:
VIDEO_TOPIC = "Your video topic here"
```

```bash
python main.py
```

---

## 📁 Project Structure

```
yt-automation/
├── main.py               # Full pipeline
├── requirements.txt      # Python dependencies
├── .env.example          # API key template (safe to commit)
├── .env                  # Your actual keys (gitignored)
├── .gitignore            # Protects secrets + generated files
├── client_secrets.json   # Google OAuth (gitignored, add manually)
└── README.md
```

---

## 🔒 Security

- `.env` and `client_secrets.json` are listed in `.gitignore` and will **never** be committed
- API key is loaded via `python-dotenv` — never hardcoded
- Generated video/image files are also gitignored (keeps repo clean)

---

## ☁️ Automate with GitHub Actions

Create `.github/workflows/daily.yml` to run the pipeline on a schedule:

```yaml
name: Daily YouTube Short

on:
  schedule:
    - cron: '0 2 * * *'   # runs every day at 2 AM UTC
  workflow_dispatch:        # also allows manual trigger

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run pipeline
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
        run: python main.py
```

Add your `GROQ_API_KEY` under **Settings → Secrets → Actions** in your GitHub repo.

> Note: YouTube OAuth requires a one-time browser login. For fully headless GitHub Actions upload, replace OAuth flow with a saved refresh token — open an issue if you need help with this.

---

## 🧑‍💻 Built By

**Akshat** — B.Tech AI & ML, GGITS (RGPV) Jabalpur
Exploring AI engineering, agentic workflows, and automation systems.

[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YOUR_USERNAME)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/YOUR_PROFILE)

---

<div align="center">
<sub>⭐ Star this repo if it helped you!</sub>
</div>
