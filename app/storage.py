"""Requirement 31: save E's processed JPEG in S3 and get a temporary viewing URL."""

import re
from uuid import uuid4

import boto3
from botocore.config import Config
from flask import current_app


def _storage():
    bucket = current_app.config["S3_BUCKET"]
    if not bucket:
        raise RuntimeError("Set S3_BUCKET before uploading photos.")
    # AWS credentials come from environment variables or an IAM role, never code.
    client = boto3.client("s3", region_name=current_app.config["AWS_DEFAULT_REGION"],
                          config=Config(signature_version="s3v4"))
    return bucket, client


def _check_key(key):
    if not isinstance(key, str) or not re.fullmatch(r"items/[a-f0-9]{32}\.jpg", key):
        raise ValueError("Expected a photo key returned by save_photo().")


def save_photo(clean_jpeg):
    # E must validate/decode the original and strip metadata first. This is not
    # an upload route or a replacement for E's process_photo() function.
    if not isinstance(clean_jpeg, bytes) or not 0 < len(clean_jpeg) <= 10 * 1024 * 1024:
        raise ValueError("Expected processed JPEG bytes, at most 10 MiB.")
    if not clean_jpeg.startswith(b"\xff\xd8") or not clean_jpeg.endswith(b"\xff\xd9"):
        raise ValueError("Expected a JPEG from the photo pipeline.")
    bucket, client = _storage()
    key = f"items/{uuid4().hex}.jpg"
    client.put_object(Bucket=bucket, Key=key, Body=clean_jpeg,
                      ContentType="image/jpeg", ServerSideEncryption="AES256")
    return key


def photo_url(key):
    _check_key(key)
    bucket, client = _storage()
    return client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=900,
    )


def delete_photo(key):
    """Clean up an uploaded photo if saving its database record fails."""
    _check_key(key)
    bucket, client = _storage()
    client.delete_object(Bucket=bucket, Key=key)
