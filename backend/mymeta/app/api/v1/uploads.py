"""File upload endpoint for document parsing."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import uuid
import hashlib
import json
from typing import List, Dict, Set
from pydantic import BaseModel

from app.core.database import get_db
from app.core.auth import get_current_active_user
from app.models.models import User
from app.core.config import settings

router = APIRouter()

# Allowed file extensions for document parsing
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".md", ".markdown"}

# Maximum file size: 200MB (increased for large documents)
MAX_FILE_SIZE = 200 * 1024 * 1024

# Chunk size for streaming upload (8MB chunks)
CHUNK_SIZE = 8 * 1024 * 1024

# Chunk size for chunked upload (5MB per chunk for better reliability)
UPLOAD_CHUNK_SIZE = 5 * 1024 * 1024

# Threshold for using chunked upload (files larger than 50MB use chunked upload)
CHUNKED_UPLOAD_THRESHOLD = 50 * 1024 * 1024


def get_uploads_dir() -> Path:
    """Get the uploads directory path."""
    # Create uploads directory in backend/mymeta/uploads
    uploads_dir = Path(__file__).resolve().parents[3] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


def get_user_uploads_dir(user_id: int) -> Path:
    """Get the user-specific uploads directory."""
    uploads_dir = get_uploads_dir()
    user_dir = uploads_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_chunks_dir(user_id: int) -> Path:
    """Get the directory for storing upload chunks."""
    uploads_dir = get_uploads_dir()
    chunks_dir = uploads_dir / str(user_id) / ".chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    return chunks_dir


def calculate_file_hash(file_path: Path) -> str:
    """Calculate MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


@router.post("/", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload a file for document parsing.
    
    Returns the relative path that can be used with the file_parser tool.
    """
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Get user uploads directory
    user_dir = get_user_uploads_dir(current_user.id)
    
    # Generate unique filename to avoid conflicts
    file_id = str(uuid.uuid4())
    original_name = Path(file.filename).stem
    new_filename = f"{original_name}_{file_id}{file_ext}"
    file_path = user_dir / new_filename
    
    try:
        # Stream file upload to avoid loading entire file into memory
        total_size = 0
        with open(file_path, "wb") as f:
            while True:
                # Read in chunks to handle large files efficiently
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                total_size += len(chunk)
                
                # Check file size during upload (before writing)
                if total_size > MAX_FILE_SIZE:
                    # Clean up partial file
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"文件太大。最大允许大小: {MAX_FILE_SIZE / (1024 * 1024):.1f}MB"
                    )
                
                f.write(chunk)
        
        # Return relative path from user's uploads directory
        # Since working_dir is set to user_uploads_dir, we only need the filename
        # This path can be used with file_parser tool
        relative_path = new_filename
        
        return {
            "filename": file.filename,
            "saved_filename": new_filename,
            "path": relative_path,
            "size": total_size,
            "message": "文件上传成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传文件时出错: {str(e)}"
        )


@router.get("/")
async def list_uploaded_files(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """List all files uploaded by the current user."""
    user_dir = get_user_uploads_dir(current_user.id)
    
    if not user_dir.exists():
        return {"files": []}
    
    files = []
    for file_path in user_dir.iterdir():
        if file_path.is_file():
            stat = file_path.stat()
            files.append({
                "filename": file_path.name,
                "path": file_path.name,  # Relative to user's uploads directory
                "size": stat.st_size,
                "created_at": stat.st_ctime
            })
    
    # Sort by creation time (newest first)
    files.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {"files": files}


@router.delete("/{filename}")
async def delete_file(
    filename: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete an uploaded file."""
    user_dir = get_user_uploads_dir(current_user.id)
    file_path = user_dir / filename
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    # Security check: ensure file is in user's directory
    if not file_path.resolve().is_relative_to(user_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此文件"
        )
    
    try:
        file_path.unlink()
        return {"message": "文件已删除", "filename": filename}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除文件时出错: {str(e)}"
        )


# ==================== Chunked Upload Endpoints ====================

