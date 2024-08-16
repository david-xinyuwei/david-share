# Make High Quality Dataset from WARC

 In the following subsections, we will explain each step involved in generating High Qualit dataset.

## What is good data?

### Using a "clean" corpus and perplexity check
- Method: Train a model using a high-quality corpus (e.g., Wikipedia) and then use this model to check the perplexity of the new dataset.
- Advantages:
Quick: Can quickly assess the quality of the dataset.
Simple: Relatively simple to implement, does not require complex computational resources.
- Disadvantages:
Limitations: Low perplexity does not necessarily mean better performance on specific tasks.
Single Metric: Perplexity is just a single metric and cannot fully reflect the quality of the dataset.

### Training small models and testing on evaluation tasks
- Method: Extract a portion of data from the dataset, train a small model, and test the model's performance on a set of specific evaluation tasks (e.g., SQuAD, GLUE, etc.).
- Advantages:
Specific: Provides specific performance feedback by testing the model on actual tasks.
Diversity: Allows for the selection of various evaluation tasks to comprehensively assess the dataset quality.
- Disadvantages:
Resource Demand: Requires a certain amount of computational resources and time.
Task Selection: Needs to select diverse and representative evaluation tasks, which may increase complexity.

### Early signal method
- Method: Train a small model and conduct preliminary evaluations on some simple and quick benchmark tasks (e.g., text classification, sentiment analysis, etc.).
- Advantages:
Rapid Iteration: Quickly obtain initial feedback, facilitating rapid iteration and optimization.
Suitable for Early Stages: Helps quickly screen datasets in the early stages of development.
- Disadvantages:
Simple Tasks: These tasks may be relatively simple and may not fully represent the model's performance on complex tasks.
Preliminary Evaluation: Only provides initial performance feedback, which may require further detailed evaluation.

### Using GPT-4 for evaluation
- Method: Use the GPT-4 model to evaluate the new dataset, potentially including various tasks (e.g., text generation, question answering, sentiment analysis, etc.).
Advantages:
High-Quality Evaluation: As a powerful language model, GPT-4 can provide high-quality evaluation results, especially on complex tasks.
Multi-Task Capability: Can evaluate on various tasks, providing comprehensive performance feedback.
Real-World Usage: Evaluation results are closer to actual usage, especially if your final application is also based on similar advanced models.
- Disadvantages:
Computational Resources: Training and evaluating GPT-4 requires a large amount of computational resources and time, which may increase costs.
Complexity: The complexity of GPT-4 means more potential issues during debugging and optimization.
Overfitting Risk: If not careful, there is a risk of over-optimizing specific tasks, leading to poorer performance on other tasks.

### Summary
- Using a "clean" corpus and perplexity check: Suitable for quick, preliminary quality assessment but limited to a single metric.
- Training small models and testing on evaluation tasks: Suitable for scenarios requiring specific task performance feedback but requires more resources and task selection.
- Early signal method: Suitable for the early stages of development to quickly screen datasets but involves simpler tasks.
- Using GPT-4 for evaluation: Suitable for scenarios requiring high-quality and comprehensive evaluation, providing feedback closest to actual usage but with high resource demands.


## Prepare environment
### Create conda env
```
#conda create --name=dataclean python=3.10  
#conda activate dataclean  
#pip install datatrove[all]  
#pip install datatrove trafilatura awscli 
#aws configure  

```
### Download WARC
Access the following link to check WARC file address:
https://data.commoncrawl.org/crawl-data/CC-MAIN-2023-23/index.html

Download this file :
```
WARC	warc.paths.gz	80000	86.77
```

Check file path just as follwing in warc.paths.gz:
```
crawl-data/CC-MAIN-2023-23/segments/1685224643388.45/warc/CC-MAIN-20230527223515-20230528013515-00000.warc.gz
```
Download files as follwing script:
```
(dataclean) root@david1a100:~/dataclean# cat download_warc_file.py
import os
import subprocess

def download_warc_file(url, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    print(f"Downloading {url}...")
    command = f"wget -P {output_dir} {url}"
    subprocess.run(command, shell=True, check=True)

if __name__ == '__main__':
    warc_url = "https://data.commoncrawl.org/crawl-data/CC-MAIN-2023-23/segments/1685224643388.45/warc/CC-MAIN-20230527223515-20230528013515-00000.warc.gz"

    output_dir = "/root/dataclean/data/CC-MAIN-2023-23/segments"

    download_warc_file(warc_url, output_dir)
```
## Basic data processing
I wrote this part of code according to process_common_crawl_dump.py, I modified many original code.

My code uses the local executor LocalPipelineExecutor to execute the data processing pipeline, which includes the following steps: 
- reading WARC files
- filtering URLs
- extracting content using Trafilatura
- filtering non-English content
- filtering duplicate content
- filtering low-quality content
- writing the processed data to JSONL files.

