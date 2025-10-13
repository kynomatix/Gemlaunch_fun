import os
import json
import requests
import logging
from typing import Dict, Optional

class PinataService:
    """Service for uploading files and metadata to IPFS via Pinata"""
    
    def __init__(self):
        self.jwt = os.environ.get('PINATA_JWT')
        self.base_url = 'https://api.pinata.cloud'
        
        if not self.jwt:
            logging.warning("Pinata JWT not found - IPFS uploads will not work")
    
    def upload_file(self, file_path: str, name: str) -> Optional[str]:
        """Upload file to IPFS via Pinata, returns IPFS hash"""
        url = f'{self.base_url}/pinning/pinFileToIPFS'
        headers = {
            'Authorization': f'Bearer {self.jwt}'
        }
        
        # Determine MIME type from file extension
        mime_type = 'application/octet-stream'  # Default
        if file_path.lower().endswith('.webp'):
            mime_type = 'image/webp'
        elif file_path.lower().endswith('.png'):
            mime_type = 'image/png'
        elif file_path.lower().endswith('.jpg') or file_path.lower().endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif file_path.lower().endswith('.gif'):
            mime_type = 'image/gif'
        
        try:
            with open(file_path, 'rb') as f:
                # Include MIME type in the tuple to ensure proper content-type
                files = {'file': (name, f, mime_type)}
                metadata = {'name': name}
                response = requests.post(
                    url,
                    files=files,
                    headers=headers,
                    data={'pinataMetadata': json.dumps(metadata)}
                )
                
                if response.status_code == 200:
                    ipfs_hash = response.json()['IpfsHash']
                    logging.info(f"Uploaded to IPFS: {ipfs_hash}")
                    return ipfs_hash
                else:
                    logging.error(f"Pinata upload failed: {response.text}")
                    return None
        except Exception as e:
            logging.error(f"Error uploading to Pinata: {str(e)}")
            return None
    
    def upload_json(self, data: Dict, name: str) -> Optional[str]:
        """Upload JSON metadata to IPFS via Pinata"""
        url = f'{self.base_url}/pinning/pinJSONToIPFS'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.jwt}'
        }
        
        try:
            payload = {
                'pinataContent': data,
                'pinataMetadata': {'name': name}
            }
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                ipfs_hash = response.json()['IpfsHash']
                logging.info(f"Uploaded JSON to IPFS: {ipfs_hash}")
                return ipfs_hash
            else:
                logging.error(f"Pinata JSON upload failed: {response.text}")
                return None
        except Exception as e:
            logging.error(f"Error uploading JSON to Pinata: {str(e)}")
            return None
    
    def get_ipfs_url(self, ipfs_hash: str, filename: str = 'image.webp') -> str:
        """Get public IPFS URL from hash with filename for proper content-type"""
        return f'https://gateway.pinata.cloud/ipfs/{ipfs_hash}?filename={filename}'
