import jwt
import time
from app.core.config import settings

def create_token():
    # Create a mock Supabase payload with your details
    payload = {
        "aud": "authenticated",           # Required by our auth.py
        "exp": int(time.time()) + 3600,   # Expires in 1 hour
        "sub": "test-user-uuid",          # Mock user ID
        "email": "chetan@example.com",    # Will be used to find/create the user
        "user_metadata": {
            "linkedin_profile_url": "https://linkedin.com/in/chetan-p"
        }
    }

    # Sign it using your secret from .env
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
    
    print("\n✅ Copy this exact token and paste it into Swagger UI:\n")
    print(token)
    print("\n")

if __name__ == "__main__":
    create_token()