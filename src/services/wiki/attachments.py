"""
Wiki Attachment Storage
Handles file uploads to S3-compatible storage (MinIO/AWS)
"""

from typing import Optional
from src.config import settings

import boto3
from botocore.exceptions import ClientError

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class WikiAttachmentStorage:
    """
    Service for managing wiki attachments.
    """

    def __init__(self):
        self.bucket_name = settings.wiki_attachments_bucket
        self.s3_client = self._init_client()

    def _init_client(self):
        endpoint = settings.s3_endpoint
        access_key = settings.s3_access_key
        secret_key = settings.s3_secret_key

        if not endpoint or not access_key:
            logger.warning("S3 configuration missing. Attachments will fail.")
            return None

        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def upload_file(self, file_content: bytes, filename: str, content_type: str) -> Optional[str]:
        """
        Upload file to S3 and return public URL.
        """
        if not self.s3_client:
            raise RuntimeError("S3 client not configured")

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_content,
                ContentType=content_type,
            )

            # Construct URL (assuming public read or presigned)
            # For MVP we assume endpoint + bucket + key
            endpoint = settings.s3_endpoint_public or settings.s3_endpoint
            return f"{endpoint}/{self.bucket_name}/{filename}"

        except ClientError as e:
            logger.error(f"Failed to upload attachment {filename}: {e}", exc_info=True)
            return None
