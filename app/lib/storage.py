"""Local or S3 file storage abstraction."""

import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings


class StorageService:
    def __init__(self) -> None:
        self.settings = get_settings()
        if self.settings.storage_backend == "local":
            Path(self.settings.local_storage_path).mkdir(parents=True, exist_ok=True)

    def upload(self, key: str, data: bytes, content_type: str = "application/pdf") -> str:
        if self.settings.storage_backend == "local":
            path = Path(self.settings.local_storage_path) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return key
        client = boto3.client(
            "s3",
            region_name=self.settings.s3_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
        )
        client.put_object(Bucket=self.settings.s3_bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def get_object(self, key: str) -> bytes:
        if self.settings.storage_backend == "local":
            path = Path(self.settings.local_storage_path) / key
            return path.read_bytes()
        client = boto3.client(
            "s3",
            region_name=self.settings.s3_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
        )
        response = client.get_object(Bucket=self.settings.s3_bucket, Key=key)
        return response["Body"].read()

    def get_signed_download_url(self, key: str, expires_in_seconds: int = 900) -> str:
        if self.settings.storage_backend == "local":
            return f"{self.settings.app_url}/api/v1/storage/{key}"
        client = boto3.client(
            "s3",
            region_name=self.settings.s3_region,
            aws_access_key_id=self.settings.aws_access_key_id,
            aws_secret_access_key=self.settings.aws_secret_access_key,
        )
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": key},
            ExpiresIn=expires_in_seconds,
        )


storage_service = StorageService()
