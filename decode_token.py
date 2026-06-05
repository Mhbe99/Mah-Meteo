#!/usr/bin/env python3
import jwt
import json
import os

token_str = os.getenv("TOKEN_TO_DECODE", "").strip()

if not token_str:
    print("Set TOKEN_TO_DECODE in environment to decode a token payload.")
    raise SystemExit(1)

try:
    # Decode without verification (just to see payload)
    decoded = jwt.decode(token_str, options={"verify_signature": False})
    print("Token payload:")
    print(json.dumps(decoded, indent=2))
except Exception as e:
    print(f"Error: {e}")
