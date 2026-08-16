# Resume ATS Tracker

A Streamlit app that scores a resume against a job description using the Google Gemini API,
reporting an ATS-style match score, matched/missing keywords, strengths, weaknesses, and
concrete suggestions to improve the resume.

## Setup

```bash
pip install -r requirements.txt
```

Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey), then edit
the `.env` file in the project root:

```bash
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=gemini-3.6-flash
```

(`.env.example` is provided as a template.) `.env` is gitignored, so your key won't be committed.

## Run

```bash
streamlit run app.py
```

Then in the app: upload or paste a resume, paste a job description, and click **Analyze Resume**.

## Features

- ATS match score (0-100), verdict, and matched/missing keyword breakdown
- Strengths, weaknesses, actionable suggestions, and ATS formatting-risk detection
- **Cover letter generator** — one click to draft a tailored cover letter from the resume + JD
- **Bullet rewriter** — Gemini rewrites the weakest resume bullets to better match the JD, with a reason for each change
- **Export** — download the full report as Markdown or as a formatted PDF (includes the cover letter and bullet rewrites if generated)

## A note on the model name

The app defaults to `gemini-3.6-flash`, as requested, but that exact model id may not be
available on every account — Google's public Flash lineup at the time of writing is
`gemini-2.5-flash` / `gemini-2.0-flash` / `gemini-1.5-flash`. If the app reports a "model not
found" error, set `GEMINI_MODEL` in `.env` to one of those and restart the app.

## Files

- `app.py` — Streamlit UI + Gemini call + result rendering
- `resume_parser.py` — PDF/DOCX/TXT text extraction for uploaded resumes
- `requirements.txt` — Python dependencies
