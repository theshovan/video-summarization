from flask import Flask, render_template, request, jsonify
import os
import speech_recognition as sr
from pydub import AudioSegment
import moviepy.editor as mp
from googletrans import Translator
import tempfile
import base64
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Initialize translator
translator = Translator()

def extract_audio_from_video(video_data):
    """Extract audio from video data with better quality"""
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video:
            temp_video.write(video_data)
            temp_video_path = temp_video.name

        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio_path = temp_audio.name

        # Extract audio using moviepy with better settings
        video = mp.VideoFileClip(temp_video_path)
        # Use higher quality audio extraction
        video.audio.write_audiofile(
            temp_audio_path, 
            verbose=False, 
            logger=None,
            fps=16000,  # Higher sample rate
            bitrate='128k'  # Higher bitrate
        )
        video.close()

        # Read audio data
        with open(temp_audio_path, 'rb') as f:
            audio_data = f.read()

        # Cleanup
        os.unlink(temp_video_path)
        os.unlink(temp_audio_path)

        return audio_data

    except Exception as e:
        print(f"Error extracting audio: {e}")
        # Cleanup in case of error
        try:
            if 'temp_video_path' in locals():
                os.unlink(temp_video_path)
            if 'temp_audio_path' in locals():
                os.unlink(temp_audio_path)
        except:
            pass
        return None

def transcribe_long_audio(audio_data, language='en-IN'):
    """Transcribe longer audio by splitting into chunks"""
    try:
        recognizer = sr.Recognizer()
        
        # Create temporary audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name

        # Load audio file for processing
        audio_segment = AudioSegment.from_file(temp_audio_path)
        
        # Calculate duration in milliseconds
        duration_ms = len(audio_segment)
        print(f"Audio duration: {duration_ms/1000} seconds")
        
        # Split into 30-second chunks with 5-second overlap
        chunk_duration = 30000  # 30 seconds
        overlap = 5000  # 5 seconds overlap
        
        full_text = ""
        chunk_count = 0
        
        for start_ms in range(0, duration_ms, chunk_duration - overlap):
            end_ms = min(start_ms + chunk_duration, duration_ms)
            
            # Extract chunk
            audio_chunk = audio_segment[start_ms:end_ms]
            
            # Save chunk to temporary file
            chunk_path = f"{temp_audio_path}_chunk_{chunk_count}.wav"
            audio_chunk.export(chunk_path, format="wav")
            
            try:
                # Transcribe chunk
                with sr.AudioFile(chunk_path) as source:
                    # Adjust for ambient noise
                    recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio_data = recognizer.record(source)
                    
                    # Transcribe based on language
                    if language == 'hi-IN':
                        chunk_text = recognizer.recognize_google(audio_data, language='hi-IN')
                    else:
                        chunk_text = recognizer.recognize_google(audio_data, language='en-IN')
                    
                    full_text += chunk_text + " "
                    print(f"Chunk {chunk_count}: {len(chunk_text)} characters")
                    chunk_count += 1
                    
            except sr.UnknownValueError:
                print(f"Chunk {chunk_count}: Could not understand audio")
            except sr.RequestError as e:
                print(f"Chunk {chunk_count}: Error with speech recognition: {e}")
            except Exception as e:
                print(f"Chunk {chunk_count}: Error: {e}")
            
            # Clean up chunk file
            try:
                os.unlink(chunk_path)
            except:
                pass
            
            # Stop if we have enough text (safety limit)
            if len(full_text) > 5000:  # Stop after 5000 characters
                break
        
        # Cleanup main audio file
        os.unlink(temp_audio_path)
        
        full_text = full_text.strip()
        print(f"Total transcribed text: {len(full_text)} characters")
        return full_text if full_text else None

    except Exception as e:
        print(f"Error in long audio transcription: {e}")
        # Cleanup in case of error
        try:
            if 'temp_audio_path' in locals():
                os.unlink(temp_audio_path)
        except:
            pass
        return None