```
(dataclean) root@david1a100:~/dataclean# cat process_common_crawl_dump.py
```
```
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

def download_punkt():
    nltk.download('punkt')
    nltk.download('punkt_tab')


def set_nltk_data_path():
    nltk.data.path.append('/root/nltk_data')

set_nltk_data_path()
download_punkt()

def main():
    # DUMP should be given as an argument. Example: CC-MAIN-2023-23
    if len(sys.argv) != 2:
        print("Argument required: dump name")
        sys.exit(-1)

    DUMP = sys.argv[1]
    MAIN_OUTPUT_PATH = "./output"  
    DATA_PATH = f"./data/{DUMP}/segments/"
    print(f"Checking files in {DATA_PATH}")
    for root, dirs, files in os.walk(DATA_PATH):
        print(f"Found directory: {root}")
        for file in files:
            print(f"Found file: {file}")

    if not any(os.scandir(DATA_PATH)):
        print(f"No files found in {DATA_PATH}")
        sys.exit(-1)

    def initializer():
        set_nltk_data_path()
        download_punkt()

    from multiprocessing import Pool

    with Pool(processes=8, initializer=initializer) as pool:
        executor = LocalPipelineExecutor(  
            pipeline=[
                WarcReader(
                    DATA_PATH,  
                    glob_pattern="*.warc.gz", 
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
            tasks=8, 
            logging_dir=f"{MAIN_OUTPUT_PATH}/logs/base_processing/{DUMP}",
        )

        executor.run()

if __name__ == '__main__':
    main()
```
Run script as following:
```
python process_common_crawl_dump.py CC-MAIN-2023-23
```
Script will run for 26 minutes, final output is as follwing:
```
2024-08-14 05:11:53.451 | INFO     | datatrove.utils.logging:add_task_logger:47 - Launching pipeline for rank=0
2024-08-14 05:11:53.452 | INFO     | datatrove.utils.logging:log_pipeline:76 -
--- 🛠️ PIPELINE 🛠
📖 - READER: 🕷 Warc
🔻 - FILTER: 😈 Url-filter
🛢 - EXTRAC: ⛏ Trafilatura
🔻 - FILTER: 🌍 Language ID
🔻 - FILTER: 👯 Gopher Repetition
🔻 - FILTER: 🥇 Gopher Quality
💽 - WRITER: 🐿 Jsonl
2024-08-14 05:11:53.452 | INFO     | datatrove.pipeline.readers.base:read_files_shard:193 - Reading input file CC-MAIN-20230527223515-20230528013515-00000.warc.gz
[nltk_data]   Package punkt is already up-to-date!
[nltk_data] Downloading package punkt_tab to /root/nltk_data...
[nltk_data]   Package punkt_tab is already up-to-date!
2024-08-14 05:11:55.704 | WARNING  | datatrove.pipeline.extractors.base:run:60 - ❌ Error "" while cleaning record text. Skipping record.
...
2024-08-14 05:38:47.661 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 8/8 tasks completed.
2024-08-14 05:38:47.686 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 8 tasks 📉📉📉

Total Runtime: 26 minutes and 36 seconds

📖 - READER: 🕷 Warc
    Runtime: (2.11%) 33 seconds [0.29 milliseconds±3.12 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 4795961005 [min=1, max=1048576, 140974.75±182620/doc], documents: 34019 [34019.00/input_file]}
🔻 - FILTER: 😈 Url-filter
    Runtime: (0.35%) 5 seconds [0.16 milliseconds±11.08 milliseconds/doc]
    Stats: {total: 34020, forwarded: 33834, doc_len: 4776069530 [min=1, max=1048576, 141161.84±182866/doc], dropped: 186, dropped_domain: 90, dropped_hard_blacklisted: 67, dropped_blacklisted_subword: 21, dropped_soft_blacklisted: 6, dropped_subdomain: 2}
🛢 - EXTRAC: ⛏ Trafilatura
    Runtime: (75.94%) 20 minutes and 12 seconds [35.84 milliseconds±29.25 milliseconds/doc]
    Stats: {total: 33834, forwarded: 27384, doc_len: 57232496 [min=1, max=551300, 2090.00±6280/doc], dropped: 4168}
🔻 - FILTER: 🌍 Language ID
    Runtime: (0.91%) 14 seconds [0.53 milliseconds±2.54 milliseconds/doc]
    Stats: {total: 27384, dropped: 16500, forwarded: 10884, doc_len: 24989254 [min=2, max=73080, 2295.96±4166/doc]}
🔻 - FILTER: 👯 Gopher Repetition
    Runtime: (13.00%) 3 minutes and 27 seconds [19.07 milliseconds±33.46 milliseconds/doc]
    Stats: {total: 10884, forwarded: 8161, doc_len: 21401662 [min=5, max=73080, 2622.43±4274/doc], dropped: 2723, dropped_top_4_gram: 345, dropped_dup_line_frac: 633, dropped_top_2_gram: 796, dropped_duplicated_5_n_grams: 281, dropped_top_3_gram: 399, dropped_duplicated_6_n_grams: 25, dropped_dup_line_char_frac: 173, dropped_duplicated_8_n_grams: 13, dropped_duplicated_10_n_grams: 16, dropped_duplicated_9_n_grams: 23, dropped_duplicated_7_n_grams: 19}
🔻 - FILTER: 🥇 Gopher Quality
    Runtime: (7.55%) 2 minutes [14.76 milliseconds±8.44 milliseconds/doc]
    Stats: {total: 8161, dropped: 2433, dropped_gopher_too_many_end_ellipsis: 232, dropped_gopher_below_alpha_threshold: 1201, forwarded: 5728, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc], dropped_gopher_short_doc: 941, dropped_gopher_too_many_bullets: 49, dropped_gopher_enough_stop_words: 6, dropped_gopher_below_avg_threshold: 1, dropped_gopher_too_many_ellipsis: 1, dropped_gopher_too_many_hashes: 2}
💽 - WRITER: 🐿 Jsonl
    Runtime: (0.14%) 2 seconds [0.40 milliseconds±0.60 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 5728, total: 5728, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc]}
```
### Check data processing result

