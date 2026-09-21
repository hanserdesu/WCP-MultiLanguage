import json, sys, time, urllib.request

BASE = "http://127.0.0.1:10100/v1"
KEY = "opencodex-loopback"

def chat(model, messages, timeout=120, max_tokens=200):
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": False}
    req = urllib.request.Request(BASE + "/chat/completions",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode())
    dt = time.time() - t0
    msg = d.get("choices", [{}])[0].get("message", {})
    return dt, msg.get("content", ""), d.get("usage", {})

if __name__ == "__main__":
    model = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "用一句话回答：德语单词 Aas 的中文释义是什么？"
    try:
        dt, content, usage = chat(model, [{"role": "user", "content": prompt}])
        print(f"OK {model} {dt:.1f}s usage={usage}")
        print("content:", content[:500])
    except Exception as e:
        print(f"FAIL {model}: {type(e).__name__}: {e}")