def transcribe_audio_file(audio_data, file_extension, language='en-IN'):
    """Transcribe audio file with chunking support"""
    try:
        # Create temporary audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name

        # Convert to WAV if needed
        if file_extension != 'wav':
            audio_segment = AudioSegment.from_file(temp_audio_path)
            wav_path = temp_audio_path.replace(f'.{file_extension}', '.wav')
            # Export with better quality settings
            audio_segment.export(
                wav_path, 
                format="wav",
                parameters=["-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le"]
            )
            os.unlink(temp_audio_path)
            temp_audio_path = wav_path

        # Use the long audio transcription function
        text = transcribe_long_audio(open(temp_audio_path, 'rb').read(), language)
        
        # Cleanup
        os.unlink(temp_audio_path)
        return text

    except Exception as e:
        print(f"Error transcribing audio file: {e}")
        # Cleanup in case of error
        try:
            if 'temp_audio_path' in locals():
                os.unlink(temp_audio_path)
        except:
            pass
        return None

def summarize_text(text, max_sentences=3):
    """Create meaningful summary from text"""
    try:
        if not text or len(text.strip()) < 100:
            return text  # Return original if text is short
        
        # Split into sentences using multiple delimiters
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]  # Remove very short fragments
        
        print(f"Found {len(sentences)} sentences")
        
        if len(sentences) <= max_sentences:
            return text  # Return original if few sentences
        
        # Select key sentences strategically
        selected_sentences = []
        
        # Always include first sentence (usually introduction)
        if sentences:
            selected_sentences.append(sentences[0])
        
        # Include some middle sentences (content)
        if len(sentences) > 3:
            # Get sentences from 25%, 50%, 75% positions
            positions = [0.25, 0.5, 0.75]
            for pos in positions:
                idx = min(int(len(sentences) * pos), len(sentences) - 1)
                if sentences[idx] not in selected_sentences:
                    selected_sentences.append(sentences[idx])
        
        # Include last sentence (usually conclusion)
        if len(sentences) > 1 and len(sentences[-1]) > 20:
            if sentences[-1] not in selected_sentences:
                selected_sentences.append(sentences[-1])
        
        # Limit to max_sentences
        selected_sentences = selected_sentences[:max_sentences]
        
        # Create summary
        summary = '. '.join(selected_sentences) + '.'
        
        # Ensure summary is significantly different from original
        if len(summary) > len(text) * 0.7:  # If too similar
            # Create more aggressive summary - take first and last parts
            words = text.split()
            if len(words) > 80:
                first_part = ' '.join(words[:40])
                last_part = ' '.join(words[-20:])
                summary = f"{first_part}... {last_part}"
            else:
                summary = text  # Return original if can't summarize effectively
        
        print(f"Original: {len(text)} chars, Summary: {len(summary)} chars")
        return summary
        
    except Exception as e:
        print(f"Summarization error: {e}")
        return text

def translate_text(text, src_lang, dest_lang):
    """Translate text between languages with chunking for long texts"""
    try:
        if src_lang == dest_lang or not text:
            return text
            
        print(f"Translating from {src_lang} to {dest_lang}, text length: {len(text)}")
        
        # Split long text into chunks for translation
        if len(text) > 1500:
            chunks = []
            # Split by sentences if possible
            sentences = re.split(r'[.!?]+', text)
            current_chunk = ""
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                    
                if len(current_chunk) + len(sentence) < 1000:
                    current_chunk += sentence + ". "
                else:
                    if current_chunk:
                        translated_chunk = translator.translate(current_chunk, src=src_lang, dest=dest_lang)
                        chunks.append(translated_chunk.text)
                    current_chunk = sentence + ". "
            
            # Don't forget the last chunk
            if current_chunk:
                translated_chunk = translator.translate(current_chunk, src=src_lang, dest=dest_lang)
                chunks.append(translated_chunk.text)
            
            return ' '.join(chunks)
        else:
            translation = translator.translate(text, src=src_lang, dest=dest_lang)
            return translation.text
            
    except Exception as e:
        print(f"Translation error ({src_lang} to {dest_lang}): {e}")
        return f"Translation error: {str(e)}"