```
root@david1a100:~/dataclean/output/output/CC-MAIN-2023-23# zcat ./00000.jsonl.gz | head -n 2 | jq .
```
Output:
```
{
  "text": "Buy Ambien Online Legally (Zolpidem) belongs to the imidazopyridines class of opioids. Ambien complements the exceptional of sleep via way of means of decreasing the time it takes to fall asleep, decreasing the frequency of nocturnal awakenings, and growing the general period of sleep. Lengthens the second one degree of sleep and the deep sleep degree (III and IV). It does now no longer make you sleepy throughout the day. If you’re seeking to Buy Ambien Online at an inexpensive cost, come to our on line pharmacy.",
  "id": "<urn:uuid:dd20979b-ada8-4c5b-b53e-4ade7274bc1b>",
  "metadata": {
    "dump": "CC-MAIN-2023-23",
    "url": "http://42627.dynamicboard.de/u101117_ambienusa.html",
    "date": "2023-05-27T23:12:51Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.8990675806999207
  }
```
```
}
{
  "text": "My little guy turned two over the summer and we celebrated with an oh-so-cute Golf Birthday Party. He is all boy and loves anything that includes a stick and ball, which made choosing the golf theme fairly easy. We had fun golfing games, snacks & treats and each little caddie even received there very own golf bag. The post was getting fairly large I decided to split it in two parts. Part one covers the favor and dessert table and part two will focus on the food and games. Enjoy!\nGolf Pro Shop for the favor table\nEach “Golf Pro” received his/her own set of golf clubs (thank you Target dollar section for saving the day!), a blue or green visor I purchased at Joann’s, practice golf balls and a water bottle to stay hydrated on the course.\nI created the backdrop for the dessert table with a tan table cloth I had and pinned it to the window frame with thumb tacks (my husband wasn’t too happy about that one…opps!) I used 12” white tissue paper balls that I purchased from Devra Party and hung them by grosgrain ribbon.\nI wanted to use items on the dessert table that went along with the theme so I racked my brain for some golf terms. The sign over the table was “Caddie’s Sweet Spot” (sweet spot refers to the center point of the face of the club).\nThere was a “water hazard” ~ blue jell-o jigglers, “wormburners” (which is the term for a ball that skims the grass) ~ chocolate pudding pack topped with crumbled Oreos and gummy worms plus a sand trap of “doughnut hole in one” ~ made with powder sugar doughnuts and crumbled graham crackers for the sand.\nI also made cake pops that resembled golf balls ~ some like a lollipop and others with a golf flag and the number two for the birthday boy. The kids had a few candy choices and a small bag to fill so they could bring treats home.\n“Wormburners” – Chocolate pudding cups topped with crushed oreos and gummy worms\nGreen Grass Cupcakes, with white gumball and printable golf flags.\nThank you so much to everyone who helped make this party amazing, I couldn’t have done it without you.\nVendor List:\nPhotography: Andary Studio\nParty Printables: Printable Studio by 505 Design, Inc\nGolf Club Sets: Target Dollar Section\nFoam Visors: Joann’s\nGreen & White Tissue Balls: Devra Party\nGreen Polka Dot Balloons: Paws Attraction Boutique\nCupcakes – My super talented sister\nInterested in hosting your own Golf Themed Party – Check out the Golf Pro Printable set now available in the shop.\nMore details coming soon….\nThanks for stopping by! Cathy C.",
  "id": "<urn:uuid:9ad54ec1-b946-4293-8099-abc434ef154c>",
  "metadata": {
    "dump": "CC-MAIN-2023-23",
    "url": "http://505-design.com/tag/boys-party/",
    "date": "2023-05-27T23:24:49Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.9405166506767273
  }
}
```

## Minhash deduplication

My code uses the local executor `LocalPipelineExecutor` to execute the data deduplication pipeline, which includes the following steps:

- **Configuring Minhash**: Setting up Minhash with 64-bit hashes for better precision and fewer false positives (collisions).

- **Reading Input Data**: Using `JsonlReader` to read input data from a specified directory.

- Stage 1: Calculating Minhash Signatures:

  - **Pipeline**: Reads input data and calculates Minhash signatures.
  - **Output**: Stores signatures in a specified folder.
  - **Tasks**: Configured to run with a specified number of tasks based on the local environment.

- Stage 2: Finding Matches Between Signatures in Each Bucket:

  - **Pipeline**: Processes the signatures to find matches within each bucket.
  - **Output**: Stores bucketed signatures in a specified folder.
  - **Tasks**: Runs with a number of tasks equal to the number of buckets.
  - **Dependency**: Depends on the completion of Stage 1.

- Stage 3: Creating Clusters of Duplicates:

  - **Pipeline**: Uses the results from all buckets to create clusters of duplicate items.
  - **Output**: Stores IDs of items to be removed in a specified folder.
  - **Tasks**: Runs as a single task.
  - **Dependency**: Depends on the completion of Stage 2.

- Stage 4: Filtering Out Duplicates:

  - **Pipeline**: Reads the original input data, counts tokens, filters out duplicates (keeping only one sample per cluster), and writes the deduplicated data to JSONL files.
  - **Output**: Stores deduplicated output and removed items in specified folders.
  - **Tasks**: Configured to run with a specified number of tasks.
  - **Dependency**: Depends on the completion of Stage 3.


