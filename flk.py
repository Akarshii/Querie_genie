from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
import os
import time
import base64
import io
from datetime import datetime
from PIL import Image
import PyPDF2
import docx
import google.generativeai as genai
from dotenv import load_dotenv

# Try to import optional modules
try:
    from sel import scrape_website
    from rag_pipeline import prepare_rag_pipeline, retrieve_relevant_chunks
    RAG_AVAILABLE = True
except ImportError:
    print("Warning: RAG modules not available. MoreYeahs-specific features will be limited.")
    RAG_AVAILABLE = False

# Load environment variables
load_dotenv()

# Check if API key is available
if not os.getenv("GEMINI_API_KEY"):
    print("Error: GEMINI_API_KEY not found in environment variables")
    print("Please create a .env file with your Gemini API key")
    exit(1)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your-secret-key-here")

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'bmp', 'docx'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Gemini models
try:
    model = genai.GenerativeModel("gemini-2.0-flash")
    vision_model = genai.GenerativeModel("gemini-2.0-flash")
except Exception as e:
    try:
        # Fallback to stable version
        model = genai.GenerativeModel("gemini-1.5-flash")
        vision_model = genai.GenerativeModel("gemini-1.5-pro")
    except Exception as e2:
        print(f"Error initializing Gemini models: {e2}")
        print("Please check your API key and internet connection")
        exit(1)

# Global variables for chat sessions
chat_sessions = {}
knowledge_ready = False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                try:
                    text += page.extract_text() + "\n"
                except Exception as e:
                    print(f"Error extracting text from page: {e}")
                    continue
        return text if text.strip() else "No text could be extracted from this PDF."
    except Exception as e:
        print(f"Error reading PDF: {str(e)}")
        return f"Error reading PDF: {str(e)}"

def extract_text_from_docx(docx_path):
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(docx_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text if text.strip() else "No text found in this document."
    except Exception as e:
        print(f"Error reading DOCX: {str(e)}")
        return f"Error reading DOCX: {str(e)}"

def extract_text_from_txt(txt_path):
    """Extract text from TXT file"""
    try:
        # Try UTF-8 first
        with open(txt_path, 'r', encoding='utf-8') as file:
            content = file.read()
            return content if content.strip() else "The text file appears to be empty."
    except UnicodeDecodeError:
        # Try with different encodings
        encodings = ['latin-1', 'cp1252', 'iso-8859-1']
        for encoding in encodings:
            try:
                with open(txt_path, 'r', encoding=encoding) as file:
                    content = file.read()
                    return content if content.strip() else "The text file appears to be empty."
            except Exception:
                continue
        return "Error: Could not decode the text file with any supported encoding."
    except Exception as e:
        print(f"Error reading TXT: {str(e)}")
        return f"Error reading TXT: {str(e)}"

def process_uploaded_file(file_path, filename):
    """Process uploaded file and extract content"""
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}", None, "error", filename
        
    file_ext = filename.rsplit('.', 1)[1].lower()
    
    if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
        try:
            # Open and verify image
            image = Image.open(file_path)
            # Convert to RGB if necessary (for JPEG compatibility)
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            return image, None, "image", filename
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return f"Error processing image: {str(e)}", None, "error", filename
    
    elif file_ext == 'pdf':
        text = extract_text_from_pdf(file_path)
        return text, None, "pdf", filename
    
    elif file_ext == 'docx':
        text = extract_text_from_docx(file_path)
        return text, None, "docx", filename
    
    elif file_ext == 'txt':
        text = extract_text_from_txt(file_path)
        return text, None, "txt", filename
    
    else:
        return f"Unsupported file type: {file_ext}", None, "error", filename

def is_moreyeahs_related(question):
    """Check if the question is related to MoreYeahs"""
    if not RAG_AVAILABLE:
        return False
        
    moreyeahs_keywords = [
        'moreyeahs', 'more yeahs', 'company', 'service', 'services', 'product', 'products',
        'pricing', 'price', 'cost', 'contact', 'support', 'team', 'about us', 'location',
        'office', 'business', 'client', 'customer', 'portfolio', 'work', 'project'
    ]
    
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in moreyeahs_keywords)

