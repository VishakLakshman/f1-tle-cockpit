import os
import json
import boto3

S3_BUCKET = os.getenv("FF1_S3_BUCKET", "")
_s3 = boto3.client("s3")


def upload_json(key: str, data: dict) -> None:
    if not S3_BUCKET:
        raise RuntimeError("FF1_S3_BUCKET env var not set")
    _s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=json.dumps(data, separators=(",", ":")),  # compact JSON
        ContentType="application/json",
    )