```
root@david1a100:~/dataclean# cat minhash_deduplication.py
```
```
from datatrove.executor.local import LocalPipelineExecutor
from datatrove.pipeline.dedup import MinhashDedupSignature
from datatrove.pipeline.dedup.minhash import (
    MinhashConfig,
    MinhashDedupBuckets,
    MinhashDedupCluster,
    MinhashDedupFilter,
)
from datatrove.pipeline.readers import JsonlReader
from datatrove.pipeline.tokens import TokensCounter
from datatrove.pipeline.writers.jsonl import JsonlWriter

def main():
   
    minhash_config = MinhashConfig(use_64bit_hashes=True)

    LOCAL_MINHASH_BASE_PATH = "./minhash"
    LOCAL_LOGS_FOLDER = "./logs"
    TOTAL_TASKS = 8 

    INPUT_READER = JsonlReader("./output/output/CC-MAIN-2023-23/")

    stage1 = LocalPipelineExecutor(
        pipeline=[
            INPUT_READER,
            MinhashDedupSignature(output_folder=f"{LOCAL_MINHASH_BASE_PATH}/signatures", config=minhash_config),
        ],
        tasks=TOTAL_TASKS,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/signatures",
    )

    stage2 = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupBuckets(
                input_folder=f"{LOCAL_MINHASH_BASE_PATH}/signatures",
                output_folder=f"{LOCAL_MINHASH_BASE_PATH}/buckets",
                config=minhash_config,
            ),
        ],
        tasks=minhash_config.num_buckets,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/buckets",
        depends=stage1,
    )

    stage3 = LocalPipelineExecutor(
        pipeline=[
            MinhashDedupCluster(
                input_folder=f"{LOCAL_MINHASH_BASE_PATH}/buckets",
                output_folder=f"{LOCAL_MINHASH_BASE_PATH}/remove_ids",
                config=minhash_config,
            ),
        ],
        tasks=1,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/clusters",
        depends=stage2,
    )

    stage4 = LocalPipelineExecutor(
        pipeline=[
            INPUT_READER,
            TokensCounter(), 
            MinhashDedupFilter(
                input_folder=f"{LOCAL_MINHASH_BASE_PATH}/remove_ids",
                exclusion_writer=JsonlWriter(f"{LOCAL_MINHASH_BASE_PATH}/removed"),
            ),
            JsonlWriter(output_folder=f"{LOCAL_MINHASH_BASE_PATH}/deduplicated_output"),
        ],
        tasks=TOTAL_TASKS,
        logging_dir=f"{LOCAL_LOGS_FOLDER}/filter",
        depends=stage3,
    )

    stage4.run()

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
```
Run code:
```
(dataclean) root@david1a100:~/dataclean# python minhash_deduplication.py
```
Result is as following:
```
--- 🛠️ PIPELINE 🛠
📖 - READER: 🐿 Jsonl
🔢 - TOKENIZER: 📊 Counter
🫂 - DEDUP: 🎯 MinHash stage 4
💽 - WRITER: 🐿 Jsonl
2024-08-14 07:20:58.795 | INFO     | datatrove.pipeline.readers.base:read_files_shard:193 - Reading input file 00000.jsonl.gz
2024-08-14 07:20:58.802 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 1/8 tasks completed.
2024-08-14 07:20:58.804 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 2/8 tasks completed.
2024-08-14 07:20:58.805 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 3/8 tasks completed.
2024-08-14 07:20:58.807 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 4/8 tasks completed.
2024-08-14 07:20:58.808 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 5/8 tasks completed.
2024-08-14 07:20:58.810 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 6/8 tasks completed.
2024-08-14 07:20:58.812 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 7/8 tasks completed.
2024-08-14 07:21:08.399 | SUCCESS  | datatrove.executor.base:_run_for_rank:85 - Processing done for rank=0
2024-08-14 07:21:08.401 | INFO     | datatrove.executor.base:_run_for_rank:91 -

📉📉📉 Stats: Task 0 📉📉📉

Total Runtime: 9 seconds

📖 - READER: 🐿 Jsonl
    Runtime: (1.54%) 0 seconds [0.03 milliseconds±0.01 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc], documents: 5727 [5727.00/input_file]}
🔢 - TOKENIZER: 📊 Counter
    Runtime: (79.15%) 7 seconds [1.29 milliseconds±5.90 milliseconds/doc]
    Stats: {tokens: 3989039 [min=54, max=18060, 696.41±1020/doc]}
🫂 - DEDUP: 🎯 MinHash stage 4
    Runtime: (0.44%) 0 seconds [0.01 milliseconds±0.03 milliseconds/doc]
    Stats: {total: 5728, forwarded: 5548, dropped: 180}
💽 - WRITER: 🐿 Jsonl
    Runtime: (18.86%) 1 second [0.32 milliseconds±0.44 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 5548, total: 5548, doc_len: 17896157 [min=257, max=73080, 3225.70±4665/doc], doc_len_tokens: 3943328 [min=54, max=18060, 710.77±1032/doc]}
2024-08-14 07:21:08.405 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 8/8 tasks completed.
2024-08-14 07:21:08.417 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 8 tasks 📉📉📉

Total Runtime: 1 second ± 2 seconds/task

📖 - READER: 🐿 Jsonl
    Runtime: (1.54%) 0 seconds±0 seconds/task, min=0 seconds [0.03 milliseconds±0.01 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 18117059 [min=257, max=73080, 3162.89±4611/doc], documents: 5727 [5727.00/input_file]}
🔢 - TOKENIZER: 📊 Counter
    Runtime: (79.15%) 0 seconds±2 seconds/task, min=0 seconds [1.29 milliseconds±5.90 milliseconds/doc]
    Stats: {tokens: 3989039 [min=54, max=18060, 696.41±1020/doc]}
🫂 - DEDUP: 🎯 MinHash stage 4
    Runtime: (0.44%) 0 seconds±0 seconds/task, min=0 seconds [0.01 milliseconds±0.03 milliseconds/doc]
    Stats: {total: 5728, forwarded: 5548, dropped: 180}
💽 - WRITER: 🐿 Jsonl
    Runtime: (18.86%) 0 seconds±0 seconds/task, min=0 seconds [0.32 milliseconds±0.44 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 5548, total: 5548, doc_len: 17896157 [min=257, max=73080, 3225.70±4665/doc], doc_len_tokens: 3943328 [min=54, max=18060, 710.77±1032/doc]}
```
### Check removed and final result in this part:
```
(dataclean) root@david1a100:~/dataclean/minhash# ls -al removed/
total 76
drwx------ 2 root root  4096 Aug 14 07:20 .
drwx------ 7 root root  4096 Aug 14 07:20 ..
-rw------- 1 root root 65584 Aug 14 07:21 00000.jsonl.gz
(dataclean) root@david1a100:~/dataclean/minhash# ls -al deduplicated_output/
total 7372
drwx------ 2 root root    4096 Aug 14 07:20 .
drwx------ 7 root root    4096 Aug 14 07:20 ..
-rw------- 1 root root 7539420 Aug 14 07:21 00000.jsonl.gz
(dataclean) root@david1a100:~/dataclean/minhash#
```
Check first intem in final output file:
```
(dataclean) root@david1a100:~/dataclean/minhash/deduplicated_output# zcat ./00000.jsonl.gz | head -n 1 | jq .
{
  "text": "Buy Ambien Online Legally (Zolpidem) belongs to the imidazopyridines class of opioids. Ambien complements the exceptional of sleep via way of means of decreasing the time it takes to fall asleep, decreasing the frequency of nocturnal awakenings, and growing the general period of sleep. Lengthens the second one degree of sleep and the deep sleep degree (III and IV). It does now no longer make you sleepy throughout the day. If you’re seeking to Buy Ambien Online at an inexpensive cost, come to our on line pharmacy.",
  "id": "<urn:uuid:dd20979b-ada8-4c5b-b53e-4ade7274bc1b>",
  "metadata": {
    "dump": "CC-MAIN-2023-23",
    "url": "http://42627.dynamicboard.de/u101117_ambienusa.html",
    "date": "2023-05-27T23:12:51Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.8990675806999207,
    "token_count": 120
  }
}
```

