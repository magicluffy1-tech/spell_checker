import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = "https://nara-speller.co.kr/old_speller/results"
payload = {'text1': '아버지가방에들어가신다. 외않되? 어의업는 실수조내요.'}
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://nara-speller.co.kr/speller/'
}

response = requests.post(url, data=payload, headers=headers, timeout=10, verify=False)
print("Response text length:", len(response.text))

# data = [ 부분을 찾아 그 근처 2000글자 출력
idx = response.text.find("data = [")
if idx != -1:
    print("Found 'data = [' at index:", idx)
    print("Content around 'data = [':")
    print(response.text[idx:idx+2500])
else:
    print("'data = [' not found in response!")
