import io
from datetime import datetime
import xml.etree.ElementTree as ET
from s3_utils import upload_fileobj_to_s3  # assumes you've written this
import traceback
from tasks.tasks import generate_gemini_analysis_async

def is_valid_jmx(xml_content: str) -> bool:
    try:
        root = ET.fromstring(xml_content)
        if root.tag != "jmeterTestPlan":
            return False

        required_elements = ["TestPlan", "ThreadGroup", "HTTPSamplerProxy"]
        xml_str = ET.tostring(root, encoding='unicode')

        return all(tag in xml_str for tag in required_elements)
    except Exception:
        return False

def extract_xml_from_markdown(jmx_response: str) -> str:
    start = jmx_response.find("```xml")
    end = jmx_response.find("```", start + 6)
    if start != -1 and end != -1:
        return jmx_response[start + 6:end].strip()
    return jmx_response.strip()

def generate_jmeter_test_plan(prompt, user_email, attempts=0, max_attempts=10):
    try:
        if attempts >= max_attempts:
            return {"status": "error", "message": f"Max retry limit of {max_attempts} reached."}, 500

        full_prompt = (
            f"{prompt.strip()}\n\n"
            "Now generate a valid Apache JMeter .jmx test plan XML file based on the above description.\n"
            "- It must be valid for Apache JMeter 5.6.3.\n"
            "- Return XML in markdown code block using ```xml ... ```.\n"
            "- Do not return explanations or comments outside the XML block."
        )

        task = generate_gemini_analysis_async.delay(full_prompt)
        raw_response = task.get(timeout=60)
        xml_only = extract_xml_from_markdown(raw_response)

        if not is_valid_jmx(xml_only):
            return generate_jmeter_test_plan(prompt, user_email, attempts + 1, max_attempts)

        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        jmx_filename = f"test_plan_{timestamp}.jmx"
        s3_key = f"uploads/{user_email}/{jmx_filename}"

        file_obj = io.BytesIO(xml_only.encode('utf-8'))
        upload_fileobj_to_s3(file_obj, s3_key)

        return {
            "status": "success",
            "message": "Test plan generated and uploaded to S3.",
            "jmx_filename": jmx_filename
        }, 200

    except Exception as e:
        print("❌ Error generating test plan:", traceback.format_exc())
        return {"status": "error", "message": str(e)}, 500