## Sentence deduplication

My code uses the local executor `LocalPipelineExecutor` to execute the data deduplication pipeline, which includes the following steps:

- **Configuring Sentence Deduplication**: Setting up sentence deduplication with specific configurations such as the number of sentences, splitting sentences, and minimum document words.

- **Preprocessing Data**: Using NLTK to download the Punkt tokenizer and preprocess data before starting multiprocessing.

- **Reading Input Data**: Using `JsonlReader` to read input data from a specified directory.

- Stage 1: Extracting and Filtering Content:

  - **Pipeline**: Reads input data, extracts content using Trafilatura, filters based on quality and language, and writes intermediate results to JSONL files.
  - **Output**: Stores intermediate results in a specified folder.
  - **Tasks**: Configured to run with a specified number of tasks.

- Stage 2: Calculating Sentence Deduplication Signatures:

  - **Pipeline**: Processes the intermediate results to calculate sentence deduplication signatures.
  - **Output**: Stores signatures in a specified folder.
  - **Tasks**: Runs with a number of tasks equal to the number of finder workers.

- Stage 3: Finding and Filtering Duplicates:

  - **Pipeline**: Reads the intermediate results, finds duplicates using the calculated signatures, and filters out duplicates (keeping only one sample per cluster).

  - **Output**: Stores deduplicated output in a specified folder.

  - **Tasks**: Configured to run with a specified number of tasks.

    The pipeline is executed by running `executor_1.run()`, `executor_2.run()`, and `executor_3.run()`.

