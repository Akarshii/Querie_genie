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
from sel import scrape_website  # Import the Selenium scraper from sel.py
from rag_pipeline import prepare_rag_pipeline, retrieve_relevant_chunks

# Load environment variables
load_dotenv()

# Check if API key is available
if not os.getenv("GEMINI_API_KEY"):
    print(" Error: GEMINI_API_KEY not found in environment variables")
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
    print("✅ Gemini 2.0 Flash models initialized")
except Exception as e:
    try:
        # Fallback to stable version
        model = genai.GenerativeModel("gemini-1.5-flash")
        vision_model = genai.GenerativeModel("gemini-1.5-pro")
        print(" Gemini 1.5 models initialized (fallback)")
    except Exception as e2:
        print(f" Error initializing Gemini models: {e2}")
        print("Please check your API key and internet connection")
        exit(1)

# Global variables for unified chat sessions
chat_sessions = {}
knowledge_ready = False
company_context = ""
scraped_content = ""

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

def analyze_conversation_context(session_id, current_question):
    """Enhanced context analysis for better company detection"""
    if session_id not in chat_sessions:
        return False, []
    
    chat_session = chat_sessions[session_id]
    
    # Enhanced MoreYeahs indicators
    moreyeahs_indicators = [
        'moreyeahs', 'more yeahs', 'company', 'service', 'services', 'product', 'products',
        'pricing', 'price', 'cost', 'contact', 'support', 'team', 'about us', 'location',
        'office', 'business', 'client', 'customer', 'portfolio', 'work', 'project',
        'website', 'site', 'link', 'url', 'address', 'phone', 'email', 'job', 'career',
        'opening', 'position', 'hire', 'recruitment', 'apply', 'application',
        'founder', 'ceo', 'established', 'started', 'founded', 'owner', 'management',
        'director', 'executive', 'leadership', 'history', 'background'
    ]
    
    # Get recent messages from history
    recent_context = []
    try:
        for part in chat_session.history[-10:]:
            if hasattr(part, 'text'):
                recent_context.append(part.text.lower())
            elif hasattr(part, 'parts'):
                for sub_part in part.parts:
                    if hasattr(sub_part, 'text'):
                        recent_context.append(sub_part.text.lower())
    except Exception as e:
        print(f"Error analyzing context: {e}")
    
    # Check current question
    current_lower = current_question.lower()
    recent_text = " ".join(recent_context) + " " + current_lower
    
    # Check for company-related content
    is_company_related = any(indicator in recent_text for indicator in moreyeahs_indicators)
    
    # Additional context clues
    contextual_phrases = [
        'your', 'our', 'this company', 'the company', 'your company',
        'who founded', 'who is the founder', 'who started', 'who owns',
        'tell me about', 'what do you do', 'how can you help', 'what services',
        'who is behind', 'company history', 'about the company'
    ]
    
    has_contextual_clues = any(phrase in current_lower for phrase in contextual_phrases)
    
    # Debug logging
    print(f" Context analysis: company_related={is_company_related}, contextual_clues={has_contextual_clues}")
    print(f" Current question: {current_question}")
    
    return is_company_related or has_contextual_clues, recent_context

def get_unified_chat_session(session_id):
    """Get or create unified chat session"""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = model.start_chat(history=[])
    return chat_sessions[session_id]

