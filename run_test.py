import docker
import os
import logging
import time

logger = logging.getLogger(__name__)

JMETER_IMAGE = "my-jmeter:5.6.3"
MINIMAL_PROPERTIES = os.path.join(os.path.dirname(__file__), "minimal.properties")


def extract_jmeter_summary(log_text):
    lines = log_text.splitlines()
    summary_lines = [line for line in lines if line.strip().startswith("summary")]
    return "\n".join(summary_lines) or "No summary found."


def _run_jmeter_internal(file_path, result_file_path):
    try:
        start_time = time.time()
        client = docker.from_env()

        container = client.containers.run(
            image=JMETER_IMAGE,
            command=[
                "-n",
                "-t", f"/data/{os.path.basename(file_path)}",
                "-l", f"/data/{os.path.basename(result_file_path)}",
                "-q", "/data/minimal.properties"
            ],
            volumes={
                os.path.abspath(file_path): {
                    'bind': f"/data/{os.path.basename(file_path)}", 'mode': 'ro'
                },
                os.path.abspath(result_file_path): {
                    'bind': f"/data/{os.path.basename(result_file_path)}", 'mode': 'rw'
                },
                os.path.abspath(MINIMAL_PROPERTIES): {
                    'bind': "/data/minimal.properties", 'mode': 'ro'
                }
            },
            detach=True,
            remove=True,
            mem_limit='1g',
            cpu_shares=512
        )

        logger.info("🧪 JMeter container started.")
        exit_status = container.wait()
        logs = container.logs().decode("utf-8")
        end_time = time.time()

        if exit_status.get("StatusCode", 1) != 0:
            logger.error(f"❌ JMeter run failed. Logs:\n{logs}")
            raise RuntimeError("JMeter container exited with error.")

        logger.info(f"🕒 Execution Time: {end_time - start_time:.2f} seconds")

        if os.path.exists(result_file_path):
            logger.info("✅ .jtl file successfully created.")
        else:
            logger.error("❌ .jtl file NOT found after JMeter run!")

        summary = extract_jmeter_summary(logs)
        return summary

    except Exception as e:
        logger.exception(f"🚨 Error running JMeter test: {e}")
        raise


# Public interface, optionally Celery-backed
try:
    from tasks.tasks import run_jmeter_test_async
except ImportError:
    run_jmeter_test_async = None

def run_jmeter_test(file_path, result_file_path):
    if run_jmeter_test_async:
        run_jmeter_test_async.delay(file_path, result_file_path)
        return None  # or task ID if needed
    else:
        return _run_jmeter_internal(file_path, result_file_path)  # ✅ This line is crucial
