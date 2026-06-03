import os
import json
import time
import requests
from dotenv import load_dotenv
import google.generativeai as genai

# Load env variables from root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

CATEGORIES = ["Career Advice", "University & Major", "Study & Exams", "Coding & Tech", "Feedback & Praise", "Other"]

def heuristic_classify(comment):
    text = comment.get("text", "").lower()
    
    # Career Keywords
    career_kw = ["job", "internship", "salary", "cv", "resume", "interview", "hire", "work", "career", "company", "industry"]
    # Uni Keywords
    uni_kw = ["uni", "university", "college", "major", "degree", "ee", "electrical", "cs", "computer science", "loughborough", "imperial", "course", "physics"]
    # Study Keywords
    study_kw = ["study", "exam", "grade", "note", "math", "revision", "lock in", "productivity", "lectures", "classes", "learn"]
    # Coding Keywords
    coding_kw = ["code", "python", "hack", "cyber", "tool", "ai", "github", "programming", "software", "hardware"]
    # Praise/Feedback Keywords
    praise_kw = ["love", "great", "nice", "good", "video", "channel", "edit", "awesome", "perfect", "underrated", "support", "subscribed"]
    
    is_question = "?" in text or any(text.startswith(w) for w in ["how", "what", "why", "where", "who", "can you", "should i", "is it", "are you"])
    
    # Simple rule based categorization
    if any(k in text for k in career_kw):
        category = "Career Advice"
    elif any(k in text for k in uni_kw):
        category = "University & Major"
    elif any(k in text for k in study_kw):
        category = "Study & Exams"
    elif any(k in text for k in coding_kw):
        category = "Coding & Tech"
    elif any(k in text for k in praise_kw):
        category = "Feedback & Praise"
    else:
        category = "Other"
        
    return {
        "comment_id": comment["comment_id"],
        "is_question": is_question,
        "category": category,
        "summarized_question": comment["text"][:80] + "..." if is_question else ""
    }

