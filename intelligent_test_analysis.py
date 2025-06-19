import pandas as pd
import json
import os
import logging
from tasks.tasks import generate_gemini_analysis_async
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('jmeter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Get the base directory of the script
BASE_DIR = os.path.abspath(os.path.dirname(__file__))




def analyze_jtl(file_path, output_folder):
    try:
        logger.info(f"📊 Starting analysis for {file_path}")

        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            logger.error(f"❌ Failed to read JTL file: {e}")
            return {"error": "Invalid JTL file format or unreadable."}

        required_columns = {"label", "elapsed", "responseCode", "allThreads"}
        if not required_columns.issubset(df.columns):
            return {"error": f"Missing required columns: {required_columns - set(df.columns)}"}

        summary = df.groupby("label").agg(
            avg_response_time=("elapsed", "mean"),
            error_rate=("responseCode", lambda x: (x.astype(str) != "200").mean() * 100),
            throughput=("label", "count"),
            concurrent_users=("allThreads", "max")
        ).reset_index()

        if summary.empty:
            return {"error": "No valid data found in JTL."}

        summary = summary.round(2)

        summary_markdown = "\n".join(
            f"- **{row['label']}**: Avg Time = `{row['avg_response_time']}ms`, "
            f"Errors = `{row['error_rate']}%`, "
            f"Throughput = `{row['throughput']}`, Users = `{row['concurrent_users']}`"
            for _, row in summary.iterrows()
        )

        prompt = (
            "You are a performance analysis expert. Analyze this result:\n\n"
            f"{summary_markdown}\n\n"
            "Provide a detailed markdown analysis. No code blocks. No additional explanations."
        )

        task = generate_gemini_analysis_async.delay(prompt)
        raw_result = task.get(timeout=60).strip()

        try:
            parsed = json.loads(raw_result)
            markdown_text = parsed.get("analysis", raw_result)
        except Exception:
            markdown_text = raw_result

        if markdown_text.startswith("```markdown"):
            markdown_text = markdown_text[len("```markdown"):].strip()
        if markdown_text.endswith("```"):
            markdown_text = markdown_text[:-3].strip()

        # Save markdown to temp output folder
        os.makedirs(output_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        filename = f"analysis_{timestamp}.md"
        output_path = os.path.join(output_folder, filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        logger.info(f"✅ Analysis saved: {output_path}")

        return {
            "analysis": markdown_text,
            "filename": filename
        }

    except Exception as e:
        logger.error(f"❌ Unexpected analysis error: {e}")
        return {"error": f"Unexpected error: {str(e)}"}