from dotenv import load_dotenv
import os 

load_dotenv()  
uri = os.getenv("connection_string")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGO = os.getenv("JWT_ALGO")
Frontend = os.getenv("Frontend")