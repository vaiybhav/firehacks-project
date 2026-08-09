#!/usr/bin/env python3
"""
Backend server for Deepgram TTS using Python SDK
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from deepgram import DeepgramClient
import io
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Never commit service credentials. Deepgram also recognizes this conventional
# environment-variable name, but keeping the check explicit gives the frontend
# a useful error when TTS has not been configured.
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
client = DeepgramClient(api_key=DEEPGRAM_API_KEY) if DEEPGRAM_API_KEY else None

@app.route('/speak', methods=['POST'])
def speak():
    """Generate speech from text using Deepgram SDK"""
    try:
        if client is None:
            return jsonify({
                'error': 'TTS is not configured. Set DEEPGRAM_API_KEY before starting the backend.'
            }), 503

        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', 'arcas')  # Default to arcas (deep male voice)
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Generate speech using Deepgram SDK with voice parameter
        # Deepgram uses model format: "aura-2-{voice}-en" for Aura 2 models
        # For Aura models, we can specify voice directly
        try:
            # Try with voice parameter (if supported by SDK)
            response = client.speak.v1.audio.generate(
                text=text,
                voice=voice
            )
        except TypeError:
            # If voice parameter not supported, use model format
            model = f"aura-2-{voice}-en"
            response = client.speak.v1.audio.generate(
                text=text,
                model=model
            )
        
        # Collect all chunks into a single audio file
        audio_data = b''
        for chunk in response:
            audio_data += chunk
        
        if not audio_data:
            return jsonify({'error': 'No audio data received from Deepgram'}), 500
        
        # Return audio as response
        return send_file(
            io.BytesIO(audio_data),
            mimetype='audio/mpeg',
            as_attachment=False,
            download_name='speech.mp3'
        )
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'Deepgram TTS Backend'})

if __name__ == '__main__':
    print("🚀 Starting Deepgram TTS Backend Server...")
    print("📡 Backend will be available at: http://localhost:5001")
    print("🎤 Frontend should call: http://localhost:5001/speak")
    app.run(host='0.0.0.0', port=5001, debug=True)
