import os
import sys
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from intelligent_test_analysis import analyze_jtl
from run_test import run_jmeter_test
from generate_test_plan import generate_jmeter_test_plan
from datetime import datetime
from flask_jwt_extended import jwt_required, get_jwt_identity
from users.auth import auth_bp
from email_utils import send_email
from users import init_jwt
from s3_utils import s3, BUCKET_NAME, download_file_from_s3, upload_file_to_s3, generate_presigned_url
import tempfile
from users import limiter
from payments.routes import payments_bp
from email_utils import styled_email_template
from dotenv import load_dotenv

load_dotenv()

def get_user_prefix():
    return f"uploads/{get_jwt_identity()}/"


# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ---------- Flask App ----------
app = Flask(__name__)
init_jwt(app)
limiter.init_app(app)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(payments_bp, url_prefix="/payments")
# Enable CORS (adjust domains before production)
CORS(app,
     supports_credentials=True,
     origins=[os.getenv("CORS_ORIGIN")])

@app.before_request
def handle_options():
    if request.method == 'OPTIONS':
        return '', 200

# ---------- Routes ----------

@app.route("/list-files", methods=["GET"])
@jwt_required()
def list_files():
    try:
        file_type = request.args.get("type", "").lower()
        if file_type not in ["jmx", "jtl", "md"]:
            return jsonify({"error": "Invalid file type requested. Must be 'jmx', 'jtl', or 'md'."}), 400

        # List only objects under 'uploads/' folder
        user_prefix = get_user_prefix()
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=user_prefix)

        if "Contents" not in response:
            return jsonify([])  # No files found

        # Extract files with the requested extension
        matching_files = [
            obj["Key"].replace(user_prefix, "")  # strip the user-specific prefix for response
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(f".{file_type}")
        ]

        return jsonify(matching_files)

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/run-test/<test_filename>', methods=['POST'])
@jwt_required()
def run_test(test_filename):
    try:
        if not test_filename.endswith(".jmx"):
            return jsonify({'status': 'error', 'message': 'Invalid test file format. Must be .jmx'}), 400

        # Download the .jmx test file from S3 to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jmx") as temp_jmx:
            local_jmx_path = temp_jmx.name

        user_prefix = get_user_prefix()
        download_file_from_s3(f"{user_prefix}{test_filename}", local_jmx_path)
        logger.info(f"📥 Downloaded {test_filename} from S3")

        # Create temp file path for .jtl result
        timestamp = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        result_filename = f"test_plan_{timestamp}.jtl"
        local_result_path = os.path.join(tempfile.gettempdir(), result_filename)

        # Run JMeter with the downloaded .jmx and capture summary
        summary_output = _run_jmeter_internal(local_jmx_path, local_result_path)
        logger.info(f"✅ JMeter run complete. Result: {local_result_path}")

        # Upload the result file to S3
        upload_file_to_s3(local_result_path, f"{user_prefix}{result_filename}")
        logger.info(f"☁️ Uploaded result to S3: uploads/{result_filename}")

        # Clean up temp files
        os.remove(local_jmx_path)
        os.remove(local_result_path)

        return jsonify({
            "status": "success",
            "message": "JMeter test executed.",
            "result_file": result_filename,
            "summary_output": summary_output  # 👈 Previewable on frontend
        })

    except Exception as e:
        logger.error(f"Run test error: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Failed to run test: {str(e)}'}), 500


@app.route("/analyzeJTL", methods=["POST"])
@limiter.limit("5/minute")
@jwt_required()
def analyze_jtl_api():
    try:
        data = request.get_json()
        jtl_filename = data.get("filename")

        if not jtl_filename or not jtl_filename.endswith(".jtl"):
            return jsonify({"error": "Invalid or missing .jtl filename"}), 400

        # Step 1: Download .jtl file from S3 to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jtl") as temp_jtl_file:
            local_jtl_path = temp_jtl_file.name
        user_prefix = get_user_prefix()
        download_file_from_s3(f"{user_prefix}{jtl_filename}", local_jtl_path)

        # Step 2: Run analysis and generate .md file in temp dir
        with tempfile.TemporaryDirectory() as temp_analysis_dir:
            result = analyze_jtl(local_jtl_path, temp_analysis_dir)

            # Step 3: Upload analysis file to S3
            md_filename = result.get("filename")
            if md_filename:
                md_path = os.path.join(temp_analysis_dir, md_filename)
                upload_file_to_s3(md_path, f"{user_prefix}{md_filename}")

        # Step 4: Clean up
        os.remove(local_jtl_path)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": f"JTL analysis error: {str(e)}"}), 500

@app.route("/sendEmail", methods=["POST"])
@jwt_required()
def send_email_api():
    try:
        data = request.get_json()
        md_filename = data.get("filename")

        if not md_filename or not md_filename.endswith(".md"):
            return jsonify({"error": "A valid .md filename is required."}), 400

        current_user_email = get_jwt_identity()
        if not current_user_email:
            return jsonify({"error": "Unable to determine recipient email."}), 400

        # Download the .md file from S3
        with tempfile.NamedTemporaryFile(delete=False, suffix=".md") as temp_file:
            local_md_path = temp_file.name
        user_prefix = get_user_prefix()
        download_file_from_s3(f"{user_prefix}{md_filename}", local_md_path)

        # Styled HTML body
        body = styled_email_template(
        title="JTL Analysis Summary",
        message="""
            Hello,<br><br>
            Please find attached the summary of your recent JTL performance analysis.<br><br>
            If you have any questions or need support, feel free to contact our team.
        """
    )

        response = send_email(
            to=current_user_email,
            subject="JTL Analysis Summary",
            body=body,
            attachments=[local_md_path],
            is_html=True
        )

        os.remove(local_md_path)
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Email error: {str(e)}"}), 500



@app.route("/generate-test-plan", methods=["POST"])
@limiter.limit("5/minute")
@jwt_required()
def generate_test_plan_api():
    try:
        data = request.json
        prompt = data.get("prompt")

        if not prompt:
            return jsonify({"status": "error", "message": "Prompt is missing."}), 400

        result, code = generate_jmeter_test_plan(prompt)
        return jsonify(result), code

    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to generate test plan: {str(e)}"}), 500


@app.route('/download/<filename>', methods=['GET'])
@jwt_required()
def universal_download(filename):
    try:
        user_prefix = get_user_prefix()
        s3_key = f"{user_prefix}{filename}"
        url = generate_presigned_url(s3_key)
        
        if url:
            return jsonify({"status": "success", "download_url": url})
        else:
            return jsonify({"status": "error", "message": "Failed to generate download URL"}), 500

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Download error: {str(e)}'}), 500

# ---------- Run ----------
if __name__ == "__main__":
    app.run()
