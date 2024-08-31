import os  
import subprocess  
  
def download_warc_file(url, output_dir):  
    # 创建输出目录  
    if not os.path.exists(output_dir):  
        os.makedirs(output_dir)  
  
    # 下载WARC文件  
    print(f"Downloading {url}...")  
    command = f"wget -P {output_dir} {url}"  
    subprocess.run(command, shell=True, check=True)  
  
if __name__ == '__main__':  
    # WARC文件的URL  
    warc_url = "https://data.commoncrawl.org/crawl-data/CC-MAIN-2023-23/segments/1685224643388.45/warc/CC-MAIN-20230527223515-20230528013515-00000.warc.gz"  
      
    # 输出目录  
    output_dir = "/root/dataclean/data/CC-MAIN-2023-23/segments"  
  
    # 下载WARC文件  
    download_warc_file(warc_url, output_dir)  

