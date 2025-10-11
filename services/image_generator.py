"""
AI-Powered Token Image Generator
Uses OpenRouter Llama for prompt enhancement and Replicate FLUX for image generation
Uploads generated images to IPFS via Pinata for permanent storage
"""

import os
import logging
import requests
import replicate

def enhance_prompt_with_llama(token_name, symbol, description):
    """
    Enhance a basic token description into a detailed image generation prompt using Llama
    
    Args:
        token_name: Name of the token
        symbol: Token symbol/ticker
        description: Basic description of the token
    
    Returns:
        str: Enhanced prompt for image generation
    """
    try:
        api_token = os.environ.get('OPENROUTER')
        if not api_token:
            raise Exception("OpenRouter API key not found")
        
        prompt_template = f"""Create a detailed image generation prompt for a cryptocurrency token. Token name: {token_name}, Symbol: {symbol}, Description: {description}. Style requirements: teal/turquoise color themes (Kaspa blockchain colors), simple illustrative art style, clean and modern, minimalist, cryptocurrency aesthetic. IMPORTANT: The design should work well as a small thumbnail - avoid excessive detail. Focus on bold shapes and clear visual hierarchy. No text in the image. Respond with ONLY the image prompt, no other text."""
        
        logging.debug(f"Enhancing prompt for token: {token_name} ({symbol})")
        
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_token}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://gemlaunch.fun',
                'X-Title': 'Gemlaunch.fun'
            },
            json={
                'model': 'meta-llama/llama-3.1-70b-instruct',
                'messages': [
                    {'role': 'system', 'content': 'You are an expert at creating detailed image generation prompts. Respond with ONLY the prompt text, no explanations or additional text.'},
                    {'role': 'user', 'content': prompt_template}
                ],
                'temperature': 0.5,
                'max_tokens': 300
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        enhanced_prompt = result['choices'][0]['message']['content'].strip()
        
        logging.info(f"Enhanced prompt generated: {enhanced_prompt[:100]}...")
        return enhanced_prompt
        
    except Exception as e:
        logging.error(f"Error enhancing prompt with Llama: {str(e)}")
        raise

def generate_image_with_replicate(prompt):
    """
    Generate an image using Replicate FLUX.1 Schnell
    
    Args:
        prompt: Detailed image generation prompt
    
    Returns:
        str: URL of the generated image
    """
    try:
        api_token = os.environ.get('REPLICATE_API_TOKEN')
        if not api_token:
            raise Exception("Replicate API token not found")
        
        logging.debug(f"Generating image with FLUX.1 Schnell")
        
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={
                "prompt": prompt,
                "num_outputs": 1,
                "aspect_ratio": "1:1",
                "output_format": "webp"
            }
        )
        
        output_list = list(output) if output else []
        
        if not output_list or len(output_list) == 0:
            raise Exception("No image generated from Replicate")
        
        image_url = str(output_list[0])
        logging.info(f"Image generated successfully: {image_url}")
        return image_url
        
    except Exception as e:
        logging.error(f"Error generating image with Replicate: {str(e)}")
        raise

def upload_to_ipfs(image_url):
    """
    Upload an image to IPFS via Pinata for permanent storage
    
    Args:
        image_url: URL of the image to upload (e.g., from Replicate)
    
    Returns:
        dict: {"ipfs_url": "ipfs://hash", "gateway_url": "https://gateway.pinata.cloud/ipfs/hash"}
    """
    try:
        api_token = os.environ.get('PINATA_JWT')
        if not api_token:
            raise Exception("Pinata JWT token not found")
        
        logging.debug(f"Downloading image from: {image_url}")
        
        # Download the image from Replicate with timeout
        image_response = requests.get(image_url, timeout=60)
        image_response.raise_for_status()
        
        if not image_response.content:
            raise Exception("Downloaded image is empty")
        
        logging.debug(f"Image downloaded, size: {len(image_response.content)} bytes")
        
        # Prepare the file for upload
        files = {
            'file': ('token_image.webp', image_response.content, 'image/webp')
        }
        
        # Upload to Pinata IPFS
        logging.debug("Uploading to Pinata IPFS...")
        pinata_response = requests.post(
            'https://api.pinata.cloud/pinning/pinFileToIPFS',
            headers={
                'Authorization': f'Bearer {api_token}'
            },
            files=files,
            timeout=120
        )
        
        pinata_response.raise_for_status()
        result = pinata_response.json()
        
        # Validate Pinata response
        if 'IpfsHash' not in result:
            raise Exception(f"Invalid Pinata response: {result}")
        
        ipfs_hash = result['IpfsHash']
        ipfs_url = f"ipfs://{ipfs_hash}"
        gateway_url = f"https://gateway.pinata.cloud/ipfs/{ipfs_hash}"
        
        logging.info(f"Image uploaded to IPFS: {ipfs_url}")
        logging.info(f"Gateway URL: {gateway_url}")
        
        return {
            "ipfs_url": ipfs_url,
            "gateway_url": gateway_url
        }
        
    except Exception as e:
        logging.error(f"Error uploading to IPFS: {str(e)}")
        raise

def generate_token_image(token_name, symbol, description):
    """
    Main function to generate a token image with AI
    
    Args:
        token_name: Name of the token
        symbol: Token symbol/ticker
        description: Basic description of the token
    
    Returns:
        dict: {"success": True, "image_url": url, "gateway_url": url, "enhanced_prompt": prompt} or {"success": False, "error": message}
    """
    try:
        logging.info(f"Starting image generation for token: {token_name} ({symbol})")
        
        enhanced_prompt = enhance_prompt_with_llama(token_name, symbol, description)
        
        replicate_url = generate_image_with_replicate(enhanced_prompt)
        
        # Upload to IPFS for permanent storage
        ipfs_data = upload_to_ipfs(replicate_url)
        
        return {
            "success": True,
            "image_url": ipfs_data["ipfs_url"],
            "gateway_url": ipfs_data["gateway_url"],
            "enhanced_prompt": enhanced_prompt
        }
        
    except Exception as e:
        logging.error(f"Token image generation failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
