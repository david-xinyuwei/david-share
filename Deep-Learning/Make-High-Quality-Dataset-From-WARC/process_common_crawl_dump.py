import nltk  
import sys  
import os  
from datatrove.executor.local import LocalPipelineExecutor  # 使用本地执行器  
from datatrove.pipeline.extractors import Trafilatura  
from datatrove.pipeline.filters import (  
    GopherQualityFilter,  
    GopherRepetitionFilter,  
    LanguageFilter,  
    URLFilter,  
)  
from datatrove.pipeline.readers import WarcReader  
from datatrove.pipeline.writers.jsonl import JsonlWriter  
  
# 在每个进程中下载punkt数据包  
def download_punkt():  
    nltk.download('punkt')  
    nltk.download('punkt_tab')  
  
# 设置NLTK数据路径  
def set_nltk_data_path():  
    nltk.data.path.append('/root/nltk_data')  
  
# 在主进程中设置NLTK数据路径并下载punkt数据包  
set_nltk_data_path()  
download_punkt()  
  
def main():  
    # DUMP should be given as an argument. Example: CC-MAIN-2023-23  
    if len(sys.argv) != 2:  
        print("Argument required: dump name")  
        sys.exit(-1)  
  
    DUMP = sys.argv[1]  
    MAIN_OUTPUT_PATH = "./output"  # 本地输出路径  
    DATA_PATH = f"./data/{DUMP}/segments/"  
  
    # 调试信息：打印路径和文件列表  
    print(f"Checking files in {DATA_PATH}")  
    for root, dirs, files in os.walk(DATA_PATH):  
        print(f"Found directory: {root}")  
        for file in files:  
            print(f"Found file: {file}")  
  
    if not any(os.scandir(DATA_PATH)):  
        print(f"No files found in {DATA_PATH}")  
        sys.exit(-1)  
  
    # 在每个子进程中设置NLTK数据路径并下载punkt数据包  
    def initializer():  
        set_nltk_data_path()  
        download_punkt()  
  
    # 使用多进程池时，传递initializer函数  
    from multiprocessing import Pool  
  
    with Pool(processes=8, initializer=initializer) as pool:  
        executor = LocalPipelineExecutor(  # 使用本地执行器  
            pipeline=[  
                WarcReader(  
                    DATA_PATH,  # 本地WARC文件路径  
                    glob_pattern="*.warc.gz",  # 我们需要WARC文件  
                    default_metadata={"dump": DUMP},  
                ),  
                URLFilter(exclusion_writer=JsonlWriter(f"{MAIN_OUTPUT_PATH}/removed/url/{DUMP}")),  
                Trafilatura(favour_precision=True),  
                LanguageFilter(  
                    exclusion_writer=JsonlWriter(  
                        f"{MAIN_OUTPUT_PATH}/non_english/",  
                        output_filename="${language}/" + DUMP + "/${rank}.jsonl.gz",  # 文件夹结构：language/dump/file  
                    )  
                ),  
                GopherRepetitionFilter(exclusion_writer=JsonlWriter(f"{MAIN_OUTPUT_PATH}/removed/repetitive/{DUMP}")),  
                GopherQualityFilter(exclusion_writer=JsonlWriter(f"{MAIN_OUTPUT_PATH}/removed/quality/{DUMP}")),  
                JsonlWriter(f"{MAIN_OUTPUT_PATH}/output/{DUMP}"),  
            ],  
            tasks=8,  # 本地任务数，根据你的VM配置调整  
            logging_dir=f"{MAIN_OUTPUT_PATH}/logs/base_processing/{DUMP}",  
        )  
  
        executor.run()  
  
if __name__ == '__main__':  
    main()  

