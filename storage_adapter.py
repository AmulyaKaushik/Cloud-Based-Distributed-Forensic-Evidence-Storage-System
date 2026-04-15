"""
Storage adapter layer for pluggable backend support.

Provides an abstract interface for evidence storage operations,
with implementations for local multi-node replication and cloud backends.
"""

import os
from abc import ABC, abstractmethod


class StorageAdapter(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def put(self, local_path, remote_key):
        """
        Store a file to the backend.
        
        Args:
            local_path (str): Path to the local file to store.
            remote_key (str): Unique key/identifier for the file in storage.
        
        Raises:
            Exception: If storage fails.
        """
        pass

    @abstractmethod
    def get(self, remote_key, local_path=None):
        """
        Retrieve a file from the backend.
        
        Args:
            remote_key (str): Unique key/identifier for the file.
            local_path (str): Optional path to save the file locally. If None, returns bytes.
        
        Returns:
            bytes or None: File contents if local_path is None, else None on success.
        
        Raises:
            Exception: If retrieval fails.
        """
        pass

    @abstractmethod
    def exists(self, remote_key):
        """
        Check if a file exists in storage.
        
        Args:
            remote_key (str): Unique key/identifier for the file.
        
        Returns:
            bool: True if file exists, False otherwise.
        """
        pass

    @abstractmethod
    def delete(self, remote_key):
        """
        Delete a file from the backend.
        
        Args:
            remote_key (str): Unique key/identifier for the file.
        
        Raises:
            Exception: If deletion fails.
        """
        pass

    @abstractmethod
    def health_check(self):
        """
        Verify backend connectivity and readiness.
        
        Returns:
            dict: Status report with keys 'healthy' (bool), 'message' (str).
        """
        pass


class LocalStorageAdapter(StorageAdapter):
    """
    Local multi-node replication adapter.
    
    Replicates files across multiple local directories to simulate
    distributed storage and provide fault tolerance.
    """

    def __init__(self, node_dirs):
        """
        Initialize the local storage adapter.
        
        Args:
            node_dirs (list): List of directory paths for each replica node.
        """
        self.node_dirs = node_dirs
        for node_dir in self.node_dirs:
            os.makedirs(node_dir, exist_ok=True)

    def put(self, local_path, remote_key):
        """Replicate file to all node directories."""
        import shutil

        for node_dir in self.node_dirs:
            dest_path = os.path.join(node_dir, remote_key)
            shutil.copy(local_path, dest_path)

    def get(self, remote_key, local_path=None):
        """Retrieve file from the first available node."""
        for node_dir in self.node_dirs:
            source_path = os.path.join(node_dir, remote_key)
            if os.path.exists(source_path):
                if local_path is None:
                    with open(source_path, "rb") as f:
                        return f.read()
                else:
                    import shutil
                    shutil.copy(source_path, local_path)
                    return None
        raise FileNotFoundError(f"File {remote_key} not found in any node.")

    def exists(self, remote_key):
        """Check if file exists in any node."""
        for node_dir in self.node_dirs:
            source_path = os.path.join(node_dir, remote_key)
            if os.path.exists(source_path):
                return True
        return False

    def delete(self, remote_key):
        """Delete file from all nodes."""
        for node_dir in self.node_dirs:
            dest_path = os.path.join(node_dir, remote_key)
            if os.path.exists(dest_path):
                os.remove(dest_path)

    def health_check(self):
        """Check all nodes are accessible."""
        missing_nodes = []
        for node_dir in self.node_dirs:
            if not os.path.isdir(node_dir):
                missing_nodes.append(node_dir)

        if missing_nodes:
            return {
                "healthy": False,
                "message": f"Missing nodes: {', '.join(missing_nodes)}",
            }
        return {"healthy": True, "message": "All nodes accessible"}


class S3StorageAdapter(StorageAdapter):
    """
    AWS S3 storage adapter (stub for future implementation).
    
    To enable, set STORAGE_BACKEND=s3 and configure AWS credentials.
    """

    def __init__(self, bucket_name, region=None):
        """
        Initialize S3 storage adapter.
        
        Args:
            bucket_name (str): S3 bucket name.
            region (str): AWS region. Defaults to environment or us-east-1.
        """
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "boto3 not installed. Install with: pip install boto3"
            )

        self.bucket_name = bucket_name
        self.region = region or "us-east-1"
        self.s3_client = boto3.client("s3", region_name=self.region)

    def put(self, local_path, remote_key):
        """Upload file to S3."""
        self.s3_client.upload_file(local_path, self.bucket_name, remote_key)

    def get(self, remote_key, local_path=None):
        """Download file from S3."""
        if local_path is None:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name, Key=remote_key
            )
            return response["Body"].read()
        else:
            self.s3_client.download_file(
                self.bucket_name, remote_key, local_path
            )
            return None

    def exists(self, remote_key):
        """Check if file exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=remote_key)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False

    def delete(self, remote_key):
        """Delete file from S3."""
        self.s3_client.delete_object(Bucket=self.bucket_name, Key=remote_key)

    def health_check(self):
        """Check S3 connectivity."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return {"healthy": True, "message": f"S3 bucket '{self.bucket_name}' accessible"}
        except Exception as e:
            return {
                "healthy": False,
                "message": f"S3 health check failed: {str(e)}",
            }


def get_storage_adapter():
    """
    Factory function to instantiate the configured storage adapter.
    
    Reads STORAGE_BACKEND environment variable:
    - 'local' (default): LocalStorageAdapter with three node directories
    - 's3': S3StorageAdapter with bucket from S3_BUCKET_NAME env var
    
    Returns:
        StorageAdapter: Configured adapter instance.
    """
    backend = os.environ.get("STORAGE_BACKEND", "local").lower()

    if backend == "local":
        runtime_data_dir = os.environ.get(
            "RUNTIME_DATA_DIR",
            "/tmp/forensic2" if os.environ.get("VERCEL") else os.path.dirname(os.path.abspath(__file__))
        )
        node_dirs = [
            os.path.join(runtime_data_dir, "storage_nodes", f"node{i}")
            for i in range(1, 4)
        ]
        return LocalStorageAdapter(node_dirs)

    elif backend == "s3":
        bucket_name = os.environ.get("S3_BUCKET_NAME")
        if not bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable not set")
        region = os.environ.get("AWS_REGION")
        return S3StorageAdapter(bucket_name, region)

    else:
        raise ValueError(
            f"Unknown storage backend: {backend}. Supported: local, s3"
        )
