import google.generativeai as genai
import os

API_KEY = "AIzaSyADD00hFb_Rr8z_ZIOudUTHKpxtamtf8XE"

def test_sdk():
    print(f"Configuring SDK with key: {API_KEY[:5]}...")
    genai.configure(api_key=API_KEY)
    
    print("Listing models...")
    try:
        with open("models_list.txt", "w", encoding="utf-8") as f:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    print(f"Found model: {m.name}")
                    f.write(f"{m.name}\n")
    except Exception as e:
        print(f"List models failed: {e}")
        return

    print("\nGenerating content with gemini-1.5-flash...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Ping")
        print(f"Response: {response.text}")
        print("SDK Test Successful!")
    except Exception as e:
        print(f"Generate content failed: {e}")

if __name__ == "__main__":
    test_sdk()