@router.post("/chunked/init", status_code=status.HTTP_200_OK)
async def init_chunked_upload(
    filename: str = Form(...),
    file_size: int = Form(...),
    total_chunks: int = Form(...),
    file_hash: str = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Initialize a chunked upload session.
    
    Returns upload_id and list of already uploaded chunks (for resume).
    """
    # Check file extension
    file_ext = Path(filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件太大。最大允许大小: {MAX_FILE_SIZE / (1024 * 1024):.1f}MB"
        )
    
    # Generate upload_id
    upload_id = str(uuid.uuid4())
    
    # Get chunks directory
    chunks_dir = get_chunks_dir(current_user.id)
    upload_dir = chunks_dir / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save upload metadata
    metadata = {
        "filename": filename,
        "file_size": file_size,
        "total_chunks": total_chunks,
        "file_hash": file_hash,
        "uploaded_chunks": []
    }
    metadata_path = upload_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f)
    
    return {
        "upload_id": upload_id,
        "uploaded_chunks": []  # No chunks uploaded yet
    }


@router.post("/chunked/chunk", status_code=status.HTTP_200_OK)
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    chunk: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Upload a single chunk."""
    chunks_dir = get_chunks_dir(current_user.id)
    upload_dir = chunks_dir / upload_id
    
    # Security check: ensure upload_id belongs to current user
    if not upload_dir.exists() or not upload_dir.resolve().is_relative_to(chunks_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    # Load metadata
    metadata_path = upload_dir / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Check if chunk already uploaded
    if chunk_index in metadata["uploaded_chunks"]:
        return {"message": "Chunk already uploaded", "chunk_index": chunk_index}
    
    # Save chunk
    chunk_path = upload_dir / f"chunk_{chunk_index}"
    try:
        with open(chunk_path, "wb") as f:
            while True:
                data = await chunk.read(8192)  # 8KB buffer
                if not data:
                    break
                f.write(data)
        
        # Update metadata
        if chunk_index not in metadata["uploaded_chunks"]:
            metadata["uploaded_chunks"].append(chunk_index)
            metadata["uploaded_chunks"].sort()
        
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f)
        
        return {
            "message": "Chunk uploaded successfully",
            "chunk_index": chunk_index,
            "uploaded_chunks": metadata["uploaded_chunks"],
            "progress": len(metadata["uploaded_chunks"]) / metadata["total_chunks"] * 100
        }
    except Exception as e:
        # Clean up failed chunk
        chunk_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"上传分片失败: {str(e)}"
        )


@router.post("/chunked/complete", status_code=status.HTTP_201_CREATED)
async def complete_chunked_upload(
    upload_id: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Complete chunked upload by merging all chunks."""
    chunks_dir = get_chunks_dir(current_user.id)
    upload_dir = chunks_dir / upload_id
    
    # Security check
    if not upload_dir.exists() or not upload_dir.resolve().is_relative_to(chunks_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    # Load metadata
    metadata_path = upload_dir / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    # Check if all chunks are uploaded
    if len(metadata["uploaded_chunks"]) != metadata["total_chunks"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"分片未完整。已上传: {len(metadata['uploaded_chunks'])}/{metadata['total_chunks']}"
        )
    
    # Get user uploads directory
    user_dir = get_user_uploads_dir(current_user.id)
    
    # Generate final filename
    file_ext = Path(metadata["filename"]).suffix.lower()
    file_id = str(uuid.uuid4())
    original_name = Path(metadata["filename"]).stem
    new_filename = f"{original_name}_{file_id}{file_ext}"
    file_path = user_dir / new_filename
    
    try:
        # Merge chunks
        with open(file_path, "wb") as f:
            for i in range(metadata["total_chunks"]):
                chunk_path = upload_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"分片 {i} 不存在"
                    )
                
                with open(chunk_path, "rb") as chunk_file:
                    shutil.copyfileobj(chunk_file, f)
        
        # Verify file size
        actual_size = file_path.stat().st_size
        if actual_size != metadata["file_size"]:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件大小不匹配。期望: {metadata['file_size']}, 实际: {actual_size}"
            )
        
        # Clean up chunks
        shutil.rmtree(upload_dir, ignore_errors=True)
        
        relative_path = new_filename
        
        return {
            "filename": metadata["filename"],
            "saved_filename": new_filename,
            "path": relative_path,
            "size": actual_size,
            "message": "文件上传成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"合并文件时出错: {str(e)}"
        )


@router.get("/chunked/status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get the status of a chunked upload (for resume)."""
    chunks_dir = get_chunks_dir(current_user.id)
    upload_dir = chunks_dir / upload_id
    
    # Security check
    if not upload_dir.exists() or not upload_dir.resolve().is_relative_to(chunks_dir.resolve()):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    metadata_path = upload_dir / "metadata.json"
    if not metadata_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="上传会话不存在"
        )
    
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    
    return {
        "upload_id": upload_id,
        "filename": metadata["filename"],
        "total_chunks": metadata["total_chunks"],
        "uploaded_chunks": metadata["uploaded_chunks"],
        "progress": len(metadata["uploaded_chunks"]) / metadata["total_chunks"] * 100
    }

