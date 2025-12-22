import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

print("Testing OpenAI API connection...")
print(f"API Key present: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")

if os.getenv('OPENAI_API_KEY'):
    key = os.getenv('OPENAI_API_KEY')
    print(f"API Key starts with: {key[:20]}...")
    
    try:
        client = OpenAI(api_key=key)
        
        # Try a simple completion
        print("\nTesting API call...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Say 'API is working' if you can read this."}
            ],
            max_tokens=50
        )
        
        print(f"✅ SUCCESS! Response: {response.choices[0].message.content}")
        print(f"Model used: {response.model}")
        
    except Exception as e:
        print(f"❌ FAILED! Error: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        
        if "invalid" in str(e).lower() or "auth" in str(e).lower():
            print("\n🔴 The API key appears to be invalid or revoked.")
            print("Please check your OpenAI account at https://platform.openai.com/api-keys")
        elif "quota" in str(e).lower() or "insufficient" in str(e).lower():
            print("\n🔴 You have exceeded your usage quota or have no credits.")
            print("Please check your billing at https://platform.openai.com/account/billing")
else:
    print("❌ No OPENAI_API_KEY found in environment!")
