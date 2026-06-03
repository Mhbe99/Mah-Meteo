#!/usr/bin/env python3
import jwt
import json

token_str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJjbGllbnRfaWQiOjEsInVzZXJuYW1lIjoiZ2VvZGlzLWxlbWV1eCIsImV4cCI6MTc3NDUzNTAwM30.wEaCM0vcXViWSkgH6RL81R07ZZy32EEBH4AQglA-HBg"

try:
    # Decode without verification (just to see payload)
    decoded = jwt.decode(token_str, options={"verify_signature": False})
    print("Token payload:")
    print(json.dumps(decoded, indent=2))
except Exception as e:
    print(f"Error: {e}")
