import secrets
from simple_logger import log

def generate_new_token():
    with open("master_token.txt", 'w') as f:
        f.write(secrets.token_urlsafe(24))
    
    log("SUCCESS", "New random token generated successfully!")

if __name__ == "__main__":
    generate_new_token()