def is_hindi_text(text):
    """Check if text contains Hindi characters"""
    hindi_range = '\u0900-\u097F'
    return any(char for char in text if '\u0900' <= char <= '\u097F')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_media():
    try:
        if not request.json or 'fileData' not in request.json:
            return jsonify({'error': 'No file data provided'}), 400
        
        file_data = request.json['fileData']
        file_type = request.json.get('fileType', '')
        file_name = request.json.get('fileName', '')
        language = request.json.get('language', 'en-IN')

        # Decode base64 data
        file_bytes = base64.b64decode(file_data.split(',')[1] if ',' in file_data else file_data)

        transcribed_text = None

        print(f"Processing file: {file_name}, type: {file_type}, language: {language}")

        # Process based on file type
        if file_type.startswith('video/'):
            # Video file - extract audio first
            print("Extracting audio from video...")
            audio_data = extract_audio_from_video(file_bytes)
            if audio_data:
                print("Transcribing audio with chunking...")
                transcribed_text = transcribe_long_audio(audio_data, language)
        elif file_type.startswith('audio/'):
            # Audio file - determine extension
            file_extension = file_name.split('.')[-1].lower() if '.' in file_name else 'wav'
            print(f"Transcribing audio file with extension: {file_extension}")
            transcribed_text = transcribe_audio_file(file_bytes, file_extension, language)
        else:
            return jsonify({'error': 'Unsupported file type'}), 400

        if not transcribed_text:
            return jsonify({'error': 'Failed to transcribe audio. The audio might be too short, unclear, or there might be network issues.'}), 500
        
        print(f"Successfully transcribed {len(transcribed_text)} characters")
        
        # Determine source language for translation
        if language == 'hi-IN' or is_hindi_text(transcribed_text):
            source_language = 'hi'
            original_language = 'Hindi'
        else:
            source_language = 'en'
            original_language = 'English'
        
        print(f"Detected source language: {source_language}")
        
        # Generate translations
        english_full_text = None
        bengali_full_text = None
        
        if source_language == 'hi':
            # Hindi to English
            print("Translating Hindi to English...")
            english_full_text = translate_text(transcribed_text, 'hi', 'en')
            # Hindi to Bengali
            print("Translating Hindi to Bengali...")
            bengali_full_text = translate_text(transcribed_text, 'hi', 'bn')
        else:
            # English to Bengali
            english_full_text = transcribed_text
            print("Translating English to Bengali...")
            bengali_full_text = translate_text(transcribed_text, 'en', 'bn')
        
        # Generate summaries (only create if text is significantly long)
        english_summary = None
        bengali_summary = None
        
        should_summarize = len(transcribed_text) > 200  # Only summarize if text is long enough
        
        if english_full_text:
            if should_summarize and len(english_full_text) > 200:
                print("Generating English summary...")
                english_summary = summarize_text(english_full_text)
            else:
                english_summary = english_full_text  # Use full text as summary if short
                
        if bengali_full_text:
            if should_summarize and len(bengali_full_text) > 200:
                print("Generating Bengali summary...")
                bengali_summary = summarize_text(bengali_full_text)
            else:
                bengali_summary = bengali_full_text  # Use full text as summary if short
        
        print("Processing completed successfully")
        
        return jsonify({
            'success': True,
            'original_text': transcribed_text,
            'original_language': original_language,
            'english_full_text': english_full_text,
            'bengali_full_text': bengali_full_text,
            'english_summary': english_summary,
            'bengali_summary': bengali_summary,
            'text_length': len(transcribed_text),
            'was_summarized': should_summarize
        })
        
    except Exception as e:
        print(f"Processing error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Processing error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)