def get_chat_session(session_id, chat_type='general'):
    """Get or create chat session"""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = {
            'general': model.start_chat(history=[]),
            'rag': model.start_chat(history=[])
        }
    return chat_sessions[session_id][chat_type]

def get_hybrid_response(question, file_content=None, file_type=None, file_name=None, session_id=None):
    """Get response using hybrid approach"""
    
    # Handle image files
    if file_type == "image" and file_content is not None:
        try:
            prompt = f"""
You are a helpful AI assistant. The user has uploaded an image named "{file_name}" and asked: "{question}"

Please analyze the image and provide a comprehensive response. You can:
1. Describe what you see in the image
2. Extract any text visible in the image
3. Answer specific questions about the image content
4. Provide relevant information based on what's shown

Be detailed and helpful in your response.
"""
            response = vision_model.generate_content([prompt, file_content])
            return response.text, "file"
        except Exception as e:
            print(f"Error processing image with AI: {str(e)}")
            return f"Error processing image: {str(e)}", "error"
    
    # Handle text-based files
    elif file_content is not None and file_type in ["pdf", "docx", "txt"]:
        try:
            # Truncate content if too long (Gemini has token limits)
            max_chars = 30000  # Conservative limit
            content_preview = file_content[:max_chars] if len(file_content) > max_chars else file_content
            
            if len(file_content) > max_chars:
                content_preview += "\n\n[Content truncated due to length...]"
            
            prompt = f"""
You are a helpful AI assistant. The user has uploaded a {file_type.upper()} file named "{file_name}" and asked: "{question}"

File Content:
{content_preview}

Based on the file content above, please provide a comprehensive response to the user's question: "{question}"

Please provide a detailed and helpful response based on the file content.
"""
            
            chat = get_chat_session(session_id, 'general')
            response = chat.send_message(prompt)
            return response.text, "file"
        except Exception as e:
            print(f"Error processing text file: {str(e)}")
            return f"Error processing file: {str(e)}", "error"
    
    # MoreYeahs-related questions
    elif is_moreyeahs_related(question) and RAG_AVAILABLE:
        try:
            if knowledge_ready:
                relevant_chunks = retrieve_relevant_chunks(question)
                if relevant_chunks:
                    context = "\n---\n".join(relevant_chunks)
                    
                    prompt = f"""
You are a helpful AI assistant for MoreYeahs company. Use the information from the company's website below to answer the user's question accurately and professionally.

Company Information:
{context}

User Question: {question}

Instructions:
1. Answer based primarily on the provided company information
2. Be conversational and helpful
3. If the specific information isn't in the context, mention that you can provide general guidance but recommend contacting MoreYeahs directly for specific details
4. Always maintain a professional and friendly tone

Answer:
"""
                    
                    chat = get_chat_session(session_id, 'rag')
                    response = chat.send_message(prompt)
                    return response.text, "rag"
            
            # Fallback to general response
            prompt = f"""
The user is asking about MoreYeahs company: "{question}"

I don't have specific information about MoreYeahs in my knowledge base. Please provide a helpful general response and suggest they contact MoreYeahs directly for specific information about their services, pricing, or other company details.

Be professional and helpful in your response.
"""
            chat = get_chat_session(session_id, 'general')
            response = chat.send_message(prompt)
            return response.text, "general"
        except Exception as e:
            print(f"Error in MoreYeahs response: {str(e)}")
            return "I apologize, but I encountered an error. Please try again or contact MoreYeahs directly for assistance.", "error"
    
    # General questions
    try:
        chat = get_chat_session(session_id, 'general')
        response = chat.send_message(question)
        return response.text, "general"
    except Exception as e:
        print(f"Error in general response: {str(e)}")
        return f"I apologize, but I encountered an error processing your question: {str(e)}", "error"

@app.route('/')
def index():
    # Initialize session
    if 'messages' not in session:
        session['messages'] = []
    if 'session_id' not in session:
        session['session_id'] = str(int(time.time())) + str(os.getpid())
    
    return render_template('index.html')