```
(dataclean) root@david1a100:~/dataclean# cat sentence_deduplication.py
```
```
import nltk
from nltk.tokenize.punkt import PunktSentenceTokenizer, PunktParameters
from datatrove.executor.base import PipelineExecutor
from datatrove.executor.local import LocalPipelineExecutor
import multiprocessing

# Ensure punkt tokenizer is downloaded before multiprocessing
nltk.download('punkt', force=True)

# Custom function to load PunktSentenceTokenizer
def load_punkt_tokenizer():
    punkt_param = PunktParameters()
    with open(nltk.data.find('tokenizers/punkt/english.pickle'), 'rb') as f:
        tokenizer = PunktSentenceTokenizer(punkt_param)
    return tokenizer

# Load tokenizer in the main process
tokenizer = load_punkt_tokenizer()

# Example configuration for sentence deduplication
sent_dedup_config = SentDedupConfig(
    n_sentences=3,
    split_sentences=True,
    only_dedup_in_index=True,
    min_doc_words=50,
)

FINDER_WORKERS = 10

class TimeStats:
    def __init__(self):
        self.global_mean = 0
        self.global_std_dev = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __repr__(self):
        return f"TimeStats(global_mean={self.global_mean}, global_std_dev={self.global_std_dev})"

    def __add__(self, other):
        result = TimeStats()
        result.global_mean = self.global_mean + other.global_mean
        result.global_std_dev = self.global_std_dev + other.global_std_dev
        return result

class Stat:
    def __init__(self):
        self.value = 0

    def update(self, value, unit=None):
        self.value += value

    def __repr__(self):
        return f"Stat(value={self.value})"

    def __add__(self, other):
        result = Stat()
        result.value = self.value + other.value
        return result

class PipelineStats(UserDict):
    def __init__(self):
        super().__init__()
        self.total_runtime = 0
        self.time_stats = TimeStats()
        self.data['total'] = Stat()
        self.data['removed_sentences'] = Stat()
        self.data['original_sentences'] = Stat()

    def as_dict(self):
        return {
            'total_runtime': self.total_runtime,
            'time_stats': repr(self.time_stats),
            'stats': {key: repr(value) for key, value in self.data.items()}
        }

    def to_dict(self):
        return self.as_dict()

    def to_json(self):
        import json
        return json.dumps(self.to_dict(), indent=4)

    def save_to_disk(self, file):
        file.write(self.to_json())

    def get_repr(self, task_name):
        x = f"\n\n📉📉📉 Stats: {task_name} 📉📉📉\n\nTotal Runtime: {self.total_runtime} seconds\n\n"
        x += "\n".join([repr(stat) for stat in self.data.values()])
        return x

    def __repr__(self, *args, **kwargs):
        return f"PipelineStats(total_runtime={self.total_runtime}, time_stats={self.time_stats})"

    def __add__(self, other):
        result = PipelineStats()
        result.total_runtime = self.total_runtime + other.total_runtime
        result.time_stats = self.time_stats + other.time_stats
        for key in self.data:
            result.data[key] = self.data[key] + other.data[key]
        return result

class CustomSentenceDedupFilter(SentenceDedupFilter):
    def __init__(self, data_folder, config):
        self.data_folder = get_datafolder(data_folder)
        self.config = config
        self._tokenizer = None
        self.exclusion_writer = None
        self.stats = PipelineStats()
        self.language = 'english'

    def set_tokenizer(self, tokenizer):
        self._tokenizer = tokenizer

    def run(self, data, rank, world_size, *args):
        # Implement the logic for the run method here
        # For now, let's just print the arguments to verify they are passed correctly
        print(f"Running with data: {data}, rank: {rank}, world_size: {world_size}, args: {args}")
        # Add your actual processing logic here
        return data

def preprocess_data():
    # Preprocess data using nltk before starting multiprocessing
    # This is a placeholder function. Implement your preprocessing logic here.
    # For example, you can read the input files, tokenize the sentences, and save the preprocessed data.
    pass

def run_example():
    preprocess_data()  # Preprocess data before starting multiprocessing

    pipeline_1 = [
        JsonlReader(data_folder="./minhash/deduplicated_output/"),
        Trafilatura(),
        GopherQualityFilter(min_stop_words=0),
        LanguageFilter(language_threshold=0.5, languages=(Languages.english,)),
        JsonlWriter("./intermediate/"),
        SentenceDedupSignature(output_folder="./c4/sigs", config=sent_dedup_config, finder_workers=FINDER_WORKERS),
    ]

    pipeline_2 = [SentenceFindDedups(data_folder="./c4/sigs", output_folder="./c4/dups", config=sent_dedup_config)]

    sentence_dedup_filter = CustomSentenceDedupFilter(data_folder="./c4/dups", config=sent_dedup_config)
    sentence_dedup_filter.set_tokenizer(tokenizer)

    pipeline_3 = [
        JsonlReader(data_folder="./intermediate/"),
        sentence_dedup_filter,
        JsonlWriter(output_folder="./final_deduplicated_output/"),
    ]

    executor_1: PipelineExecutor = LocalPipelineExecutor(pipeline=pipeline_1, workers=4, tasks=4)
    executor_2: PipelineExecutor = LocalPipelineExecutor(pipeline=pipeline_2, workers=1, tasks=FINDER_WORKERS)
    executor_3: PipelineExecutor = LocalPipelineExecutor(pipeline=pipeline_3, workers=4, tasks=4)

    print(executor_1.run())
    print(executor_2.run())
    print(executor_3.run())

if __name__ == '__main__':
    multiprocessing.freeze_support()
    run_example()
```
Run the script:
```
(dataclean) root@david1a100:~/dataclean# python3 sentence_deduplication.py
```
Some of the output:
```
2024-08-15 03:46:20.151 | INFO     | datatrove.pipeline.dedup.sentence_dedup:run:247 - PQ initialized.
2024-08-15 03:46:20.151 | SUCCESS  | datatrove.executor.base:_run_for_rank:85 - Processing done for rank=9
2024-08-15 03:46:20.152 | INFO     | datatrove.executor.base:_run_for_rank:91 -

📉📉📉 Stats: Task 9 📉📉📉

Total Runtime: 0 seconds

🫂 - DEDUPS: 💥 sentence-deduplication stage 2
    Runtime: (100.00%) 0 seconds [1.17 milliseconds±0 milliseconds/doc]
2024-08-15 03:46:20.156 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 10 tasks 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

🫂 - DEDUPS: 💥 sentence-deduplication stage 2
    Runtime: (100.00%) 0 seconds±0 seconds/task, min=0 seconds, max=0 seconds [1.68 milliseconds±1.21 milliseconds/doc]


📉📉📉 Stats 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

🫂 - DEDUPS: 💥 sentence-deduplication stage 2
    Runtime: (100.00%) 0 seconds±0 seconds/task, min=0 seconds, max=0 seconds [1.68 milliseconds±1.21 milliseconds/doc]
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data] Downloading package punkt to /root/nltk_data...
[nltk_data]   Unzipping tokenizers/punkt.zip.
[nltk_data]   Unzipping tokenizers/punkt.zip.
[nltk_data]   Unzipping tokenizers/punkt.zip.
[nltk_data]   Unzipping tokenizers/punkt.zip.
2024-08-15 03:46:20.887 | INFO     | datatrove.utils.logging:add_task_logger:47 - Launching pipeline for rank=2
2024-08-15 03:46:20.887 | INFO     | datatrove.utils.logging:log_pipeline:76 -
--- 🛠️ PIPELINE 🛠
📖 - READER: 🐿 Jsonl
🫂 - DEDUPS: 💥 sentence-deduplication stage 3
💽 - WRITER: 🐿 Jsonl
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a030>, rank: 2, world_size: 4, args: ()
2024-08-15 03:46:20.887 | WARNING  | datatrove.pipeline.readers.base:run:226 - No files found on /root/dataclean/intermediate for rank=2
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a030>, rank: 1, world_size: 4, args: ()
2024-08-15 03:46:20.887 | SUCCESS  | datatrove.executor.base:_run_for_rank:85 - Processing done for rank=2
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a030>, rank: 0, world_size: 4, args: ()
2024-08-15 03:46:20.888 | INFO     | datatrove.executor.base:_run_for_rank:91 -

📉📉📉 Stats: Task 2 📉📉📉

Total Runtime: 0 seconds

📖 - READER: 🐿 Jsonl
PipelineStats(total_runtime=0, time_stats=TimeStats(global_mean=0, global_std_dev=0))
💽 - WRITER: 🐿 Jsonl
2024-08-15 03:46:20.891 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 1/4 tasks completed.
2024-08-15 03:46:20.892 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 2/4 tasks completed.
2024-08-15 03:46:20.897 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 3/4 tasks completed.
Running with data: <generator object BaseDiskReader.run at 0x7fc2ae75a340>, rank: 3, world_size: 4, args: ()
2024-08-15 03:46:20.911 | INFO     | datatrove.executor.local:_launch_run_for_rank:79 - 4/4 tasks completed.
2024-08-15 03:46:20.948 | SUCCESS  | datatrove.executor.local:run:146 -

📉📉📉 Stats: All 4 tasks 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

📖 - READER: 🐿 Jsonl
    Runtime: (7.77%) 0 seconds±0 seconds/task, min=0 seconds [0.06 milliseconds±0.04 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc], documents: 3 [3.00/input_file]}
PipelineStats(total_runtime=0, time_stats=TimeStats(global_mean=0, global_std_dev=0))
💽 - WRITER: 🐿 Jsonl
    Runtime: (92.23%) 0 seconds±0 seconds/task, min=0 seconds [0.66 milliseconds±0.88 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 4, total: 4, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc]}


📉📉📉 Stats 📉📉📉

Total Runtime: 0 seconds ± 0 seconds/task

📖 - READER: 🐿 Jsonl
    Runtime: (7.77%) 0 seconds±0 seconds/task, min=0 seconds [0.06 milliseconds±0.04 milliseconds/doc]
    Stats: {input_files: 1, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc], documents: 3 [3.00/input_file]}
PipelineStats(total_runtime=0, time_stats=TimeStats(global_mean=0, global_std_dev=0))
💽 - WRITER: 🐿 Jsonl
    Runtime: (92.23%) 0 seconds±0 seconds/task, min=0 seconds [0.66 milliseconds±0.88 milliseconds/doc]
    Stats: {XXXXX.jsonl.gz: 4, total: 4, doc_len: 40103 [min=484, max=30632, 10025.75±14240/doc], doc_len_tokens: 10228 [min=95, max=6656, 2557.00±3132/doc]}
```
Check the the frist item of final output:

