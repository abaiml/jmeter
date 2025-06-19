import boto3
import os
from botocore.exceptions import ClientError

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

BUCKET_NAME = os.getenv("S3_BUCKET")


def upload_file_to_s3(file_path, s3_key):
    try:
        s3.upload_file(file_path, BUCKET_NAME, s3_key)
        return True
    except ClientError as e:
        print(f"Upload error: {e}")
        return False


def upload_fileobj_to_s3(file_obj, s3_key):
    try:
        s3.upload_fileobj(file_obj, BUCKET_NAME, s3_key)
        return True
    except ClientError as e:
        print(f"Upload error: {e}")
        return False


def download_file_from_s3(s3_key, local_path):
    try:
        s3.download_file(BUCKET_NAME, s3_key, local_path)
        return True
    except ClientError as e:
        print(f"Download error: {e}")
        return False


def generate_presigned_url(s3_key, expiration=3600):
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print(f"❌ Error generating presigned URL: {e}")
        return None
