import os
import json
import time  
import requests  

from queue import Queue 
import threading

local_data = threading.local()

token_total = 0
time_total = 0
i = 0
system_start_time = time.time()
first_token_total = 0
first_token_backups = 0


def foreach_file(folder_path: str):
    for root, dirs, files in os.walk(folder_path):
        for name in files:
            if name.endswith('.txt'):
                full_path = os.path.join(root, name)
                read_csv(full_path)


def fetch_task(queue):  
    while True:  
        param = queue.get() 
        if param is None:  # 如果收到None，则结束线程  
            break  
        try:  
            http_call(param)
        except requests.RequestException as e:  
            print(f"Error: {e} for URL {param}")  
        finally:  
            queue.task_done()  # 表示队列中的一个项目已被处理


def put_task(file_path: str, queue):
    with open(file_path, mode='r', encoding='utf-8') as f:
        lines = f.readlines()
        for row in lines:
            param = {
                "model": "qwen",
                "messages": [
                    {
                        "role": "user",
                        "type": "text",
                        "content": row
                    }
                ],
            }
            queue.put(param)


def read_f(file_path: str):
        task_queue = Queue()  
        put_task(file_path, task_queue)

        num_threads = 10
        threads = []  
      
        for _ in range(num_threads):  
            thread = threading.Thread(target=fetch_task, args=(task_queue,))  
            thread.start()  
            threads.append(thread)  
     
        for _ in range(num_threads):  
            task_queue.put(None)  

        for thread in threads:  
            thread.join()  


def http_call(param: dict):
    url = 'http://localhost:8080/v1/chat/completions'
    param_json_str = json.dumps(param, indent=4)
    start_time = time.time()
    global i
    global token_total
    global time_total
    global first_token_total
    global system_start_time
    global first_token_backups
    local_data.f_token = None

    requests.packages.urllib3.disable_warnings()
    with requests.post(url, headers=headers, data=param_json_str, stream=True, verify=False) as response:
        if response.status_code == 200:  
            # 打印响应内容  
            tokens = 0
            flag = True 
            for line in response.iter_lines():
                line = line[:-1].decode('utf-8')  
            
                if flag:
                    local_data.f_token = (time.time() - start_time) * 1000
                    i += 1
                    first_token_total += local_data.f_token
                    avg_first_token = first_token_total / i
                    print(f"avg_first_token => {avg_first_token} ms, count: {i}")
                    flag = False 
                if line:
                    tokens = tokens + 1
                if "DONE" in line:
                    end_time = (time.time() - start_time) * 1000
                    decode_time = end_time - local_data.f_token
                    total_time_spent = (time.time() - system_start_time) * 1000
                    token_total += (tokens - 1)
                    time_total += decode_time
                    avg_token_speed = token_total / time_total * 1000
                    print(f"this_time_request_time => {end_time} ms,token_total => {token_total} num, decode_time_total => {time_total} ms, avg_token_speed => {avg_token_speed} /s, total_time_spent =>{total_time_spent} ms")
        else:  
            print(f'请求失败: code={response.status_code}')




if __name__== "__main__" :
    foreach_file('/dataset')