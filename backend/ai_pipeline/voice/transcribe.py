import time
import uuid
from ai_pipeline.config import config

def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcribes raw audio bytes using Amazon Transcribe.
    Wait for completion (approx 2-4 seconds) and return transcript string.
    """
    import boto3
    import requests
    
    s3 = boto3.client('s3', region_name=config.AWS_REGION)
    transcribe = boto3.client('transcribe', region_name=config.AWS_REGION)
    
    # Detect format based on magic bytes
    # WebM starts with \x1a\x45\xdf\xa3
    # Ogg starts with OggS
    media_format = 'ogg'
    ext = 'ogg'
    if audio_bytes.startswith(b"\x1a\x45\xdf\xa3"):
        media_format = 'webm'
        ext = 'webm'
    elif audio_bytes.startswith(b"OggS"):
        media_format = 'ogg'
        ext = 'ogg'
    elif audio_bytes.startswith(b"RIFF"):
        media_format = 'wav'
        ext = 'wav'

    bucket_name = f"clinicops-audio-{config.AWS_REGION}"
    job_name = f"stt-{uuid.uuid4().hex}"
    file_key = f"temp/{job_name}.{ext}"
    
    try:
        # 1. Ensure bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
        except:
            print(f"[transcribe] Creating bucket: {bucket_name}")
            if config.AWS_REGION == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': config.AWS_REGION}
                )

        # 2. Upload to S3
        print(f"[transcribe] Uploading {media_format} audio to S3: {file_key}")
        s3.put_object(Bucket=bucket_name, Key=file_key, Body=audio_bytes)
        
        # 3. Start Transcription
        print(f"[transcribe] Starting transcription job (en-US): {job_name}")
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': f's3://{bucket_name}/{file_key}'},
            MediaFormat=media_format,
            LanguageCode='en-US'
        )
        
        # 4. Polling for results
        timeout = 25 # Increased timeout
        start_time = time.time()
        job_status = "IN_PROGRESS"
        
        while time.time() - start_time < timeout:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status['TranscriptionJob']['TranscriptionJobStatus']
            if job_status in ['COMPLETED', 'FAILED']:
                break
            time.sleep(1.0) # Slightly slower polling
            
        duration = time.time() - start_time
        print(f"[transcribe] Polling finished after {duration:.1f}s. Final status: {job_status}")

        if job_status == 'COMPLETED':
            transcript_url = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
            print(f"[transcribe] Job completed. Fetching transcript from: {transcript_url}")
            response = requests.get(transcript_url)
            data = response.json()
            transcript = data['results']['transcripts'][0]['transcript']
            print(f"[transcribe] Transcript received: {transcript[:50]}...")
            return transcript
        else:
            print(f"[transcribe] Transcription failed or reached context limit. Status: {job_status}")
            return "Transcription failed"
            
    except Exception as e:
        print(f"[transcribe] Error during transcription: {str(e)}")
        return "Transcription failed"
    finally:
        # Cleanup
        try:
            print(f"[transcribe] Cleaning up S3 and job data...")
            s3.delete_object(Bucket=bucket_name, Key=file_key)
            
            # Defensive check for job status before deleting
            status_check = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            current_status = status_check['TranscriptionJob']['TranscriptionJobStatus']
            if current_status not in ['IN_PROGRESS', 'QUEUED']:
                transcribe.delete_transcription_job(TranscriptionJobName=job_name)
            else:
                print(f"[transcribe] Skipping job deletion as it is still {current_status}.")
        except Exception as cleanup_err:
            # Ignore cleanup errors for non-existent or busy jobs
            pass