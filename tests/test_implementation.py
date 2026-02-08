import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_health():
    print("Testing /health ...", end=" ")
    try:
        r = requests.get(f"{BASE_URL}/health")
        if r.status_code == 200:
            print("OK")
            return True
        else:
            print(f"FAIL ({r.status_code})")
            return False
    except Exception as e:
        print(f"FAIL: {e}")
        return False

def test_summarize_with_length():
    print("\nTesting /summarize with length parameter...")
    
    text = """Artificial Intelligence (AI) is intelligence demonstrated by machines, 
    as opposed to the natural intelligence displayed by humans and animals. 
    Leading AI textbooks define the field as the study of intelligent agents. 
    The field was founded on the assumption that human intelligence can be so precisely 
    described that a machine can be made to simulate it. AI research has been divided into subfields 
    that often fail to communicate with each other. These subfields include learning, reasoning, 
    problem solving, perception, and using language."""
    
    for length in ['S', 'M', 'L', 'XL']:
        print(f"  Length {length}: ", end="")
        try:
            r = requests.post(f"{BASE_URL}/summarize", json={"text": text, "length": length})
            if r.status_code == 200:
                data = r.json()
                if "heading" in data and "summary" in data:
                    summary_len = len(data['summary'])
                    print(f"OK (heading: '{data['heading'][:30]}...', summary: {summary_len} chars)")
                else:
                    print(f"FAIL (missing fields: {list(data.keys())})")
            else:
                print(f"FAIL ({r.status_code})")
        except Exception as e:
            print(f"FAIL: {e}")

def test_follow_up():
    print("\nTesting /follow-up ...")
    payload = {
        "question": "What is the main point?",
        "context": "AI is the simulation of human intelligence by machines.",
        "history": []
    }
    try:
        r = requests.post(f"{BASE_URL}/follow-up", json=payload)
        if r.status_code == 200 and "answer" in r.json():
            print("  OK")
        else:
            print(f"  FAIL ({r.status_code})")
    except Exception as e:
        print(f"  FAIL: {e}")

if __name__ == "__main__":
    if test_health():
        test_summarize_with_length()
        test_follow_up()
    else:
        print("Server not running!")