def classify_batch(model, comments_batch):
    prompt = """You are a research assistant analyzing comments from an engineering student YouTube channel.
Your goal is to categorize each comment, determine whether it contains a question, and if so, summarize it.

Categories:
1. "Career Advice" (jobs, internships, salary, CVs, interview prep)
2. "University & Major" (which degree is best, CS vs EE, university difficulty, selection of college)
3. "Study & Exams" (learning, lock-in, note-taking, math tips, productivity)
4. "Coding & Tech" (specific programming questions, hacking, tech stack, tools)
5. "Feedback & Praise" (loving the channel, general comments, nice edits, positive feedback)
6. "Other" (off-topic, general chatting, spam)

Comments to analyze:
"""
    for c in comments_batch:
        prompt += f"ID: {c['comment_id']}\nText: {c['text']}\n---\n"
        
    prompt += "\nOutput JSON list of classifications."
    
    schema = {
      "type": "OBJECT",
      "properties": {
        "classifications": {
          "type": "ARRAY",
          "items": {
            "type": "OBJECT",
            "properties": {
              "comment_id": {"type": "STRING"},
              "is_question": {"type": "BOOLEAN"},
              "category": {
                "type": "STRING",
                "enum": ["Career Advice", "University & Major", "Study & Exams", "Coding & Tech", "Feedback & Praise", "Other"]
              },
              "summarized_question": {"type": "STRING"}
            },
            "required": ["comment_id", "is_question", "category", "summarized_question"]
          }
        }
      },
      "required": ["classifications"]
    }
    
    max_retries = 6
    backoff_time = 4.0
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                prompt,
                generation_config=dict(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
            return data.get("classifications", [])
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error calling Gemini API (final attempt): {e}")
                return []
            
            if "429" in str(e) or "ResourceExhausted" in str(e):
                print(f"Gemini Rate limited (429) on attempt {attempt+1}/{max_retries}. Retrying in {backoff_time}s...")
            else:
                print(f"Error calling Gemini API: {e}. Retrying in {backoff_time}s...")
                
            time.sleep(backoff_time)
            backoff_time *= 2.0
            
    return []

def classify_batch_groq(api_key, comments_batch):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    prompt = """Analyze these comments from a YouTube channel. Categorize each comment and determine if it contains a question.
Available Categories:
- "Career Advice" (jobs, internships, salary, CVs, interview prep)
- "University & Major" (which degree is best, CS vs EE, university difficulty, selection of college)
- "Study & Exams" (learning, lock-in, note-taking, math tips, productivity)
- "Coding & Tech" (specific programming questions, hacking, tech stack, tools)
- "Feedback & Praise" (loving the channel, general comments, nice edits, positive feedback)
- "Other" (off-topic, general chatting, spam)

Format your output exactly as a JSON object with a single root key "classifications" containing a list of objects.
Each object must have:
- "comment_id" (string)
- "is_question" (boolean)
- "category" (string, must be one of the six categories above)
- "summarized_question" (string, 1-sentence summary if is_question is true, otherwise empty string)

Comments:
"""
    for c in comments_batch:
        prompt += f"ID: {c['comment_id']}\nText: {c['text']}\n---\n"
        
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "You are a research assistant. Always respond in JSON format conforming to the requested schema."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    
    max_retries = 6
    backoff_time = 5.0
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 429:
                print(f"Rate limited (429) on attempt {attempt+1}/{max_retries}. Retrying in {backoff_time}s...")
                time.sleep(backoff_time)
                backoff_time *= 2.0
                continue
                
            response.raise_for_status()
            res_data = response.json()
            content = res_data["choices"][0]["message"]["content"]
            data = json.loads(content)
            return data.get("classifications", [])
            
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error calling Groq API (final attempt): {e}")
                return []
            # For 429 inside raise_for_status (just in case) or other connection errors
            if "429" in str(e):
                print(f"Rate limited (429) inside exception on attempt {attempt+1}/{max_retries}. Retrying in {backoff_time}s...")
            else:
                print(f"Error calling Groq API: {e}. Retrying in {backoff_time}s...")
            time.sleep(backoff_time)
            backoff_time *= 2.0
            
    return []

def main():
    raw_file = os.path.join(os.path.dirname(__file__), "data/raw_comments.json")
    if not os.path.exists(raw_file):
        print(f"Error: {raw_file} does not exist. Please run scrape_youtube.py first.")
        return
        
    with open(raw_file, "r", encoding="utf-8") as f:
        comments = json.load(f)
        
    print(f"Loaded {len(comments)} raw comments.")
    
    use_llm = None  # Can be 'groq', 'gemini', or None
    model_obj = None
    
    if API_KEY:
        try:
            print("Configuring Gemini API Client...")
            genai.configure(api_key=API_KEY)
            model_obj = genai.GenerativeModel("gemini-2.5-flash")
            use_llm = 'gemini'
            print("Successfully initialized Gemini model: gemini-2.5-flash.")
        except Exception as e:
            print(f"Could not initialize Gemini API: {e}.")
    elif GROQ_API_KEY:
        use_llm = 'groq'
        print("Using Groq API with Llama-3.1-8b-instant for classification.")
            
    classified_results = []
    
    if use_llm:
        # Configure batch sizes and delays based on model rate limits
        if use_llm == 'gemini':
            batch_size = 50       # Gemini free tier supports 1M TPM, so 50 comments/batch is very safe
            sleep_time = 4.5      # Sleep to stay comfortably below Gemini free tier's 15 RPM
        else:
            batch_size = 20       # Groq free tier has 30k TPM limit, so 20 comments/batch is safer
            sleep_time = 6.0      # Sleep to avoid Groq rate limits
            
        total_comments = len(comments)
        print(f"Analyzing {total_comments} comments in batches of {batch_size} using {use_llm.upper()}...")
        
        for idx in range(0, total_comments, batch_size):
            batch = comments[idx : idx + batch_size]
            print(f"Processing batch {idx // batch_size + 1}/{((total_comments - 1) // batch_size) + 1} (comments {idx} to {min(idx + batch_size, total_comments)})...")
            
            if use_llm == 'groq':
                classifications = classify_batch_groq(GROQ_API_KEY, batch)
            else:
                classifications = classify_batch(model_obj, batch)
            
            # Map back to our dataset structure
            class_map = {c["comment_id"]: c for c in classifications}
            
            for comment in batch:
                c_id = comment["comment_id"]
                if c_id in class_map:
                    item = class_map[c_id]
                else:
                    # Fallback to heuristics for any failed items in this batch
                    item = heuristic_classify(comment)
                
                classified_results.append({
                    "comment_id": comment["comment_id"],
                    "video_id": comment["video_id"],
                    "video_title": comment["video_title"],
                    "author": comment["author"],
                    "text": comment["text"],
                    "like_count": comment["like_count"],
                    "published_at": comment["published_at"],
                    "reply_count": comment["reply_count"],
                    "is_question": item["is_question"],
                    "category": item["category"],
                    "summarized_question": item.get("summarized_question", "")
                })
            
            # Rate limit safety sleep
            time.sleep(sleep_time)
    else:
        print("No API keys found in .env. Classifying all comments via keyword heuristics...")
        for comment in comments:
            item = heuristic_classify(comment)
            classified_results.append({
                "comment_id": comment["comment_id"],
                "video_id": comment["video_id"],
                "video_title": comment["video_title"],
                "author": comment["author"],
                "text": comment["text"],
                "like_count": comment["like_count"],
                "published_at": comment["published_at"],
                "reply_count": comment["reply_count"],
                "is_question": item["is_question"],
                "category": item["category"],
                "summarized_question": item["summarized_question"]
            })
            
    output_file = os.path.join(os.path.dirname(__file__), "data/classified_comments.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(classified_results, f, indent=2, ensure_ascii=False)
        
    print(f"Success! Classified {len(classified_results)} comments and saved to {output_file}")

if __name__ == "__main__":
    main()
