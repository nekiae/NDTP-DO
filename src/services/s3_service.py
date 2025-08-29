"""S3 service for file upload operations."""

import uuid
import mimetypes
from typing import Optional, BinaryIO
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError

from src.core.config import config


class S3Service:
    """Service for S3 file upload operations."""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            endpoint_url=config.aws_host,
            config=Config(signature_version='s3'),
        )
        self.bucket_name = config.aws_s3_bucket_name
    
    def upload_file(
        self, 
        file_data: BinaryIO, 
        filename: str, 
        user_id: str,
        content_type: Optional[str] = None
    ) -> tuple[bool, str]:
        """Upload file to S3 and return success status and file URL or error message."""
        try:
            # Validate file type
            if content_type and content_type not in config.allowed_file_types:
                return False, f"File type {content_type} is not allowed"
            
            # Validate file size
            file_data.seek(0, 2)  # Go to end of file
            file_size = file_data.tell()
            file_data.seek(0)  # Reset to beginning
            
            if file_size > config.max_file_size:
                return False, f"File size {file_size} exceeds maximum allowed size {config.max_file_size}"
            
            # Generate unique filename
            file_extension = self._get_file_extension(filename)
            unique_filename = self._generate_unique_filename(user_id, file_extension)
            
            # Determine content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(filename)
                if not content_type:
                    content_type = 'application/octet-stream'
            
            # Upload to S3
            self.s3_client.upload_fileobj(
                file_data,
                self.bucket_name,
                unique_filename,
                ExtraArgs={
                    'ContentType': content_type,
                    'Metadata': {
                        'user_id': str(user_id),
                        'original_filename': filename,
                        'upload_timestamp': datetime.utcnow().isoformat()
                    }
                }
            )
            
            return True, ""
            
        except (ClientError, BotoCoreError) as e:
            return False, f"S3 error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        if '.' in filename:
            return filename.rsplit('.', 1)[1].lower()
        return ''
    
    def _generate_unique_filename(self, user_id: str, extension: str) -> str:
        """Generate unique filename for S3 storage."""
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        
        if extension:
            return f"uploads/{user_id}/{timestamp}_{unique_id}.{extension}"
        else:
            return f"uploads/{user_id}/{timestamp}_{unique_id}"
    
    def delete_file(self, file_key: str) -> tuple[bool, str]:
        """Delete file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True, "File deleted successfully"
        except (ClientError, BotoCoreError) as e:
            return False, f"AWS S3 error: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"