@app.route('/initialize', methods=['POST'])
def initialize():
    global knowledge_ready
    try:
        if not RAG_AVAILABLE:
            return jsonify({'success': True, 'message': 'General AI ready! (RAG features not available)'})
            
        if not knowledge_ready:
            site_text = scrape_website()
            prepare_rag_pipeline(site_text)
            knowledge_ready = True
        
        return jsonify({'success': True, 'message': 'Knowledge base ready!'})
    except Exception as e:
        print(f"Error initializing: {str(e)}")
        return jsonify({'success': False, 'message': f'Error initializing: {str(e)}'})

@app.route('/chat', methods=['POST'])
def chat():
    try:
        question = request.form.get('message', '').strip()
        if not question:
            return jsonify({'error': 'No message provided'}), 400
        
        # Handle file upload
        file_content = None
        file_type = None
        file_name = None
        file_data_url = None
        
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    # Add timestamp to avoid conflicts
                    timestamp = str(int(time.time()))
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Save file
                    file.save(file_path)
                    
                    # Verify file was saved
                    if not os.path.exists(file_path):
                        return jsonify({'error': 'Failed to save uploaded file'}), 500
                    
                    # Process the file
                    file_content, _, file_type, original_name = process_uploaded_file(file_path, file.filename)
                    file_name = original_name
                    
                    # For images, create data URL for display
                    if file_type == "image" and isinstance(file_content, Image.Image):
                        try:
                            buffered = io.BytesIO()
                            # Save as JPEG for better compatibility
                            file_content.save(buffered, format="JPEG", quality=85)
                            img_base64 = base64.b64encode(buffered.getvalue()).decode()
                            file_data_url = f"data:image/jpeg;base64,{img_base64}"
                        except Exception as e:
                            print(f"Error creating image data URL: {str(e)}")
                            # Fallback to PNG
                            try:
                                buffered = io.BytesIO()
                                file_content.save(buffered, format="PNG")
                                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                                file_data_url = f"data:image/png;base64,{img_base64}"
                            except Exception as e2:
                                print(f"Error creating PNG data URL: {str(e2)}")
                                file_data_url = None
                    
                    # Clean up uploaded file
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"Warning: Could not remove temporary file {file_path}: {str(e)}")
                        
                except Exception as e:
                    print(f"Error processing uploaded file: {str(e)}")
                    return jsonify({'error': f'Error processing uploaded file: {str(e)}'}), 500
            elif file and file.filename and not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed. Please upload: txt, pdf, png, jpg, jpeg, gif, bmp, docx'}), 400
        
        # Get response
        session_id = session.get('session_id')
        response_text, response_type = get_hybrid_response(
            question, file_content, file_type, file_name, session_id
        )
        
        # Save to session
        user_message = {
            'role': 'user',
            'content': question,
            'file_name': file_name,
            'file_type': file_type,
            'file_data_url': file_data_url,
            'timestamp': datetime.now().strftime('%H:%M')
        }
        
        assistant_message = {
            'role': 'assistant',
            'content': response_text,
            'type': response_type,
            'timestamp': datetime.now().strftime('%H:%M')
        }
        
        if 'messages' not in session:
            session['messages'] = []
        
        session['messages'].extend([user_message, assistant_message])
        session.modified = True
        
        return jsonify({
            'user_message': user_message,
            'assistant_message': assistant_message
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/clear', methods=['POST'])
def clear_chat():
    try:
        session['messages'] = []
        session_id = session.get('session_id')
        if session_id in chat_sessions:
            del chat_sessions[session_id]
        session.modified = True
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error clearing chat: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/refresh', methods=['POST'])
def refresh_knowledge():
    global knowledge_ready
    try:
        knowledge_ready = False
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error refreshing knowledge: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {str(e)}")
    return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

if __name__ == '__main__':
    print("Starting MoreYeahs AI Assistant...")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Allowed file types: {', '.join(ALLOWED_EXTENSIONS)}")
    print(f"Max file size: {MAX_CONTENT_LENGTH // (1024*1024)}MB")
    app.run(debug=True, host='0.0.0.0', port=5000)