```
(dataclean) root@david1a100:~/dataclean/final_deduplicated_output#  zcat ./00000.jsonl.gz | head -n 1 | jq .
```
```
  "text": "Angular 2 has reached Beta and appears poised to become the hot new framework of 2016. It’s time for a showdown. Let’s see how it stacks up against 2015’s darling: React. Disclaimer: I enjoyed working in Angular 1 but switched to React in 2015. I just published a Pluralsight course on React and Flux (free trial). So yes, I’m biased. But I’m attacking both sides. Alright, let’s do this. There will be blood. Angular 2 has reached Beta and appears poised to become the hot new framework of 2016. It’s time for a showdown. Let’s see how it stacks up against 2015’s darling: React. Disclaimer: I enjoyed working in Angular 1 but switched to React in 2015. I’ve published Pluralsight courses on React and Flux and React and Redux in ES6 (free trial). So yes, I’m biased. But I’m attacking both sides. Alright, let’s do this. There will be blood. You’re Comparing Apples and Orangutans! Sigh. Yes, Angular is a framework, React is a library. Some say this difference makes comparing them illogical. Not at all! Choosing between Angular and React is like choosing between buying an off-the-shelf computer and building your own with off-the-shelf parts. This post considers the merits of these two approaches. I compare React’s syntax and component model to Angular’s syntax and component model. This is like comparing an off-the-shelf computer’s CPU to a raw CPU. Apples to apples. Angular 2 Advantages Let’s start by considering Angular 2’s advantages over React. Low Decision Fatigue Since Angular is a framework, it provides significantly more opinions and functionality out of the box. With React, you typically pull a number of other libraries off the shelf to build a real app. You’ll likely want libraries for routing, enforcing unidirectional flows, web API calls, testing, dependency management, and so on. The number of decisions is pretty overwhelming. This is why React has so many starter kits (I’ve published two). Angular offers more opinions out of the box, which helps you get started more quickly without feeling intimidated by decisions. This enforced consistency also helps new hires feel at home more quickly and makes switching developers between teams more practical. I admire how the Angular core team has embraced TypeScript, which leads to the next advantage… TypeScript = Clear Path Sure, TypeScript isn’t loved by all, but Angular 2’s opinionated take on which flavor of JavaScript to use is a big win. React examples across the web are frustratingly inconsistent — it’s presented in ES5 and ES6 in roughly equal numbers, and it currently offers three different ways to declare components. This creates confusion for newcomers. (Angular also embraces decorators instead of extends — many would consider this a plus as well). While Angular 2 doesn’t require TypeScript, the Angular core team certainly embraces it and defaults to using TypeScript in documentation. This means related examples and open source projects are more likely to feel familiar and consistent. Angular already provides clear examples that show how to utilize the TypeScript compiler. (though admittedly, not everyone is embracing TypeScript yet, but I suspect shortly after launch it’ll become the de facto standard). This consistency should help avoid the confusion and decision overload that comes with getting started with React. Reduced Churn 2015 was the year of JavaScript fatigue. Although React itself is expected to be quite stable with version 15 coming soon, React’s ecosystem has churned at a rapid pace, particularly around the long list of Flux flavors and routing. So anything you write in React today may feel out of date or require breaking changes in the future if you lean on one of many related libraries. In contrast, Angular 2 is a careful, methodical reinvention of a mature, comprehensive framework. So Angular is less likely to churn in painful ways after release. And as a full framework, when you choose Angular, you can trust a single team to make careful decisions about the future. In React, it’s your responsibility to herd a bunch of disparate, fast-moving, open-source libraries into a comprehensive whole that plays well together. It’s time-consuming, frustrating, and a never-ending job. Broad Tooling Support As you’ll see below, I consider React’s JSX a big win. However, you need to select tooling that supports JSX. React has become so popular that tooling support is rarely a problem today, but new tooling such as IDEs and linters are unlikely to support JSX on day one. Angular 2’s templates store markup in a string or in separate HTML files, so it doesn’t require special tooling support (though it appears tooling to intelligently parse Angular’s string templates is on the way). Web Component Friendly Angular 2’s design embraces the web component’s standard. Sheesh, I’m embarrassed I forgot to mention this initially — I recently published a course on web components! In short, the components that you build in Angular 2 should be much easier to convert into plain, native web components than React’s components. Sure, browser support is still weak, but this could be a big win in the long-term. Angular’s approach comes with its own set of gotchas, which is a good segue for discussing React’s advantages… React Advantages Alright, let’s consider what sets React apart. JSX JSX is an HTML-like syntax that compiles down to JavaScript. Markup and code are composed in the same file. This means code completion gives you a hand as you type references to your component’s functions and variables. In contrast, Angular’s string-based templates come with the usual downsides: No code coloring in many editors, limited code completion support, and run-time failures. You’d normally expect poor error messaging as well, but the Angular team created their own HTML parser to fix that. (Bravo!) If you don’t like Angular string-based templates, you can move the templates to a separate file, but then you’re back to what I call “the old days:” wiring the two files together in your head, with no code completion support or compile-time checking to assist. That doesn’t seem like a big deal until you’ve enjoyed life in React. Composing components in a single compile-time checked file is one of the big reasons JSX is so special. For more on why JSX is such a big win, see JSX: The Other Side of the Coin. React Fails Fast and Explicitly When you make a typo in React’s JSX, it won’t compile. That’s a beautiful thing. It means you know immediately exactly which line has an error. It tells you immediately when you forget to close a tag or reference a property that doesn’t exist. In fact, the JSX compiler specifies the line number where the typo occurred. This behavior radically speeds development. In contrast, when you mistype a variable reference in Angular 2, nothing happens at all. Angular 2 fails quietly at run time instead of compile-time. It fails slowly. I load the app and wonder why my data isn’t displaying. Not fun. React is JavaScript-Centric Here it is. This is the fundamental difference between React and Angular. Unfortunately, Angular 2 remains HTML-centric rather than JavaScript-centric. Angular 2 failed to solve its most fundamental design problem: Angular 2 continues to put “JS” into HTML. React puts “HTML” into JS. I can’t emphasize the impact of this schism enough. It fundamentally impacts the development experience. Angular’s HTML-centric design remains its greatest weakness. As I cover in “JSX: The Other Side of the Coin”, JavaScript is far more powerful than HTML. Thus, it’s more logical to enhance JavaScript to support markup than to enhance HTML to support logic. HTML and JavaScript need to be glued together somehow, and React’s JavaScript-centric approach is fundamentally superior to Angular, Ember, and Knockout’s HTML-centric approach. Here’s why… React’s JavaScript-centric design = simplicity Angular 2 continues Angular 1’s approach of trying to make HTML more powerful. So you have to utilize Angular 2’s unique syntax for simple tasks like looping and conditionals. For example, Angular 2 offers both one and two way binding via two syntaxes that are unfortunately quite different: {{myVar}} //One-way binding ngModel=\"myVar\" //Two-way binding In React, binding markup doesn’t change based on this decision (it’s handled elsewhere, as I’d argue it should be). In either case, it looks like this: {myVar} Angular 2 supports inline master templates using this syntax:",
  "id": "<urn:uuid:b4dd1e12-c924-4e84-acfb-e3d9894b0ffa>",
  "metadata": 
    "dump": "CC-MAIN-2023-23",
    "url": "http://www.bitnative.com/2016/01/04/angular-2-versus-react/",
    "date": "2023-05-27T23:18:42Z",
    "file_path": "/root/dataclean/data/CC-MAIN-2023-23/segments/CC-MAIN-20230527223515-20230528013515-00000.warc.gz",
    "language": "en",
    "language_score": 0.9108889102935791,
    "token_count": 3354
  

```

##  Exact substrings (Optional)

Refer to : *https://github.com/google-research/deduplicate-text-datasets*

```
(dataclean) root@david1a100:~/dataclean# git clone https://github.com/google-research/deduplicate-text-datasets
#cd deduplicate-text-datasets
#curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
#pip3 install numpy scipy sentencepiece
#pip3 install -r requirements-tf.txt
#cargo build
```
Follow the repo to do rest steps.