def get_intelligent_response(question, file_content=None, file_type=None, file_name=None, session_id=None):
    """Enhanced response generation with better company integration"""
    
    # Get unified chat session
    chat = get_unified_chat_session(session_id)
    
    # Analyze conversation context
    is_company_context, recent_context = analyze_conversation_context(session_id, question)
    
    print(f" Processing question: {question}")
    print(f" Company context detected: {is_company_context}")
    print(f" Knowledge ready: {knowledge_ready}")
    
    # Handle image files
    if file_type == "image" and file_content is not None:
        try:
            # Enhanced image prompt with context awareness
            base_prompt = f"""
You are the MoreYeahs AI Assistant, a helpful and intelligent assistant for MoreYeahs company. 

The user has uploaded an image named "{file_name}" and asked: "{question}"

Please analyze the image and provide a comprehensive response. You can:
1. Describe what you see in the image
2. Extract any text visible in the image
3. Answer specific questions about the image content
4. Provide relevant information based on what's shown

"""
            
            if is_company_context:
                base_prompt += """
IMPORTANT: Based on the conversation context, this seems to be related to MoreYeahs company. 
If the image contains company-related content, provide insights that would be relevant to MoreYeahs business context.
"""
            
            if knowledge_ready and company_context:
                base_prompt += f"""
Company Context for Reference:
{company_context[:2000]}...

"""
            
            base_prompt += "Be detailed and helpful in your response, maintaining context from our ongoing conversation."
            
            response = vision_model.generate_content([base_prompt, file_content])
            return response.text, "image"
        except Exception as e:
            print(f"Error processing image with AI: {str(e)}")
            return f"Error processing image: {str(e)}", "error"
    
    # Handle text-based files
    elif file_content is not None and file_type in ["pdf", "docx", "txt"]:
        try:
            # Truncate content if too long
            max_chars = 25000
            content_preview = file_content[:max_chars] if len(file_content) > max_chars else file_content
            
            if len(file_content) > max_chars:
                content_preview += "\n\n[Content truncated due to length...]"
            
            prompt = f"""
You are the MoreYeahs AI Assistant. The user has uploaded a {file_type.upper()} file named "{file_name}" and asked: "{question}"

File Content:
{content_preview}

Based on the file content above, please provide a comprehensive response to: "{question}"

"""
            
            if is_company_context:
                prompt += """
IMPORTANT: This question seems to be in the context of MoreYeahs company. Please provide insights that would be relevant to the business context.
"""
            
            if knowledge_ready and company_context:
                prompt += f"""
For additional context, here's information about MoreYeahs:
{company_context[:1500]}...

"""
            
            prompt += "Maintain context from our ongoing conversation and provide a detailed, helpful response."
            
            response = chat.send_message(prompt)
            return response.text, "file"
        except Exception as e:
            print(f"Error processing text file: {str(e)}")
            return f"Error processing file: {str(e)}", "error"
    
    # Handle regular questions with enhanced company integration
    try:
        # Build context-aware prompt
        prompt = f"""
You are the MoreYeahs AI Assistant, a helpful and intelligent assistant for MoreYeahs company.

User Question: {question}

"""
        
        # Add company context with enhanced retrieval
        if is_company_context and knowledge_ready:
            try:
                print(" Retrieving relevant company information...")
                relevant_chunks = retrieve_relevant_chunks(question, top_k=5)
                
                if relevant_chunks:
                    print(f" Found {len(relevant_chunks)} relevant chunks")
                    for i, chunk in enumerate(relevant_chunks):
                        print(f"Chunk {i+1}: {chunk[:150]}...")
                    
                    company_info = "\n---\n".join(relevant_chunks)
                    prompt += f"""
MOREYEAHS COMPANY INFORMATION (Use this to answer questions about MoreYeahs):
{company_info}

"""
                else:
                    print(" No relevant chunks found, using fallback context")
                    if company_context:
                        prompt += f"""
MOREYEAHS COMPANY INFORMATION:
{company_context[:3000]}...

"""
                    
            except Exception as e:
                print(f" Error retrieving company info: {e}")
                if company_context:
                    prompt += f"""
MOREYEAHS COMPANY INFORMATION:
{company_context[:3000]}...

"""
        elif is_company_context and company_context:
            prompt += f"""
MOREYEAHS COMPANY INFORMATION:
{company_context[:3000]}...

"""
        
        # Enhanced instructions based on context
        if is_company_context:
            prompt += """
CONTEXT: This question is about MoreYeahs company. Use the company information provided above to give accurate, detailed responses.

IMPORTANT INSTRUCTIONS:
1. Use the company information provided to answer accurately and specifically
2. If asked about founder/CEO/management/history, look for this information in the company data above
3. Be specific and helpful - provide detailed information from the company data
4. If the exact information isn't available in the company data, say so clearly but offer related information that is available
5. Maintain a professional, helpful tone as a company representative
6. Don't make up information - only use what's provided in the company data

"""
        else:
            prompt += """
INSTRUCTIONS:
1. If this seems to be about MoreYeahs company, use any available company information
2. If this is a general question, provide helpful general assistance
3. Maintain context from our ongoing conversation
4. Be conversational, professional, and helpful

"""
        
        prompt += "Provide a helpful, accurate response based on the information available:"
        
        print(f" Sending prompt to AI (length: {len(prompt)})")
        
        response = chat.send_message(prompt)
        
        # Determine response type for UI
        response_type = "company" if is_company_context else "general"
        
        print(f" Generated response (type: {response_type})")
        
        return response.text, response_type
        
    except Exception as e:
        print(f" Error in intelligent response: {str(e)}")
        import traceback
        traceback.print_exc()
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
    global knowledge_ready, company_context, scraped_content
    try:
        print(" Initializing MoreYeahs knowledge base...")
        
        # Scrape website using Selenium scraper from sel.py
        try:
            print(" Starting website scraping...")
            site_text = scrape_website()
            print(f" Scraped {len(site_text)} characters from website")
            
            # Debug: Check if we got meaningful content
            if len(site_text) < 1000:
                print(" Warning: Very little content scraped from website")
                print(f"Sample content: {site_text[:500]}")
            else:
                print("Good amount of content scraped")
            
            # Save scraped content for debugging
            with open("debug_scraped_content.txt", "w", encoding="utf-8") as f:
                f.write(site_text)
            print(" Scraped content saved to debug_scraped_content.txt")
            
            # Store the scraped content globally
            scraped_content = site_text
            
        except Exception as scrape_error:
            print(f" Error scraping website: {scrape_error}")
            import traceback
            traceback.print_exc()
            # Use fallback content if scraping fails
            site_text = """
            MoreYeahs Company Information:
            MoreYeahs is a technology company that provides various services including web development, 
            software solutions, and digital marketing services.
            
            We are committed to delivering high-quality solutions to our clients.
            
            For more information, please visit our website at https://www.moreyeahs.com or contact us directly.
            """
            scraped_content = site_text
        
        # Prepare RAG pipeline
        try:
            print("🔧 Preparing RAG pipeline...")
            prepare_rag_pipeline(site_text)
            print(" RAG pipeline prepared successfully")
        except Exception as rag_error:
            print(f" Error preparing RAG pipeline: {rag_error}")
            import traceback
            traceback.print_exc()
            raise rag_error
        
        # Store company context
        company_context = site_text[:5000]  # Store first 5000 chars for context
        knowledge_ready = True
        
        # Test RAG retrieval with multiple queries
        test_queries = ["founder CEO MoreYeahs", "services products", "about company"]
        for query in test_queries:
            try:
                test_chunks = retrieve_relevant_chunks(query, top_k=3)
                print(f" Test query '{query}' returned {len(test_chunks)} chunks")
                for i, chunk in enumerate(test_chunks):
                    print(f"  Chunk {i+1}: {chunk[:100]}...")
            except Exception as test_error:
                print(f" Warning: RAG test failed for '{query}': {test_error}")
        
        return jsonify({
            'success': True, 
            'message': f'MoreYeahs AI Assistant fully ready! Loaded {len(site_text)} characters of company data.'
        })
        
    except Exception as e:
        print(f" Error initializing: {str(e)}")
        import traceback
        traceback.print_exc()
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
        
        # Get intelligent response
        session_id = session.get('session_id')
        response_text, response_type = get_intelligent_response(
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
        import traceback
        traceback.print_exc()
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
    global knowledge_ready, company_context, scraped_content
    try:
        print(" Refreshing knowledge base...")
        knowledge_ready = False
        company_context = ""
        scraped_content = ""
        
        # Clear any existing chat sessions to start fresh
        chat_sessions.clear()
        
        return jsonify({'success': True, 'message': 'Knowledge base refreshed. Please initialize again.'})
    except Exception as e:
        print(f"Error refreshing knowledge: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/debug', methods=['GET'])
def debug_status():
    """Debug endpoint to check system status"""
    try:
        # Import chunks safely
        chunks_count = 0
        try:
            from rag_pipeline import chunks
            chunks_count = len(chunks) if chunks else 0
        except:
            chunks_count = 0
        
        return jsonify({
            'knowledge_ready': knowledge_ready,
            'company_context_length': len(company_context) if company_context else 0,
            'scraped_content_length': len(scraped_content) if scraped_content else 0,
            'active_sessions': len(chat_sessions),
            'chunks_available': chunks_count,
            'upload_folder': UPLOAD_FOLDER,
            'allowed_extensions': list(ALLOWED_EXTENSIONS)
        })
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/test_retrieval', methods=['POST'])
def test_retrieval():
    """Test RAG retrieval functionality"""
    try:
        data = request.get_json()
        query = data.get('query', 'founder CEO MoreYeahs') if data else 'founder CEO MoreYeahs'
        
        if not knowledge_ready:
            return jsonify({'error': 'Knowledge base not ready'})
        
        chunks = retrieve_relevant_chunks(query, top_k=3)
        
        return jsonify({
            'query': query,
            'chunks_found': len(chunks),
            'chunks': chunks[:3]  # Return first 3 chunks
        })
        
    except Exception as e:
        print(f"Error in test retrieval: {str(e)}")
        return jsonify({'error': str(e)})

@app.route('/view_scraped', methods=['GET'])
def view_scraped():
    """View scraped content for debugging"""
    try:
        if not scraped_content:
            return jsonify({'error': 'No scraped content available'})
        
        # Return first 5000 characters for review
        return jsonify({
            'content_length': len(scraped_content),
            'sample_content': scraped_content[:5000],
            'knowledge_ready': knowledge_ready
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large. Maximum size is 16MB.'}), 413

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {str(e)}")
    import traceback
    traceback.print_exc()
    return jsonify({'error': 'An unexpected error occurred. Please try again.'}), 500

if __name__ == '__main__':
    print("Starting MoreYeahs AI Assistant...")
    app.run(debug=True, host='0.0.0.0', port=5000)