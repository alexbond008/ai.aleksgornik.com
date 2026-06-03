import os
import json
import time
import pandas as pd
from dotenv import load_dotenv
import google.generativeai as genai

# Load env variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

def get_gemini_client():
    if not API_KEY:
        raise ValueError("GEMINI_API_KEY not found in .env file. Please set it to proceed.")
    genai.configure(api_key=API_KEY)
    return genai.GenerativeModel("gemini-flash-latest")

def define_clusters_with_llm(model, questions_sample):
    print(f"Defining clusters dynamically based on a sample of {len(questions_sample)} questions...")
    questions_input = [{"comment_id": q["comment_id"], "text": q["text"]} for q in questions_sample]
    
    prompt = f"""You are a data scientist analyzing student comments.
Review this sample of {len(questions_input)} student questions and identify 6 to 8 distinct topic clusters (categories) they fall into.
For each cluster, provide a 1-based integer cluster_id, a concise title, and a brief description of what kinds of questions belong in it.

Questions sample:
{json.dumps(questions_input, indent=2)}
"""
    schema = {
      "type": "OBJECT",
      "properties": {
        "clusters": {
          "type": "ARRAY",
          "items": {
            "type": "OBJECT",
            "properties": {
              "cluster_id": {"type": "INTEGER"},
              "title": {"type": "STRING"},
              "description": {"type": "STRING"}
            },
            "required": ["cluster_id", "title", "description"]
          }
        }
      },
      "required": ["clusters"]
    }
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=dict(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2
            )
        )
        return json.loads(response.text)["clusters"]
    except Exception as e:
        print(f"Error defining clusters: {e}")
        return None

def annotate_questions_batch(model, clusters, questions_batch):
    questions_input = [{"comment_id": q["comment_id"], "text": q["text"]} for q in questions_batch]
    
    prompt = f"""You are a senior data scientist profiling student questions from Aleks Gornik's channel.
Assign each of the questions to one of the predefined clusters and extract key entities.

Predefined Clusters:
{json.dumps(clusters, indent=2)}

Questions to annotate:
{json.dumps(questions_input, indent=2)}
"""
    schema = {
      "type": "OBJECT",
      "properties": {
        "annotations": {
          "type": "ARRAY",
          "items": {
            "type": "OBJECT",
            "properties": {
              "comment_id": {"type": "STRING"},
              "cluster_id": {"type": "INTEGER"},
              "subject": {"type": "STRING"},
              "tool": {"type": "STRING"},
              "student_stage": {"type": "STRING", "enum": ["prospective", "active", "job-seeker"]},
              "urgency": {"type": "STRING", "enum": ["high", "medium", "low"]}
            },
            "required": ["comment_id", "cluster_id", "subject", "tool", "student_stage", "urgency"]
          }
        }
      },
      "required": ["annotations"]
    }
    
    max_retries = 5
    backoff_time = 4.0
    
    for attempt in range(max_retries):
        try:
            print(f"  Calling Gemini API (attempt {attempt + 1}/{max_retries})...", flush=True)
            start_time = time.time()
            response = model.generate_content(
                prompt,
                generation_config=dict(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1
                )
            )
            print(f"  Gemini API responded in {time.time() - start_time:.2f}s", flush=True)
            return json.loads(response.text)["annotations"]
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Error calling Gemini API for batch (final attempt): {e}")
                return []
            
            if "429" in str(e) or "ResourceExhausted" in str(e):
                print(f"Rate limited (429). Retrying in {backoff_time}s...")
            else:
                print(f"Error: {e}. Retrying in {backoff_time}s...")
            time.sleep(backoff_time)
            backoff_time *= 2.0
            
    return []

def main():
    classified_file = os.path.join(os.path.dirname(__file__), "data/classified_comments.json")
    if not os.path.exists(classified_file):
        print(f"Error: {classified_file} does not exist. Please run analyze_comments.py first.")
        return
        
    with open(classified_file, "r", encoding="utf-8") as f:
        comments = json.load(f)
        
    df = pd.DataFrame(comments)
    questions_df = df[df["is_question"] == True].copy()
    print(f"Loaded {len(df)} total comments. Found {len(questions_df)} questions.")
    
    # 1. Video Help-Density Analysis
    video_stats = []
    for video_title, group in df.groupby("video_title"):
        total_comments = len(group)
        q_comments = len(group[group["is_question"] == True])
        density = (q_comments / total_comments) if total_comments > 0 else 0
        video_stats.append({
            "video_title": video_title,
            "total_comments": total_comments,
            "question_comments": q_comments,
            "help_density_pct": round(density * 100, 2)
        })
    video_density_df = pd.DataFrame(video_stats).sort_values(by="help_density_pct", ascending=False)
    print("\n--- Top 5 Videos by Help-Density (Highest Question Ratio) ---")
    print(video_density_df.head(5).to_string(index=False))

    try:
        model = get_gemini_client()
    except Exception as e:
        print(f"Configuration error: {e}")
        return
        
    questions_list = questions_df.to_dict(orient="records")
    
    # 2. Step 1: Define clusters dynamically from sample
    sample_size = min(80, len(questions_list))
    sample_questions = questions_df.sample(n=sample_size, random_state=42).to_dict(orient="records")
    clusters = define_clusters_with_llm(model, sample_questions)
    
    if not clusters:
        print("Failed to define clusters. Exiting.")
        return
        
    print("\n--- Dynamically Defined Student Question Clusters ---")
    for c in clusters:
        print(f"Cluster {c['cluster_id']}: {c['title']} - {c['description']}")
        
    time.sleep(4.5)  # Stay below RPM limit

    # 3. Step 2: Annotate questions in batches
    batch_size = 20
    all_annotations = []
    total_questions = len(questions_list)
    print(f"\nAnnotating {total_questions} questions in batches of {batch_size}...")
    
    for idx in range(0, total_questions, batch_size):
        batch = questions_list[idx : idx + batch_size]
        batch_num = idx // batch_size + 1
        total_batches = ((total_questions - 1) // batch_size) + 1
        print(f"Processing batch {batch_num}/{total_batches}...")
        
        annotations = annotate_questions_batch(model, clusters, batch)
        all_annotations.extend(annotations)
        time.sleep(4.5)  # Stay below RPM limit
        
    # Map back to our dataset structure
    annotations_map = {a["comment_id"]: a for a in all_annotations}
    
    advanced_records = []
    for q in questions_list:
        c_id = q["comment_id"]
        ann = annotations_map.get(c_id, {
            "cluster_id": -1,
            "subject": "None",
            "tool": "None",
            "student_stage": "active",
            "urgency": "low"
        })
        
        q.update({
            "cluster_id": ann["cluster_id"],
            "subject": ann["subject"],
            "tool": ann["tool"],
            "student_stage": ann["student_stage"],
            "urgency": ann["urgency"]
        })
        advanced_records.append(q)
        
    output_data = {
        "clusters": clusters,
        "video_help_density": video_density_df.to_dict(orient="records"),
        "annotated_questions": advanced_records
    }
    
    output_file = os.path.join(os.path.dirname(__file__), "data/advanced_analysis.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"\nSuccess! Completed advanced profiling. Saved results to {output_file}")

if __name__ == "__main__":
    main()
